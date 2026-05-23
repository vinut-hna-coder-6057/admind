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

    mode
):

    with get_connection() as conn:

        cursor = conn.cursor()

        cursor.execute("""

        INSERT INTO history (

            video_title,

            category,

            mode,

            created_at

        )

        VALUES (?, ?, ?, ?)

        """, (

            video_title,

            category,

            mode,

            datetime.now().isoformat()
        ))

        conn.commit()


# ─────────────────────────────────────────────────────
# GET RECENT ADS
# ─────────────────────────────────────────────────────

def get_recent_ads(
    limit=3
):

    with get_connection() as conn:

        cursor = conn.cursor()

        cursor.execute("""

        SELECT category

        FROM history

        ORDER BY id DESC

        LIMIT ?

        """, (

            limit,

        ))

        rows = cursor.fetchall()

    return [

        row[0]

        for row in rows
    ]
def get_recent_mode_mismatches(
    current_mode,
    limit=5
):

    with get_connection() as conn:

        cursor = conn.cursor()

        cursor.execute("""

        SELECT category

        FROM history

        ORDER BY id DESC

        LIMIT ?

        """, (limit,))

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