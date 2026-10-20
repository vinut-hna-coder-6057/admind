"""Explicit local/provisioning command; runtime production startup never seeds ads."""
import argparse
import json
from pathlib import Path

from backend.database import init_db, insert_ads
from backend.database import connection


def initialize(database, seed_catalog=False):
    path = Path(database).resolve()
    if not path.parent.is_dir():
        raise FileNotFoundError(f"database parent directory does not exist: {path.parent}")
    connection.DB_NAME = str(path)
    init_db()
    if seed_catalog:
        insert_ads()
    with connection.get_connection() as conn:
        usable_ads = conn.execute(
            "SELECT COUNT(*) FROM ads WHERE trim(COALESCE(ad_name, '')) <> '' "
            "AND trim(COALESCE(description, '')) <> ''"
        ).fetchone()[0]
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
    if usable_ads < 1:
        raise RuntimeError("database initialized, but no usable ads exist; rerun with --seed-catalog")
    return {"database": str(path), "usable_ads": usable_ads, "tables": tables}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, help="absolute path on persistent local storage")
    parser.add_argument("--seed-catalog", action="store_true", help="insert missing starter catalogue rows (never updates existing rows)")
    args = parser.parse_args()
    if not Path(args.database).is_absolute():
        parser.error("--database must be an absolute path")
    print(json.dumps(initialize(args.database, args.seed_catalog), indent=2))


if __name__ == "__main__":
    main()
