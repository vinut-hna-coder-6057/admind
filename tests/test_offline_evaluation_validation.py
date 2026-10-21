import tempfile
import unittest
from pathlib import Path

import pandas as pd

from backend.services.offline_evaluation import evaluate


PACKET = Path(__file__).resolve().parents[1] / "docs" / "recommendation-labels.csv"


class OfflineEvaluationValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.labels = pd.read_csv(PACKET, keep_default_na=False)

    def tearDown(self):
        self.temp.cleanup()

    def evaluate_frame(self, frame):
        labels_path = self.root / "labels.csv"
        frame.to_csv(labels_path, index=False)
        return evaluate(labels_path, self.root / "report.json")

    def test_original_packet_awaits_human_labels_and_packet_is_complete(self):
        report = self.evaluate_frame(self.labels)
        self.assertEqual(report["status"], "awaiting_labels")
        self.assertEqual(report["candidate_packet_pairs"], 120)
        self.assertEqual(report["pending_pairs"], 120)
        self.assertEqual(report["rated_pairs"], 0)
        self.assertIsNone(report["metrics"])

    def test_duplicate_pairs_are_rejected(self):
        frame = pd.concat([self.labels, self.labels.iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.evaluate_frame(frame)

    def test_missing_video_identifier_is_rejected(self):
        frame = self.labels.copy()
        frame.loc[0, "video_id"] = "  "
        with self.assertRaisesRegex(ValueError, "video_id cannot be blank"):
            self.evaluate_frame(frame)

    def test_incomplete_candidate_set_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Incomplete candidate packet"):
            self.evaluate_frame(self.labels.iloc[1:].copy())

    def test_invalid_rating_is_rejected(self):
        frame = self.labels.copy()
        frame.loc[0, "judgment_status"] = "rated"
        frame.loc[0, "relevance"] = "4"
        with self.assertRaisesRegex(ValueError, "0 through 3"):
            self.evaluate_frame(frame)

    def test_rated_row_without_rating_is_rejected(self):
        frame = self.labels.copy()
        frame.loc[0, "judgment_status"] = "rated"
        frame.loc[0, "relevance"] = ""
        with self.assertRaisesRegex(ValueError, "must have a relevance label"):
            self.evaluate_frame(frame)

    def test_invalid_nonblank_rating_is_rejected_even_when_pending(self):
        frame = self.labels.copy()
        frame.loc[0, "relevance"] = "not-a-rating"
        with self.assertRaisesRegex(ValueError, "Relevance values must be integer"):
            self.evaluate_frame(frame)

    def test_held_out_metrics_require_a_frozen_ranker_declaration(self):
        labels_path = self.root / "labels.csv"
        self.labels.to_csv(labels_path, index=False)
        with self.assertRaisesRegex(ValueError, "requires --frozen-ranker-version"):
            evaluate(labels_path, self.root / "report.json", include_held_out=True)


if __name__ == "__main__":
    unittest.main()
