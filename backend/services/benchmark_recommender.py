"""Run a small, offline-friendly benchmark against a disposable copy of ads."""
import argparse
import json
import os
import sqlite3
import statistics
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

from backend.database import connection, init_db
from backend.services.embedding_service import embedding_service
from backend.services.recommender_engine import recommender_engine
from backend.services.vector_store import vector_store


def _rss_mb():
    try:
        import psutil
        return round(psutil.Process().memory_info().rss / (1024 * 1024), 1)
    except (ImportError, OSError):
        return "not_measured"


def benchmark(title, iterations=10, source_db=None):
    if iterations < 1:
        raise ValueError("iterations must be positive")
    source = Path(source_db or connection.DB_NAME)
    if str(source) == ":memory:":
        raise ValueError("benchmark needs a persistent source SQLite catalogue")
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"catalogue database not found: {source}")

    uri = f"file:{quote(source.as_posix(), safe='/:')}?mode=ro"
    with sqlite3.connect(uri, uri=True) as source_conn:
        rows = source_conn.execute(
            "SELECT ad_name, description, category, mode, created_at FROM ads ORDER BY ad_name"
        ).fetchall()
    if not rows:
        raise ValueError("source catalogue contains no ads")

    with tempfile.TemporaryDirectory(prefix="admind-benchmark-") as temp_dir:
        previous_db = connection.DB_NAME
        connection.DB_NAME = os.path.join(temp_dir, "benchmark.db")
        try:
            init_db()
            with connection.get_connection() as conn:
                conn.executemany(
                    "INSERT INTO ads(ad_name, description, category, mode, created_at) VALUES (?, ?, ?, ?, ?)",
                    rows,
                )
            start = time.perf_counter()
            first = recommender_engine.rank(title, "study", "casual")
            cold_ms = (time.perf_counter() - start) * 1000
            warm_ms = []
            for _ in range(iterations):
                start = time.perf_counter()
                recommender_engine.rank(title, "study", "casual")
                warm_ms.append((time.perf_counter() - start) * 1000)
            return {
                "python": __import__("sys").version.split()[0],
                "model": "all-MiniLM-L6-v2 (lazy; lexical fallback if unavailable)",
                "source_catalogue": str(source),
                "catalogue_ads": len(rows),
                "video_title": title,
                "cold_first_request_ms": round(cold_ms, 2),
                "cold_stage_timings_ms": {
                    "embedding_model_load": embedding_service.model_load_ms,
                    **vector_store.initialization_timings_ms,
                    "stage_note": "Model load is nested inside title_batch_encoding; stage durations are first-process observations, not additive latency estimates.",
                },
                "process_rss_mb_after_cold_request": _rss_mb(),
                "warm_iterations": iterations,
                "warm_median_ms": round(statistics.median(warm_ms), 2),
                "warm_max_ms": round(max(warm_ms), 2),
                "first_recommendation": first.get("ad_name") if first else None,
                "score_basis": first.get("relevance_basis") if first else None,
                "database_writes": "temporary copy only",
            }
        finally:
            connection.DB_NAME = previous_db


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", default="How to use Python for data analysis")
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--db", default=None, help="source SQLite database; defaults to configured DB_NAME")
    args = parser.parse_args()
    print(json.dumps(benchmark(args.title, args.iterations, args.db), indent=2))


if __name__ == "__main__":
    main()
