from datetime import datetime

from backend.database.connection import (
    get_connection
)


# ─────────────────────────────────────────────────────
# SAVE HISTORY
# ─────────────────────────────────────────────────────

def save_history(

    video_title,

    category,

    mode,
    ad_category=None,
    session_id=None
):

    with get_connection() as conn:

        cursor = conn.cursor()

        cursor.execute("""

        INSERT INTO history (

            video_title,

            category,

            mode,

            ad_category,

            session_id,

            created_at

        )

        VALUES (?, ?, ?, ?, ?, ?)

        """, (

            video_title,

            category,

            mode,

            ad_category,

            session_id,

            datetime.now().isoformat()
        ))

        conn.commit()


# ─────────────────────────────────────────────────────
# GET RECENT ADS
# ─────────────────────────────────────────────────────

def get_recent_ads(
    limit=3,
    session_id=None
):

    with get_connection() as conn:

        if not session_id:
            return []
        cursor = conn.cursor()

        cursor.execute("""

        SELECT ad_category

        FROM history
        WHERE session_id = ? AND ad_category IS NOT NULL

        ORDER BY id DESC

        LIMIT ?

        """, (

            session_id,

            limit,

        ))

        rows = cursor.fetchall()

    return [

        row[0]

        for row in rows
    ]
def get_recent_mode_mismatches(
    current_mode,
    limit=5,
    session_id=None
):

    with get_connection() as conn:

        cursor = conn.cursor()

        if not session_id:
            return False
        cursor.execute("""

        SELECT category

        FROM history
        WHERE session_id = ?

        ORDER BY id DESC

        LIMIT ?

        """, (session_id, limit))

        rows = cursor.fetchall()

    categories = [

        row[0]

        for row in rows
    ]

    entertainment_categories = [

        "entertainment",
        "gaming",
        "fashion",
        "food",
        "comedy"
    ]

    mismatch_count = sum(

        1

        for cat in categories

        if (
            current_mode == "study"
            and cat in entertainment_categories
        )
    )

    return mismatch_count >= 4
