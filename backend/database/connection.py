import sqlite3
import os

from dotenv import load_dotenv

# load env variables
load_dotenv()

# ─────────────────────────────────────────────────────
#backend.database NAME
# ─────────────────────────────────────────────────────

DB_NAME = os.getenv(
    "DB_NAME",
    "admind.db"
)

# ─────────────────────────────────────────────────────
# GET CONNECTION
# ─────────────────────────────────────────────────────

def get_connection():

    return sqlite3.connect(DB_NAME)

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

        conn.commit()