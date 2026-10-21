import unittest

import pandas as pd

from backend.services.labeling_review import render_review_html, verified_youtube_id


VIDEO_ID = "dQw4w9WgXcQ"


class LabelingReviewTests(unittest.TestCase):
    def row(self, **overrides):
        row = {
            "video_id": "ytanalytics-stable-key",
            "video_title": "Recorded title",
            "ad_id": "ad-1",
            "ad_name": "Useful tool",
            "ad_description": "A detailed description",
            "source_video_url": f"https://www.youtube.com/watch?v={VIDEO_ID}",
            "source_video_url_verified": "true",
            "source_video_verified_by": "reviewer@example.test",
            "source_video_verified_at": "2026-10-20",
            "source_video_verification_source": "https://www.youtube.com/watch?v=" + VIDEO_ID,
            "source_video_verification_method": "Compared official title and channel",
        }
        row.update(overrides)
        return row

    def test_only_provenance_backed_https_youtube_links_are_accepted(self):
        row = self.row()
        self.assertEqual(verified_youtube_id(row), VIDEO_ID)
        self.assertEqual(verified_youtube_id(self.row(source_video_verified_by="")), "")
        self.assertEqual(verified_youtube_id(self.row(source_video_verification_source="")), "")
        self.assertEqual(verified_youtube_id(self.row(source_video_url_verified="false")), "")
        self.assertEqual(verified_youtube_id(self.row(source_video_url=f"http://youtu.be/{VIDEO_ID}")), "")
        self.assertEqual(verified_youtube_id(self.row(source_video_url=f"https://example.test/{VIDEO_ID}")), "")

    def test_html_embeds_only_verified_video_and_keeps_ad_metadata(self):
        html = render_review_html(pd.DataFrame([self.row()]))
        self.assertIn("https://www.youtube-nocookie.com/embed/${videoIdForEmbed}", html)
        self.assertIn("verified && verifier && verifiedAt", html)
        self.assertIn(VIDEO_ID, html)
        self.assertIn("Open unverified candidate on YouTube to check identity", html)
        self.assertIn("A detailed description", html)
        unverified = render_review_html(pd.DataFrame([self.row(source_video_url_verified="false")]))
        self.assertIn('"source_video_url_verified": "false"', unverified)


if __name__ == "__main__":
    unittest.main()
