from backend.database.connection import (
    get_connection
)


# ─────────────────────────────────────────────────────
# SAVE FEEDBACK
# ─────────────────────────────────────────────────────

def save_feedback(

    ad_name,

    feedback
):

    with get_connection() as conn:

        cursor = conn.cursor()

        cursor.execute("""

        INSERT INTO feedback (

            ad_name,

            feedback,

            created_at

        )

        VALUES (

            ?, ?, datetime('now')

        )

        """, (

            ad_name,

            feedback
        ))

        conn.commit()


# ─────────────────────────────────────────────────────
# FEEDBACK SCORES
# ─────────────────────────────────────────────────────

def get_feedback_score():

    with get_connection() as conn:

        cursor = conn.cursor()

        cursor.execute("""

        SELECT

            ad_name,

            SUM(

                CASE

                    WHEN feedback='positive'

                    THEN 1

                    ELSE -1

                END

            ) as score

        FROM feedback

        GROUP BY ad_name

        """)

        rows = cursor.fetchall()

    return {

        row[0]: row[1]

        for row in rows
    }


# ─────────────────────────────────────────────────────
# FEEDBACK STATS
# ─────────────────────────────────────────────────────

def get_feedback_stats():

    with get_connection() as conn:

        cursor = conn.cursor()

        cursor.execute("""

        SELECT

            feedback,

            COUNT(*)

        FROM feedback

        GROUP BY feedback

        """)

        rows = cursor.fetchall()

    stats = {

        "positive": 0,

        "negative": 0
    }

    for row in rows:

        stats[row[0]] = row[1]

    return stats