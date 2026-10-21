# Recommendation quality evaluation and labeling

## Available data and current evidence

The configured SQLite catalogue contains 30 ads and currently matches `backend/datasets/ads_dataset.csv` row-for-row. The live video category index reads 537 records from `backend/datasets/youtube_analytics.csv` across 12 YouTube categories. That file has titles, channel names, publication dates, category IDs, and analytics, but no YouTube video IDs, descriptions, tags, or transcripts. `backend/datasets/videos_dataset.csv` contains 14 title/mode/category examples without source IDs; it is not used as the live video source. There were no human relevance labels when this packet was created.

The packet generator selects one title from each available category, preferring records whose title terms fit the source category and then more descriptive titles. It assigns a stable dataset record key from the source row, category ID, and title. This key is **not** a YouTube video ID. The packet includes the source file, row, channel, publication timestamp, original category, and a flag when title terms do not support the source category. Review the title and source metadata; do not treat a category ID as proof of the video's subject. The ads' stable IDs are their SQLite primary keys (`ad_name`).

For each video, the selector includes up to two lexical-overlap candidates, category-context candidates, then seeded category-balanced samples from the rest of the catalogue. This is not the current ranker's top-K list: it intentionally includes cross-category alternatives. Selection cues are not labels or proof of likely relevance. The generated set currently has 12 videos and 120 videoÃ¢â‚¬â€œad pairs (10 per video); all labels remain blank.

## Reproduce the packet

Run from the repository root. The command reads the configured SQLite database read-only and falls back to the versioned CSV only if that database or its `ads` table is unavailable. It does not initialize or modify the database.

```powershell
python -m backend.services.labeling_dataset --output docs/recommendation-labels.csv --videos 12 --ads-per-video 10 --seed 20261019
```

The seed and deterministic sampling keep IDs, train/held-out split, and candidates stable for a fixed source dataset and catalogue. The generator refuses to overwrite any packet that contains ratings or non-pending review statuses. To check for accidental packet changes after labeling, generate to a second path and compare it without replacing the reviewed file:

```powershell
python -m backend.services.labeling_dataset --output docs/recommendation-labels-regenerated.csv --videos 12 --ads-per-video 10 --seed 20261019
git diff --no-index docs/recommendation-labels.csv docs/recommendation-labels-regenerated.csv
```

The regenerated file contains pending labels; remove it after comparison. `--force` explicitly discards a reviewed packet's labels and should only be used when that is intended.

## Human labeling workflow

The original `docs/recommendation-labels.csv` is the frozen 120-pair manifest: 12 stable video-record keys, 10 ads per video, and a `development` or `held_out` split. Its `video_id` is a source-row key, not a YouTube ID. It remains the canonical candidate set and must not be overwritten. Current human-facing artifacts are [recommendation-labels-human-review.csv](../artifacts/recommendation-labels-human-review.csv) and [recommendation-human-review.html](../artifacts/recommendation-human-review.html). The earlier generated artifacts are preserved separately.

The HTML page groups the complete candidate set for each video and displays its stable ID, title, source channel/date/category, split, candidate count, and every ad's name, description, category, and mode. It shows no ranks or scores. Each candidate has a status, a 0â€“3 rating control, and a notes field. The split exports keep development and held-out judgments in separate CSVs. Do not combine the files or make held-out labels available to anyone changing ranking logic.

### Exact reviewer procedure

1. Open `artifacts/recommendation-human-review.html`. Review one entire video group at a time. Confirm its stable video key, split, and candidate count (10) before rating; all 10 ads in the group are the complete candidate set for this packet.
2. Review the recorded title, channel, publication date, source category, and the actual ad name, description, category, and mode. Do not infer subject or need from a broad category alone.
3. The source audit is in [recommendation-video-source-matches.md](recommendation-video-source-matches.md). A metadata-confirmed URL is not proof that the footage matches: inspect the actual footage. Uncertain candidate URLs are available as clearly labeled links for manual identity checks but are not embedded. Do not replace an unresolved source with a similarly titled result.
4. For each ad, select `Rated` and an integer: `0` = irrelevant; `1` = weak/incidental; `2` = relevant to the specific subject or supported need; `3` = highly relevant, specific, and useful. Add a short reason in notes, especially for borderline ratings.
5. If source/title context is too ambiguous to judge responsibly, select `Insufficient information`, leave the numeric rating blank, and state the exact missing information in notes. Leave unreviewed candidates `Pending`. A video set contributes no quality metrics unless all 10 candidates have numeric ratings.
6. Use **Download development labels** for the development file. Keep **Download sealed held-out labels** in a separate access-controlled location, unavailable to anyone changing ranking, features, or parameters. Do not inspect or disclose held-out scores/examples until the ranker is frozen and identified by version. Then a separate evaluator invocation may reveal the held-out result.
7. Preserve `video_id`, `video_title`, `ad_id`, split, source provenance, and ad metadata. Do not create AI or synthetic ratings. Resolve reviewer disagreements before evaluation; a second independent reviewer on a sample is recommended.

Rating scale: `0` irrelevant; `1` weak/incidental or tangential; `2` relevant and clearly addresses the specific subject or supported need; `3` highly relevant, specific, and useful. A complete candidate-set review can still be excluded from metrics if any pair is `insufficient_information`.

The review CSV remains unlabeled: 120 pairs are pending and no ratings have been generated. Source identity states are evidence-only and are not relevance labels. Do not change ranking weights from this packet without reliable human relevance evidence.

## Evaluate

Validate the full candidate set against the frozen packet before scoring:

```powershell
python -m backend.services.offline_evaluation --labels artifacts/recommendation-labels-development-reviewed.csv --packet docs/recommendation-labels.csv --output artifacts/recommendation-evaluation.json --k 5
```

The evaluator rejects blank video identifiers, duplicate video/ad labels, invalid/non-integer ratings, split changes, and missing or unexpected candidate pairs. Pending and insufficient rows are counted but never scored; every candidate in a video set must have a numeric rating before that set enters metrics. No label is inferred. With no complete development set it reports `awaiting_labels` and null metrics.

Held-out metrics and examples are sealed by default. Only after ranking is frozen, provide an explicit immutable ranker version to reveal the held-out results:

```powershell
python -m backend.services.offline_evaluation --labels artifacts/recommendation-labels-held_out-reviewed.csv --packet docs/recommendation-labels.csv --output artifacts/recommendation-held-out-evaluation.json --k 5 --include-held-out-after-freeze --frozen-ranker-version <frozen-version>
```

This explicit gate documents the evaluation phase; organizational access controls must still keep the held-out file away from the ranking/tuning process until freeze. Metrics are macro NDCG@K, Precision@K (relevance â‰¥2), Recall@K (within sampled candidates), and MRR. The content baseline is `max(title/ad-description cosine, inferred-video-category/ad-category cosine)`; candidate replay uses current title-to-offering cosine, lexical tie-breaking, and duplicate suppression. This small stratified packet is diagnostic, not a representative estimate of production quality. No ranking logic or weights are changed by labeling or evaluation.
## Video context investigation

The dashboard calls `get_video_details`, which uses the already-configured YouTube Data API key and `videos.list(part="snippet")`. YouTube documents that the snippet includes title, description, tags, and category ID ([Videos: list](https://developers.google.com/youtube/data/reference/rest/v3/videos/list)); the current function returns only title and tags. Returning the description from this same response would not require another request. The existing request has a five-second HTTP timeout and catches service/API errors, but there is no explicit retry or rate-limit backoff. The dashboard currently falls back to title-only when no description is available; if the title itself cannot be fetched, the opaque video ID is not usable as content.

No transcript integration exists. Avoid unofficial transcript scraping/downloading; YouTube's Terms restrict automated access except in specified cases ([Terms of Service](https://www.youtube.com/t/terms)). The maintainable next context step is to expose the public snippet description from the existing official API call, bound its length, use it only in-memory, and keep title-only behavior when it is empty/unavailable. This context change is deferred until the labeling packet can show title-only failure cases and an evaluation can compare the same pairs. No ranking changes have been made from synthetic tests alone.
