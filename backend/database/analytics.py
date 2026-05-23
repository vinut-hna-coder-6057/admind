import logging
import pandas as pd

from .connection import get_connection

logger = logging.getLogger(__name__)
# ─────────────────────────────────────────────────────
# TRACK SHOWN
# ─────────────────────────────────────────────────────

def track_shown(ad_name):

    with get_connection() as conn:

        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO analytics (

            ad_name,
            shown,
            clicked

        )
        VALUES (?, 1, 0)

        ON CONFLICT(ad_name)

        DO UPDATE SET
        shown = shown + 1
        """, (ad_name,))

        conn.commit()


# ─────────────────────────────────────────────────────
# TRACK CLICKED
# ─────────────────────────────────────────────────────

def track_clicked(ad_name):

    with get_connection() as conn:

        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO analytics (

            ad_name,
            shown,
            clicked

        )
        VALUES (?, 0, 1)

        ON CONFLICT(ad_name)

        DO UPDATE SET
        clicked = clicked + 1
        """, (ad_name,))

        conn.commit()


# ─────────────────────────────────────────────────────
# GET ANALYTICS
# ─────────────────────────────────────────────────────

def get_analytics():

    with get_connection() as conn:

        try:

            return pd.read_sql_query("""
            SELECT *
            FROM analytics
            """, conn)

        except Exception as e:

            logger.exception(
                "Failed to load analytics"
            )

            return pd.DataFrame()
        
def get_ctr_scores():

    with get_connection() as conn:

        df = pd.read_sql_query("""
        SELECT *
        FROM analytics
        """, conn)

        if df.empty:

            return {}

        scores = {}

        for _, row in df.iterrows():

            shown = row["shown"]

            clicked = row["clicked"]

            ctr = (
                clicked / shown
                if shown > 0
                else 0
            )

            scores[
                row["ad_name"]
            ] = ctr

        return scores