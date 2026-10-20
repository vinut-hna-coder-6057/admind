# Recommendation quality evaluation and labeling

## Available data and current evidence

The configured SQLite catalogue contains 30 ads and currently matches `backend/datasets/ads_dataset.csv` row-for-row. The live video category index reads 537 records from `backend/datasets/youtube_analytics.csv` across 12 YouTube categories. That file has titles, channel names, publication dates, category IDs, and analytics, but no YouTube video IDs, descriptions, tags, or transcripts. `backend/datasets/videos_dataset.csv` contains 14 title/mode/category examples without source IDs; it is not used as the live video source. There were no human relevance labels when this packet was created.

The packet generator selects one title from each available category, preferring records whose title terms fit the source category and then more descriptive titles. It assigns a stable dataset record key from the source row, category ID, and title. This key is **not** a YouTube video ID. The packet includes the source file, row, channel, publication timestamp, original category, and a flag when title terms do not support the source category. Review the title and source metadata; do not treat a category ID as proof of the video's subject. The ads' stable IDs are their SQLite primary keys (`ad_name`).

For each video, the selector includes up to two lexical-overlap candidates, category-context candidates, then seeded category-balanced samples from the rest of the catalogue. This is not the current ranker's top-K list: it intentionally includes cross-category alternatives. Selection cues are not labels or proof of likely relevance. The generated set currently has 12 videos and 120 video–ad pairs (10 per video); all labels remain blank.

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

Generate `artifacts/recommendation-review.html` with `python -m backend.services.labeling_review --input docs/recommendation-labels.csv --output artifacts/recommendation-review.html`, then open that local file in a browser. It groups each complete video candidate set and displays the recorded source title/channel/date/category plus each ad's name, description, category, and mode. It shows no model rank or score. The **Download reviewed CSV** button creates a separate `recommendation-labels-reviewed.csv`; keep it separate from the source packet, inspect it, then pass it as `--labels` to the evaluator only after human review.

The source video dataset has no YouTube IDs or URLs, descriptions, or transcripts. The stable `video_id` is a dataset-row key, not a YouTube ID. Do not guess a link from the title. To review footage, add these four optional columns to a **separate copy** of the packet, repeating the same values for every ad row for that video: `source_video_url`, `source_video_url_verified`, `source_video_verified_by`, and `source_video_verified_at`. A reviewer must manually verify that an HTTPS YouTube URL shows the recorded title/channel before setting the verified field to `true` and recording verifier/date. The review page embeds only provenance-backed YouTube URLs using youtube-nocookie; unverified/missing links are not embedded. Keep packet IDs, split, original provenance, and ad metadata unchanged. The generated source packet remains unchanged and all judgments remain blank. If footage cannot be verified or is unavailable, use `insufficient_information` when recorded metadata cannot support a responsible judgment. Such rows are excluded from metrics; an evaluated video set must contain numeric ratings for every candidate.

Open `docs/recommendation-labels.csv` in a spreadsheet. Each row is one video–ad judgment. Keep `video_id`, `video_title`, `ad_id`, source columns, split, and ad metadata unchanged. Set `judgment_status` to `rated` and enter an integer in `relevance`; if the available title/source details do not let you judge the offering, set `judgment_status` to `insufficient_information`, leave relevance blank, and explain what is missing in `label_notes`. Leave unreviewed rows as `pending`. Metrics include a video only when all candidates for that video are rated, avoiding incomplete candidate lists that favor one ranking.

Judge the ad name and actual description against the video's specific subject or an evident need. A shared broad category or generic word is not sufficient. Use the source channel/date to disambiguate a title when useful. Do not infer a need that the title and source context do not support. A video with only an ambiguous or opaque title should be marked insufficient rather than guessed.

Scale:

- `0` — irrelevant; no meaningful connection to the video's subject or need.
- `1` — weak/incidental; a generic or tangential connection, with little practical usefulness.
- `2` — relevant; the offering clearly addresses the video's specific subject or a supported need.
- `3` — highly relevant and useful; the offering is a strong, specific fit and its benefit is clear.

Reviewers should not see model rankings or scores while labeling. If possible, use two reviewers for a sample of pairs and resolve disagreements before evaluating. The held-out videos are marked `held_out`; do not use them to tune ranking choices. With only three held-out videos in this starter packet, held-out metrics will be descriptive and underpowered.

## Evaluate

```powershell
python -m backend.services.offline_evaluation --labels docs/recommendation-labels.csv --output artifacts/recommendation-evaluation.json --k 5
```

The evaluator first writes an `awaiting_labels` report with no metrics if there are no fully judged videos. It does not infer labels. Once one or more videos are fully judged, it reports per-split macro NDCG@5, Precision@5 (relevance ≥2), Recall@5 (relevance ≥2 within the selected candidates), and MRR. It also records the distribution of human labels, incomplete/insufficient videos, candidate top-ad examples for held-out videos, and held-out examples where candidate NDCG is below baseline. A scored-pairs CSV is written beside the JSON output. Failure classifications come only from human labels.

The reproducible content baseline is `max(title↔ad-description cosine, inferred-video-category↔ad-category cosine)`. It isolates the previous content score. Historical production ranking is not reproducible from available data: historical CTR, session history, mode, audience, and per-ad feedback are not logged as a complete per-request feature snapshot. The candidate replay uses current title↔(ad name + description) cosine, lexical tie-breaking, and duplicate suppression. The model's semantic score is not calibrated. Metrics apply only to fully judged packet candidates, not every catalogue ad; Recall@5 is therefore relative to the sampled candidate set. This small, source-category-stratified packet is an initial diagnostic, not a statistically representative estimate of production quality.

No ranking adjustment should be tuned on the held-out split. Do not claim improved recommendation quality unless held-out labeled results support it.

## Video context investigation

The dashboard calls `get_video_details`, which uses the already-configured YouTube Data API key and `videos.list(part="snippet")`. YouTube documents that the snippet includes title, description, tags, and category ID ([Videos: list](https://developers.google.com/youtube/data/reference/rest/v3/videos/list)); the current function returns only title and tags. Returning the description from this same response would not require another request. The existing request has a five-second HTTP timeout and catches service/API errors, but there is no explicit retry or rate-limit backoff. The dashboard currently falls back to title-only when no description is available; if the title itself cannot be fetched, the opaque video ID is not usable as content.

No transcript integration exists. Avoid unofficial transcript scraping/downloading; YouTube's Terms restrict automated access except in specified cases ([Terms of Service](https://www.youtube.com/t/terms)). The maintainable next context step is to expose the public snippet description from the existing official API call, bound its length, use it only in-memory, and keep title-only behavior when it is empty/unavailable. This context change is deferred until the labeling packet can show title-only failure cases and an evaluation can compare the same pairs. No ranking changes have been made from synthetic tests alone.
