"""Explicit, count-only retention cleanup for history, feedback, and events."""
import argparse
import json
import sqlite3
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

from backend.database.connection import DB_NAME

_COUNT_QUERIES = {
    "history": "SELECT COUNT(*) FROM history WHERE date(created_at) < date(?)",
    "feedback": "SELECT COUNT(*) FROM feedback WHERE date(created_at) < date(?)",
    "analytics_events": "SELECT COUNT(*) FROM analytics_events WHERE date(created_at) < date(?)",
}
_INHERIT_CUTOFF = object()


def purge_before(database, cutoff_date=None, apply=False, feedback_cutoff_date=_INHERIT_CUTOFF, events_cutoff_date=_INHERIT_CUTOFF):
    feedback_cutoff_date = cutoff_date if feedback_cutoff_date is _INHERIT_CUTOFF else feedback_cutoff_date
    events_cutoff_date = cutoff_date if events_cutoff_date is _INHERIT_CUTOFF else events_cutoff_date
    cutoffs = {
        "history": date.fromisoformat(str(cutoff_date)).isoformat() if cutoff_date is not None else None,
        "feedback": date.fromisoformat(str(feedback_cutoff_date)).isoformat() if feedback_cutoff_date is not None else None,
        "analytics_events": date.fromisoformat(str(events_cutoff_date)).isoformat() if events_cutoff_date is not None else None,
    }
    path = Path(database).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"database not found: {path}")
    with closing(sqlite3.connect(path, timeout=30)) as conn:
        conn.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        conn.execute("PRAGMA busy_timeout = 30000")
        counts = {
            table: conn.execute(
                _COUNT_QUERIES[table],
                (table_cutoff,),
            ).fetchone()[0] if table_cutoff is not None else 0
            for table, table_cutoff in cutoffs.items()
        }
        old_events = conn.execute(
            "SELECT ad_name, event_type, COUNT(*) FROM analytics_events "
            "WHERE date(created_at) < date(?) GROUP BY ad_name, event_type",
            (cutoffs["analytics_events"],),
        ).fetchall() if cutoffs["analytics_events"] is not None else []
        if apply:
            if cutoffs["history"] is not None:
                conn.execute("DELETE FROM history WHERE date(created_at) < date(?)", (cutoffs["history"],))
            if cutoffs["feedback"] is not None:
                conn.execute("DELETE FROM feedback WHERE date(created_at) < date(?)", (cutoffs["feedback"],))
            if cutoffs["analytics_events"] is not None:
                conn.execute("DELETE FROM analytics_events WHERE date(created_at) < date(?)", (cutoffs["analytics_events"],))
            # Preserve legacy aggregate offsets while subtracting only events removed here.
            for ad_name, event_type, count in old_events:
                if event_type == "impression":
                    conn.execute("UPDATE analytics SET shown = MAX(0, shown - ?) WHERE ad_name = ?", (count, ad_name))
                else:
                    conn.execute("UPDATE analytics SET clicked = MAX(0, clicked - ?) WHERE ad_name = ?", (count, ad_name))
            conn.commit()
        else:
            conn.rollback()
    return {
        "database": str(path),
        "cutoff_dates_exclusive": cutoffs,
        "mode": "apply" if apply else "dry_run",
        "matched_rows": {key: int(value) for key, value in counts.items()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=DB_NAME)
    parser.add_argument("--older-than-days", type=int, help="compatibility shorthand; applies one age to all three record tables")
    parser.add_argument("--history-days", type=int)
    parser.add_argument("--feedback-days", type=int)
    parser.add_argument("--events-days", type=int)
    parser.add_argument("--apply", action="store_true", help="perform deletion; default only reports counts")
    args = parser.parse_args()
    ages = {
        "history": args.history_days if args.history_days is not None else args.older_than_days,
        "feedback": args.feedback_days if args.feedback_days is not None else args.older_than_days,
        "events": args.events_days if args.events_days is not None else args.older_than_days,
    }
    if all(value is None for value in ages.values()):
        parser.error("provide --older-than-days or one or more table-specific --*-days options")
    if any(value is not None and value < 1 for value in ages.values()):
        parser.error("retention ages must be at least 1 day")
    cutoffs = {key: date.today() - timedelta(days=value) for key, value in ages.items() if value is not None}
    result = purge_before(
        args.database,
        cutoffs.get("history"),
        args.apply,
        feedback_cutoff_date=cutoffs.get("feedback"),
        events_cutoff_date=cutoffs.get("events"),
    )
    result["configured_ages_days"] = ages
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
