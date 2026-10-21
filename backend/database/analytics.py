import logging
import uuid
import pandas as pd

from .connection import get_connection

logger = logging.getLogger(__name__)
# ─────────────────────────────────────────────────────
# TRACK SHOWN
# ─────────────────────────────────────────────────────

def _track_event(ad_name, event_type, event_id, request_id=None):

    with get_connection() as conn:

        cursor = conn.cursor()

        if event_type == "click":
            if not request_id:
                return False
            cursor.execute("""
            SELECT 1 FROM analytics_events
            WHERE request_id = ? AND ad_name = ? AND event_type = 'impression'
            LIMIT 1
            """, (request_id, ad_name))
            if cursor.fetchone() is None:
                return False

        cursor.execute("""
        INSERT OR IGNORE INTO analytics_events(event_id, request_id, ad_name, event_type)
        VALUES (?, ?, ?, ?)
        """, (event_id, request_id, ad_name, event_type))
        if cursor.rowcount == 0:
            return False

        shown_delta = 1 if event_type == "impression" else 0
        clicked_delta = 1 if event_type == "click" else 0
        cursor.execute("""
        INSERT INTO analytics (

            ad_name,
            shown,
            clicked

        )
        VALUES (?, ?, ?)

        ON CONFLICT(ad_name)

        DO UPDATE SET
        shown = shown + excluded.shown,
        clicked = clicked + excluded.clicked
        """, (ad_name, shown_delta, clicked_delta))

        conn.commit()
        return True


def track_shown(ad_name, event_id=None, request_id=None):
    event_id = event_id or (f"impression:{request_id}:{ad_name}" if request_id else str(uuid.uuid4()))
    return _track_event(ad_name, "impression", event_id, request_id)


# ─────────────────────────────────────────────────────
# TRACK CLICKED
# ─────────────────────────────────────────────────────

def track_clicked(ad_name, event_id=None, request_id=None):
    event_id = event_id or (f"click:{request_id}:{ad_name}" if request_id else str(uuid.uuid4()))
    return _track_event(ad_name, "click", event_id, request_id)


# ─────────────────────────────────────────────────────
# GET ANALYTICS
# ─────────────────────────────────────────────────────

def get_analytics():

    with get_connection() as conn:

        try:

            # The aggregate table predates event IDs and mixed positive feedback
            # into clicked counts. Report only auditable post-migration events.
            return pd.read_sql_query("""
            SELECT ad_name,
                   SUM(CASE WHEN event_type = 'impression' THEN 1 ELSE 0 END) AS shown,
                   SUM(CASE WHEN event_type = 'click' THEN 1 ELSE 0 END) AS clicked
            FROM analytics_events
            GROUP BY ad_name
            ORDER BY ad_name
            """, conn)

        except Exception:

            logger.exception(
                "Failed to load analytics"
            )

            return pd.DataFrame()
        
def get_ctr_scores():

    with get_connection() as conn:

        df = pd.read_sql_query("""
        SELECT ad_name,
               SUM(CASE WHEN event_type = 'impression' THEN 1 ELSE 0 END) AS shown,
               SUM(CASE WHEN event_type = 'click' THEN 1 ELSE 0 END) AS clicked
        FROM analytics_events
        GROUP BY ad_name
        """, conn)

        if df.empty:

            return {}

        scores = {}

        for _, row in df.iterrows():

            shown = row["shown"]

            clicked = row["clicked"]

            ctr = (
                min(max(clicked / shown, 0), 1)
                if shown > 0
                else 0
            )

            scores[
                row["ad_name"]
            ] = ctr

        return scores
