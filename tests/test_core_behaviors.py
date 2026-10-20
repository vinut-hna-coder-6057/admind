import os
import tempfile
import sys
import types
import unittest
import sqlite3
import hashlib
from contextlib import closing
from unittest.mock import patch

import numpy as np
import pandas as pd

from backend.database import (
    get_analytics,
    get_feedback_score,
    get_recent_ads,
    init_db,
    save_feedback,
    save_history,
    get_ctr_scores,
    track_clicked,
    track_shown,
)
from backend.database import connection
from backend.services.youtube_api import extract_video_id, get_video_details, choose_video_title
from backend.config import config
from backend.services.recommender_engine import AdRecommenderEngine
from backend.services.vector_store import VectorStore
from backend.services.embedding_service import EmbeddingService
from backend.api import RequestData, app as api_app
import backend.api as api_module
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.services.video_understanding import detect_video_category
from backend.services.offline_evaluation import ranking_metrics
from backend.services.offline_evaluation import evaluate
from backend.services.labeling_dataset import build_labeling_set, write_labeling_set
from backend.services.labeling_review import render_review_html
from backend.services.sqlite_backup import backup_database, restore_database, inspect_database
from backend.services.retention import purge_before
from backend.services.local_load_test import run_load_test


class TemporaryDatabaseTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        self.db_patch = patch.object(connection, "DB_NAME", self.db_path)
        self.db_patch.start()
        init_db()

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_feedback_is_averaged_and_does_not_create_clicks(self):
        save_feedback("Course", "positive")
        save_feedback("Course", "positive")
        save_feedback("Course", "negative")
        self.assertAlmostEqual(get_feedback_score()["Course"], 1 / 3)
        self.assertTrue(get_analytics().empty)

    def test_extreme_feedback_count_remains_bounded(self):
        with connection.get_connection() as conn:
            conn.executemany(
                "INSERT INTO feedback(ad_name, feedback, created_at) VALUES (?, ?, datetime('now'))",
                [("Popular", "positive") for _ in range(2000)],
            )
        self.assertEqual(get_feedback_score()["Popular"], 1.0)

    def test_repeated_request_impression_is_idempotent(self):
        self.assertTrue(track_shown("Course", request_id="request-1"))
        self.assertFalse(track_shown("Course", request_id="request-1"))
        self.assertTrue(track_shown("Course", request_id="request-2"))
        analytics = get_analytics().set_index("ad_name")
        self.assertEqual(int(analytics.loc["Course", "shown"]), 2)

    def test_legacy_aggregate_data_is_preserved_but_not_mixed_into_valid_events(self):
        with connection.get_connection() as conn:
            conn.execute("INSERT INTO analytics(ad_name, shown, clicked) VALUES ('Legacy', 10, 4)")
        init_db()
        with connection.get_connection() as legacy:
            self.assertEqual(legacy.execute("SELECT shown, clicked FROM analytics WHERE ad_name='Legacy'").fetchone(), (10, 4))
        self.assertTrue(get_analytics().empty)

    def test_migration_preserves_rows_from_the_original_history_schema(self):
        with connection.get_connection() as conn:
            conn.execute("DROP TABLE history")
            conn.execute("CREATE TABLE history (id INTEGER PRIMARY KEY, video_title TEXT, category TEXT, mode TEXT, created_at TEXT)")
            conn.execute("INSERT INTO history VALUES (7, 'Old video', 'education', 'study', '2024-01-01')")
        init_db()
        with connection.get_connection() as conn:
            row = conn.execute("SELECT video_title, category, ad_category, session_id FROM history WHERE id=7").fetchone()
        self.assertEqual(row, ("Old video", "education", None, None))

    def test_click_requires_an_impression_and_is_idempotent(self):
        self.assertFalse(track_clicked("Course", request_id="missing"))
        track_shown("Course", request_id="request-1")
        self.assertEqual(get_ctr_scores()["Course"], 0.0)
        self.assertTrue(track_clicked("Course", request_id="request-1"))
        self.assertFalse(track_clicked("Course", request_id="request-1"))
        analytics = get_analytics().set_index("ad_name")
        self.assertEqual(int(analytics.loc["Course", "shown"]), 1)
        self.assertEqual(int(analytics.loc["Course", "clicked"]), 1)
        self.assertEqual(get_ctr_scores()["Course"], 1.0)

    def test_history_diversity_uses_ad_category_and_session_scope(self):
        save_history("Video", "education", "study", ad_category="programming", session_id="s1")
        save_history("Another", "education", "study", ad_category="devices", session_id="s2")
        self.assertEqual(get_recent_ads(session_id="s1"), ["programming"])
        self.assertEqual(get_recent_ads(session_id="s2"), ["devices"])
        self.assertEqual(get_recent_ads(session_id="unknown"), [])
        # The additive migration is safe to rerun and leaves history intact.
        init_db()
        self.assertEqual(get_recent_ads(session_id="s1"), ["programming"])

    def test_backup_restore_and_retention_are_explicit_and_count_only(self):
        with connection.get_connection() as conn:
            conn.execute("INSERT INTO ads(ad_name, description) VALUES ('Course', 'Useful course')")
            conn.execute("INSERT INTO history(video_title, category, mode, created_at) VALUES ('Private title', 'education', 'study', '2020-01-01')")
            conn.execute("INSERT INTO feedback(ad_name, feedback, created_at) VALUES ('Course', 'positive', '2020-01-01')")
            conn.execute("INSERT INTO analytics_events(event_id, ad_name, event_type, request_id, created_at) VALUES ('old-event', 'Course', 'impression', 'old-request', '2020-01-01')")
            conn.execute("INSERT INTO analytics(ad_name, shown, clicked) VALUES ('Course', 1, 0)")
        dry_run = purge_before(self.db_path, "2021-01-01")
        self.assertEqual(dry_run["mode"], "dry_run")
        self.assertEqual(dry_run["matched_rows"], {"history": 1, "feedback": 1, "analytics_events": 1})
        self.assertNotIn("Private title", str(dry_run))
        with connection.get_connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM history").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT shown FROM analytics WHERE ad_name='Course'").fetchone()[0], 1)
            conn.execute("UPDATE analytics SET shown=11 WHERE ad_name='Course'")
        self.assertEqual(purge_before(self.db_path, "2021-01-01", apply=True)["mode"], "apply")
        with connection.get_connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM history").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM analytics_events").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT shown FROM analytics WHERE ad_name='Course'").fetchone()[0], 10)
            conn.execute("INSERT INTO history(video_title, category, mode, created_at) VALUES ('Scoped title', 'education', 'study', '2020-01-01')")
            conn.execute("INSERT INTO feedback(ad_name, feedback, created_at) VALUES ('Course', 'negative', '2020-01-01')")
            conn.execute("INSERT INTO analytics_events(event_id, ad_name, event_type, created_at) VALUES ('scoped-event', 'Course', 'impression', '2020-01-01')")
            conn.execute("PRAGMA journal_mode=WAL")
        scoped = purge_before(
            self.db_path,
            "2021-01-01",
            apply=True,
            feedback_cutoff_date=None,
            events_cutoff_date=None,
        )
        self.assertEqual(scoped["matched_rows"], {"history": 1, "feedback": 0, "analytics_events": 0})
        with connection.get_connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM history").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM analytics_events").fetchone()[0], 1)
        backup_path = os.path.join(self.temp_dir.name, "backup.db")
        restored_path = os.path.join(self.temp_dir.name, "restored.db")
        before = inspect_database(self.db_path)
        backup = backup_database(self.db_path, backup_path)
        self.assertEqual(backup["integrity"], "ok")
        self.assertEqual(backup["tables"], before["tables"])
        self.assertEqual(backup["indexes"], before["indexes"])
        self.assertEqual(restore_database(backup_path, restored_path)["tables"]["ads"], 1)
        self.assertEqual(inspect_database(restored_path)["indexes"], before["indexes"])
        self.assertEqual(inspect_database(restored_path)["integrity"], "ok")
        with self.assertRaises(FileExistsError):
            restore_database(backup_path, restored_path)


class YouTubeUrlTest(unittest.TestCase):
    def test_supported_urls_and_rejections(self):
        video_id = "dQw4w9WgXcQ"
        self.assertEqual(extract_video_id(f"https://www.youtube.com/watch?v={video_id}&t=1"), video_id)
        self.assertEqual(extract_video_id(f"https://youtu.be/{video_id}?si=abc"), video_id)
        self.assertEqual(extract_video_id(f"https://youtube.com/shorts/{video_id}"), video_id)
        for value in ("", "x" * 2049, f"https://youtube.com.evil.test/watch?v={video_id}", "https://youtu.be/nope"):
            self.assertIsNone(extract_video_id(value))

    def test_api_request_validation(self):
        request = RequestData(title="Video title", mode="focus", user_type="developer")
        self.assertEqual(request.mode, "focus")
        for payload in (
            {"title": "", "mode": "study"},
            {"title": "x" * 501, "mode": "study"},
            {"title": "title", "mode": "unknown"},
            {"title": "title", "mode": "study", "user_type": "unknown"},
        ):
            with self.assertRaises(ValidationError):
                RequestData(**payload)

    def test_local_load_test_refuses_remote_or_non_http_targets(self):
        for value in ("https://127.0.0.1:8000", "http://example.com:8000", "file://127.0.0.1/etc/passwd"):
            with self.assertRaises(ValueError):
                run_load_test(value, 1, 1, "valid")

    def test_api_health_validation_and_safe_service_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(connection, "DB_NAME", os.path.join(temp_dir, "api.db")),
                patch("backend.api.insert_ads"),
                patch("backend.api.recommender_engine.rank", side_effect=RuntimeError("internal detail")),
                TestClient(api_app) as client,
            ):
                self.assertEqual(client.get("/livez").json(), {"status": "alive"})
                self.assertEqual(client.get("/readyz").status_code, 503)
                self.assertEqual(client.get("/health").status_code, 503)
                with connection.get_connection() as conn:
                    conn.execute(
                        "INSERT INTO ads(ad_name, description, category, mode) VALUES (?, ?, ?, ?)",
                        ("Example course", "A useful course", "education", "study"),
                    )
                self.assertEqual(client.get("/health").json(), {"status": "healthy"})
                self.assertEqual(client.get("/readyz").status_code, 200)
                invalid = client.post("/recommend-ad", json={"title": "", "mode": "unsupported"})
                self.assertEqual(invalid.status_code, 422)
                oversized = client.post("/recommend-ad", content=b"{" + b" " * (16 * 1024), headers={"content-type": "application/json"})
                self.assertEqual(oversized.status_code, 413)
                with self.assertLogs("backend.api", level="ERROR") as logged:
                    failed = client.post("/recommend-ad", json={"title": "A video", "mode": "study"})
                self.assertEqual(failed.status_code, 500)
                self.assertEqual(failed.json(), {"detail": "Internal recommendation error"})
                self.assertNotIn("internal detail", " ".join(logged.output))

    def test_metadata_lookup_handles_missing_key_and_service_failure(self):
        valid_url = "https://youtu.be/dQw4w9WgXcQ"
        with patch("backend.services.youtube_api.API_KEY", None):
            self.assertIsNone(get_video_details(valid_url))
        failed_request = types.SimpleNamespace(execute=lambda: (_ for _ in ()).throw(RuntimeError("service unavailable")))
        youtube = types.SimpleNamespace(videos=lambda: types.SimpleNamespace(list=lambda **_kwargs: failed_request))
        discovery = types.ModuleType("googleapiclient.discovery")
        discovery.build = lambda *_args, **_kwargs: youtube
        httplib2 = types.ModuleType("httplib2")
        httplib2.Http = lambda **_kwargs: object()
        with (
            patch("backend.services.youtube_api.API_KEY", "test-key"),
            patch.dict(sys.modules, {"googleapiclient.discovery": discovery, "httplib2": httplib2}),
        ):
            self.assertIsNone(get_video_details(valid_url))

    def test_manual_video_title_is_used_as_safe_metadata_fallback(self):
        self.assertEqual(choose_video_title("  Corrected topic  ", ("Fetched topic", [])), "Corrected topic")
        self.assertEqual(choose_video_title("  ", ("Fetched topic", [])), "Fetched topic")
        self.assertEqual(choose_video_title("", None), "")

    def test_feedback_requires_an_explicit_relevance_choice(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "frontend"))
        from ui.dashboard_page import feedback_vote_value
        self.assertIsNone(feedback_vote_value("Select one"))
        self.assertEqual(feedback_vote_value("Relevant"), "positive")
        self.assertEqual(feedback_vote_value("Irrelevant"), "negative")

    def test_admin_page_guard_and_production_configuration_fail_closed(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "frontend"))
        from ui.admin_page import admin_authorized
        self.assertFalse(admin_authorized({}))
        self.assertFalse(admin_authorized({"admin_logged_in": False}))
        self.assertTrue(admin_authorized({"admin_logged_in": True}))

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "production.db")
            salt = b"test-production-salt"
            digest = hashlib.pbkdf2_hmac("sha256", b"unused-test-password", salt, 100_000).hex()
            password_hash = f"pbkdf2_sha256$100000${salt.hex()}${digest}"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE ads(ad_name TEXT, description TEXT)")
                conn.commit()
            with patch.dict(os.environ, {"DB_NAME": db_path}):
                with patch.object(config, "ADMIND_ENV", "production"), patch.object(config, "STREAMLIT_COOKIE_SECRET", ""), patch.object(config, "ADMIN_PASSWORD_HASH", password_hash):
                    with self.assertRaisesRegex(RuntimeError, "COOKIE_SECRET"):
                        config.validate_production_settings()
                with closing(sqlite3.connect(db_path)) as conn:
                    conn.execute("INSERT INTO ads VALUES ('Course', 'Useful course')")
                    conn.commit()
                with patch.object(config, "ADMIND_ENV", "production"), patch.object(config, "STREAMLIT_COOKIE_SECRET", "c" * 48), patch.object(config, "ADMIN_PASSWORD_HASH", password_hash):
                    config.validate_production_settings()

    def test_production_api_startup_never_seeds_or_exposes_admin_routes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "production-start.db")
            with (
                patch.object(connection, "DB_NAME", db_path),
                patch.object(api_module, "ADMIND_ENV", "production"),
                patch.object(api_module, "validate_production_settings"),
                patch.object(api_module, "insert_ads") as seed_catalogue,
                TestClient(api_app),
            ):
                seed_catalogue.assert_not_called()
                with connection.get_connection() as conn:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM ads").fetchone()[0], 0)
            self.assertFalse(any(getattr(route, "path", "").startswith("/admin") for route in api_app.routes))


class RecommendationScoringTest(unittest.TestCase):
    def test_blinded_review_html_groups_complete_video_sets_and_escapes_metadata(self):
        packet = pd.DataFrame([
            {
                "video_id": "source-1", "video_title": "Title <script>alert(1)</script>",
                "source_dataset": "source.tsv", "source_row": 4, "source_category": "music",
                "source_category_fit": "unverified", "source_channel": "Channel",
                "source_published_at": "2025-01-01", "split": "held_out",
                "ad_id": "A", "ad_name": "Ad A", "ad_description": "Description A",
                "ad_category": "devices", "ad_mode": "casual", "judgment_status": "pending",
                "relevance": "", "label_notes": "", "ad_catalog_source": "sqlite:test.db",
            },
            {
                "video_id": "source-1", "video_title": "Title <script>alert(1)</script>",
                "source_dataset": "source.tsv", "source_row": 4, "source_category": "music",
                "source_category_fit": "unverified", "source_channel": "Channel",
                "source_published_at": "2025-01-01", "split": "held_out",
                "ad_id": "B", "ad_name": "Ad B", "ad_description": "Description B",
                "ad_category": "finance", "ad_mode": "study", "judgment_status": "pending",
                "relevance": "", "label_notes": "", "ad_catalog_source": "sqlite:test.db",
            },
        ])
        document = render_review_html(packet)
        self.assertEqual(document.count("Candidate count:"), 1)
        self.assertIn("Candidate count:", document)
        self.assertIn("Description A", document)
        self.assertIn("Description B", document)
        self.assertNotIn("<script>alert(1)</script>", document)
        self.assertIn("\\u003cscript\\u003e", document)
        self.assertIn("Source records have no verified video IDs", document)

    def test_label_packet_is_deterministic_and_unlabeled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            videos = os.path.join(temp_dir, "videos.tsv")
            pd.DataFrame([{
                "Title": "Music album review", "channel_title": "Source Channel",
                "published_at": "2025-01-01", "category_id": 10,
            }]).to_csv(videos, sep="\t", index=False)
            ads = pd.DataFrame([
                {"ad_name": "Headphones", "description": "Wireless earbuds for music", "category": "devices", "mode": "casual"},
                {"ad_name": "Trading App", "description": "Stock market investing platform", "category": "finance", "mode": "professional"},
                {"ad_name": "Music Streaming", "description": "Ad-free music streaming", "category": "entertainment", "mode": "casual"},
            ])
            first = build_labeling_set(12, 3, 7, videos_path=videos, ads=ads)
            second = build_labeling_set(12, 3, 7, videos_path=videos, ads=ads)
            packet_path = os.path.join(temp_dir, "packet.csv")
            write_labeling_set(first, packet_path)
            reviewed = pd.read_csv(packet_path)
            reviewed.loc[0, "judgment_status"] = "rated"
            reviewed.loc[0, "relevance"] = 2
            reviewed.to_csv(packet_path, index=False)
            with self.assertRaises(FileExistsError):
                write_labeling_set(first, packet_path)
        pd.testing.assert_frame_equal(first, second)
        self.assertEqual(len(first), 3)
        self.assertTrue((first["judgment_status"] == "pending").all())
        self.assertTrue((first["relevance"] == "").all())
        self.assertEqual(first.iloc[0]["ad_id"], first.iloc[0]["ad_name"])

    def test_offline_evaluation_reports_pending_without_quality_claim(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            labels = os.path.join(temp_dir, "labels.csv")
            output = os.path.join(temp_dir, "result.json")
            pd.DataFrame([{
                "video_id": "source-row-1", "video_title": "Music album review",
                "ad_name": "Spotify Premium", "relevance": "", "judgment_status": "pending",
                "split": "held_out",
            }]).to_csv(labels, index=False)
            report = evaluate(labels, output)
        self.assertEqual(report["status"], "awaiting_labels")
        self.assertIsNone(report["metrics"])
        self.assertEqual(report["pending_pairs"], 1)

    def test_offline_metrics_use_graded_relevance_and_top_k(self):
        metrics = ranking_metrics([
            {"ad_name": "Useful", "score": 0.9, "relevance": 3},
            {"ad_name": "Weak", "score": 0.8, "relevance": 1},
            {"ad_name": "Other", "score": 0.1, "relevance": 0},
        ], k=2)
        self.assertEqual(metrics["ndcg_at_k"], 1.0)
        self.assertEqual(metrics["precision_at_k"], 0.5)
        self.assertEqual(metrics["recall_at_k"], 1.0)
        self.assertEqual(metrics["mrr"], 1.0)

    def test_known_unknown_and_mixed_video_categories(self):
        with patch("backend.services.video_understanding.vector_store.search", return_value=[
            ({"category_id": 27}, 0.8), ({"category_id": 999}, 0.2),
        ]):
            category, score = detect_video_category("query")
        self.assertEqual(category, "education")
        self.assertAlmostEqual(score, 0.5)
        with patch("backend.services.video_understanding.vector_store.search", return_value=[
            ({"category_id": 999}, 0.3),
        ]):
            category, _ = detect_video_category("query")
        self.assertEqual(category, "general")

    def test_rank_uses_offering_semantics_not_category_similarity(self):
        ads = pd.DataFrame([
            {"ad_name": "Python Course", "description": "Learn Python programming", "category": "education", "mode": ["study"]},
            {"ad_name": "Trading App", "description": "Trade stocks and investments", "category": "education", "mode": ["study"]},
        ])
        vectors = {
            "python programming tutorial": np.array([1.0, 0.0]),
            "Python Course. Learn Python programming": np.array([0.9, 0.1]),
            "Trading App. Trade stocks and investments": np.array([0.0, 1.0]),
        }
        engine = AdRecommenderEngine()
        with (
            patch("backend.services.recommender_engine.load_ads", return_value=ads),
            patch("backend.services.recommender_engine.detect_video_category", return_value=("education", 0.99)),
            patch("backend.services.recommender_engine.get_recent_mode_mismatches", return_value=False),
            patch("backend.services.recommender_engine.save_history"),
            patch("backend.services.recommender_engine.embedding_service.encode", side_effect=lambda value: vectors[value]),
            patch("backend.services.recommender_engine.embedding_service.similarity", side_effect=lambda a, b: float(np.dot(a, b))),
        ):
            result = engine.rank("python programming tutorial", "study", "casual")
        self.assertEqual(result["ad_name"], "Python Course")
        self.assertAlmostEqual(result["relevance_score"], 0.9)
        self.assertNotIn("confidence", result)

    def test_missing_title_metadata_returns_no_arbitrary_ad(self):
        engine = AdRecommenderEngine()
        self.assertIsNone(engine.rank("dQw4w9WgXcQ", "study", "student"))

    def test_missing_ad_description_and_duplicate_offerings_are_skipped(self):
        ads = pd.DataFrame([
            {"ad_name": "Blank", "description": "", "category": "technology", "mode": ["study"]},
            {"ad_name": "Python Course", "description": "Learn Python programming", "category": "technology", "mode": ["study"]},
            {"ad_name": "Python Duplicate", "description": "Python programming learn", "category": "technology", "mode": ["study"]},
            {"ad_name": "Stock App", "description": "Manage your stock investments", "category": "technology", "mode": ["study"]},
        ])
        vectors = {
            "Python programming tutorial": np.array([1.0, 0.0]),
            "Python Course. Learn Python programming": np.array([0.9, 0.1]),
            "Python Duplicate. Python programming learn": np.array([0.9, 0.1]),
            "Stock App. Manage your stock investments": np.array([0.1, 0.9]),
        }
        with (
            patch("backend.services.recommender_engine.load_ads", return_value=ads),
            patch("backend.services.recommender_engine.detect_video_category", return_value=("technology", 1.0)),
            patch("backend.services.recommender_engine.get_recent_mode_mismatches", return_value=False),
            patch("backend.services.recommender_engine.save_history"),
            patch("backend.services.recommender_engine.embedding_service.encode", side_effect=lambda value: vectors[value]),
            patch("backend.services.recommender_engine.embedding_service.similarity", side_effect=lambda a, b: float(np.dot(a, b))),
        ):
            result = AdRecommenderEngine().rank("Python programming tutorial", "study", "student")
        self.assertEqual(result["ad_name"], "Python Course")

    def test_vector_store_handles_empty_data_and_numpy_fallback(self):
        empty_store = VectorStore()
        with (
            patch("backend.services.vector_store.load_youtube_dataset", return_value=pd.DataFrame()),
            patch("backend.services.vector_store.prepare_dataset", return_value=pd.DataFrame()),
        ):
            empty_store.initialize()
        self.assertEqual(empty_store.search("query", k=5), [])
        self.assertEqual(empty_store.search("query", k=0), [])

        rows = pd.DataFrame([{"title": "first", "category_id": 10}, {"title": "second", "category_id": 20}])
        store = VectorStore()
        embeddings = {"first": np.array([1.0, 0.0]), "second": np.array([0.0, 1.0]), "query": np.array([0.9, 0.1])}
        with (
            patch.dict(sys.modules, {"faiss": None}),
            patch("backend.services.vector_store.load_youtube_dataset", return_value=rows),
            patch("backend.services.vector_store.prepare_dataset", return_value=rows),
            patch("backend.services.vector_store.embedding_service.encode_many", side_effect=lambda values: [embeddings[value] for value in values]),
            patch("backend.services.vector_store.embedding_service.encode", side_effect=lambda value: embeddings[value]),
        ):
            store.initialize()
            results = store.search("query", k=50)
        self.assertEqual([row["title"] for row, _ in results], ["first", "second"])

    def test_embedding_model_failure_is_cached_and_category_index_falls_back(self):
        calls = []
        fake_module = types.ModuleType("sentence_transformers")
        def fail_to_load(_model_name):
            calls.append(1)
            raise OSError("offline model unavailable")
        fake_module.SentenceTransformer = fail_to_load
        service = EmbeddingService()
        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            for _ in range(2):
                with self.assertRaises((OSError, RuntimeError)):
                    service.encode("query")
        self.assertEqual(len(calls), 1)

        missing_service = EmbeddingService()
        with patch.dict(sys.modules, {"sentence_transformers": None}):
            with self.assertRaises(ImportError):
                missing_service.encode("query")
            with self.assertRaises(RuntimeError):
                missing_service.encode("query")

        store = VectorStore()
        rows = pd.DataFrame([{"title": "one", "category_id": 10}])
        with (
            patch("backend.services.vector_store.load_youtube_dataset", return_value=rows),
            patch("backend.services.vector_store.prepare_dataset", return_value=rows),
            patch("backend.services.vector_store.embedding_service.encode_many", side_effect=OSError("offline")) as encode,
        ):
            store.initialize()
            store.initialize()
            self.assertEqual(store.search("query"), [])
        self.assertEqual(encode.call_count, 1)

    def test_vector_store_encodes_dataset_titles_in_one_batch(self):
        rows = pd.DataFrame([{"title": "one", "category_id": 10}, {"title": "two", "category_id": 20}])
        batches = []
        def encode_many(values):
            batches.append(values)
            return [np.array([1.0, 0.0]), np.array([0.0, 1.0])]
        store = VectorStore()
        with (
            patch("backend.services.vector_store.load_youtube_dataset", return_value=rows),
            patch("backend.services.vector_store.prepare_dataset", return_value=rows),
            patch("backend.services.vector_store.embedding_service.encode_many", side_effect=encode_many),
        ):
            store.initialize()
        self.assertEqual(batches, [["one", "two"]])
        self.assertEqual(store.embeddings.shape, (2, 2))

    def test_admin_password_hash_fails_closed_and_checks_hash(self):
        self.assertFalse(config.verify_admin_password("anything"))
        import hashlib
        salt = b"test-salt"
        digest = hashlib.pbkdf2_hmac("sha256", b"correct", salt, 100_000).hex()
        with patch.object(config, "ADMIN_PASSWORD_HASH", f"pbkdf2_sha256$100000${salt.hex()}${digest}"):
            self.assertTrue(config.verify_admin_password("correct"))
            self.assertFalse(config.verify_admin_password("incorrect"))


if __name__ == "__main__":
    unittest.main()
