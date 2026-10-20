import sqlite3
import os
from contextlib import contextmanager

from dotenv import load_dotenv

# load env variables
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# ─────────────────────────────────────────────────────
#backend.database NAME
# ─────────────────────────────────────────────────────

configured_db_name = os.getenv("DB_NAME", os.path.join(PROJECT_ROOT, "admind.db"))
DB_NAME = (configured_db_name if configured_db_name == ":memory:" or os.path.isabs(configured_db_name)
           else os.path.join(PROJECT_ROOT, configured_db_name))

# ─────────────────────────────────────────────────────
# GET CONNECTION
# ─────────────────────────────────────────────────────

@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_NAME, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        with conn:
            yield conn
    finally:
        conn.close()

# ─────────────────────────────────────────────────────
# INITbackend.database
# ─────────────────────────────────────────────────────

def init_db():

    with get_connection() as conn:

        cursor = conn.cursor()

        # ADS TABLE
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ads (

            ad_name TEXT PRIMARY KEY,

            description TEXT,

            category TEXT,

            mode TEXT,

            created_at TEXT
        )
        """)

        # FEEDBACK TABLE
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            ad_name TEXT,

            feedback TEXT,

            created_at TEXT
        )
        """)

        # ANALYTICS TABLE
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS analytics (

            ad_name TEXT PRIMARY KEY,

            shown INTEGER DEFAULT 0,

            clicked INTEGER DEFAULT 0
        )
        """)

        # HISTORY TABLE
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            video_title TEXT,

            category TEXT,

            mode TEXT,

            created_at TEXT
        )
        """)
        history_columns = {row[1] for row in cursor.execute("PRAGMA table_info(history)")}
        if "ad_category" not in history_columns:
            cursor.execute("ALTER TABLE history ADD COLUMN ad_category TEXT")
        if "session_id" not in history_columns:
            cursor.execute("ALTER TABLE history ADD COLUMN session_id TEXT")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_session_id ON history(session_id, id)")

        # Additive event storage preserves the legacy aggregate table and records.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS analytics_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            request_id TEXT,
            ad_name TEXT NOT NULL,
            event_type TEXT NOT NULL CHECK(event_type IN ('impression', 'click')),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_events_ad_type ON analytics_events(ad_name, event_type)")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_analytics_events_request_ad_type ON analytics_events(request_id, ad_name, event_type) WHERE request_id IS NOT NULL")

        conn.commit()
