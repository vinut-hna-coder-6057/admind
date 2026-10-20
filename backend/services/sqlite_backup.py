"""Consistent SQLite backup, verification, and non-overwriting restore helpers."""
import argparse
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from urllib.parse import quote

from backend.database.connection import DB_NAME

_TABLE_COUNT_QUERIES = {
    "ads": "SELECT COUNT(*) FROM ads",
    "feedback": "SELECT COUNT(*) FROM feedback",
    "analytics": "SELECT COUNT(*) FROM analytics",
    "history": "SELECT COUNT(*) FROM history",
    "analytics_events": "SELECT COUNT(*) FROM analytics_events",
}


def _readonly_connection(path):
    resolved = Path(path).resolve()
    uri = f"file:{quote(resolved.as_posix(), safe='/:')}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def inspect_database(path):
    with closing(_readonly_connection(path)) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise sqlite3.DatabaseError("SQLite integrity check failed")
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        indexes = [
            {"name": row[0], "table": row[1], "sql": row[2]}
            for row in conn.execute(
                "SELECT name, tbl_name, sql FROM sqlite_master "
                "WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts = {
            table: conn.execute(_TABLE_COUNT_QUERIES[table]).fetchone()[0]
            for table in tables if table in _TABLE_COUNT_QUERIES
        }
        return {"integrity": integrity, "tables": counts, "indexes": indexes, "sqlite_version": sqlite3.sqlite_version}


def _copy_database(source, output):
    source = Path(source).resolve()
    output = Path(output).resolve()
    if source == output:
        raise ValueError("source and output paths must be different")
    if not source.is_file():
        raise FileNotFoundError(f"SQLite source not found: {source}")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing SQLite output: {output}")
    if not output.parent.is_dir():
        raise FileNotFoundError(f"output directory does not exist: {output.parent}")

    fd, temporary_name = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".partial", dir=output.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with closing(_readonly_connection(source)) as src, closing(sqlite3.connect(temporary)) as dst:
            src.backup(dst)
            dst.commit()
        result = inspect_database(temporary)
        if "ads" not in result["tables"]:
            raise sqlite3.DatabaseError("database is missing the required ads table")
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            # Windows ACLs remain the operator's responsibility.
            pass
        os.replace(temporary, output)
        return {"path": str(output), **result}
    finally:
        if temporary.exists():
            temporary.unlink()


def backup_database(source, output):
    """Use SQLite's online backup API, including committed WAL contents."""
    return _copy_database(source, output)


def restore_database(backup, output):
    """Restore to a new path; never replace the configured live database."""
    return _copy_database(backup, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    backup = sub.add_parser("backup")
    backup.add_argument("--source", default=DB_NAME)
    backup.add_argument("--output", required=True)
    restore = sub.add_parser("restore")
    restore.add_argument("--backup", required=True)
    restore.add_argument("--output", required=True, help="new restore path; existing files are never overwritten")
    verify = sub.add_parser("verify")
    verify.add_argument("--database", required=True)
    args = parser.parse_args()
    if args.command == "backup":
        result = backup_database(args.source, args.output)
    elif args.command == "restore":
        result = restore_database(args.backup, args.output)
    else:
        result = {"path": str(Path(args.database).resolve()), **inspect_database(args.database)}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
