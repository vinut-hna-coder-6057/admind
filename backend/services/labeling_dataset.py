"""Create a deterministic, unlabeled human review packet from repository data."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from backend.database.connection import DB_NAME
from backend.services.category_map import CATEGORY_MAP


ROOT = Path(__file__).resolve().parents[2]
VIDEO_DATA = ROOT / "backend" / "datasets" / "youtube_analytics.csv"
AD_CSV = ROOT / "backend" / "datasets" / "ads_dataset.csv"
STOPWORDS = {
    "the", "and", "for", "with", "from", "your", "you", "how", "what", "this", "that", "are", "was",
    "best", "new", "official", "video", "watch", "full", "part", "episode", "shorts", "live", "in", "of",
}
TOKEN = __import__("re").compile(r"[a-z0-9]{2,}")
ADJACENT_AD_CATEGORIES = {
    "education": {"education", "programming", "technology"},
    "technology": {"technology", "devices", "programming", "productivity"},
    "gaming": {"gaming", "devices", "entertainment"},
    "entertainment": {"entertainment", "gaming"},
    "film": {"entertainment"},
    "music": {"entertainment", "devices", "wellness"},
    "sports": {"wellness", "devices", "food"},
    "travel": {"devices", "finance", "entertainment"},
    "fashion": {"fashion", "devices"},
    "news": {"finance", "technology"},
    "comedy": {"entertainment"},
}
TOPIC_TERMS = {
    "film": {"film", "movie", "trailer", "teaser", "cinema", "disney"},
    "gaming": {"game", "games", "gameplay", "gaming", "minecraft", "roblox", "fortnite"},
    "blogs": {"vlog", "daily", "lifestyle", "day", "life"},
    "news": {"news", "breaking", "report", "reporter", "politics", "election"},
    "travel": {"travel", "places", "destination", "vacation", "visit", "country", "city", "wonders"},
    "technology": {"technology", "tech", "artificial", "intelligence", "ai", "computer", "phone", "software", "chatgpt"},
    "education": {"learn", "learning", "tutorial", "course", "class", "classroom", "lesson", "lecture", "explained", "education"},
    "entertainment": {"show", "shows", "series", "episode", "celebrity", "entertainment", "reality"},
    "music": {"music", "song", "singer", "album", "artist", "dj", "producer", "audio"},
    "fashion": {"fashion", "outfit", "clothes", "style", "sneakers", "beauty", "makeup"},
    "comedy": {"comedy", "funny", "joke", "prank", "laugh", "gone", "wrong"},
    "sports": {"sports", "football", "soccer", "basketball", "tennis", "cricket", "match", "league"},
}


def _tokens(value):
    return {token for token in TOKEN.findall(str(value or "").casefold()) if token not in STOPWORDS}


def _stable(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def load_ad_catalog():
    """Read the app's SQLite catalogue without creating or mutating its DB."""
    db_path = Path(DB_NAME)
    if db_path.exists():
        uri = f"file:{quote(db_path.resolve().as_posix(), safe='/:')}?mode=ro"
        try:
            with sqlite3.connect(uri, uri=True) as conn:
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if "ads" in tables:
                    rows = conn.execute("SELECT ad_name, description, category, mode FROM ads ORDER BY ad_name").fetchall()
                    if rows:
                        return pd.DataFrame(rows, columns=["ad_name", "description", "category", "mode"]), f"sqlite:{db_path.name}"
        except sqlite3.Error as exc:
            raise RuntimeError(f"Could not read the configured ad database read-only: {exc}") from exc
    ads = pd.read_csv(AD_CSV).fillna("")
    return ads, "backend/datasets/ads_dataset.csv (SQLite catalogue unavailable)"


def _video_records(path=VIDEO_DATA):
    frame = pd.read_csv(path, sep="\t", on_bad_lines="skip").fillna("")
    frame.columns = [column.strip().lower() for column in frame.columns]
    for column in ("title", "category_id"):
        if column not in frame:
            raise ValueError(f"Video dataset is missing required column {column!r}")
    records = []
    for row_number, row in frame.iterrows():
        title = str(row["title"]).strip()
        try:
            category_id = int(row["category_id"])
        except (TypeError, ValueError):
            continue
        category = CATEGORY_MAP.get(category_id)
        if not title or not category:
            continue
        source_row = int(row_number) + 2  # header is row 1
        digest = _stable(f"youtube_analytics.csv\0{source_row}\0{category_id}\0{title}")[:16]
        records.append({
            "video_id": f"ytanalytics-{digest}",
            "video_title": title,
            "source_dataset": "backend/datasets/youtube_analytics.csv",
            "source_row": source_row,
            "source_category_id": category_id,
            "source_category": category,
            "source_category_fit": "term_match" if (_tokens(title) & TOPIC_TERMS.get(category, set())) else "unverified",
            "source_channel": str(row.get("channel_title", "")),
            "source_published_at": str(row.get("published_at", "")),
        })
    return records


def _pick_videos(records, count, seed):
    by_category = {}
    for record in records:
        by_category.setdefault(record["source_category_id"], []).append(record)
    picked = []
    for category_id, group in sorted(by_category.items()):
        # Prefer titles whose visible terms support the source category, then specificity.
        group.sort(key=lambda row: (
            row["source_category_fit"] != "term_match",
            -len(_tokens(row["video_title"]) & TOPIC_TERMS.get(row["source_category"], set())),
            -len(_tokens(row["video_title"])),
            _stable(f"{seed}|{row['video_id']}"),
        ))
        picked.append(group[0])
    picked.sort(key=lambda row: _stable(f"{seed}|{row['video_id']}"))
    return picked[:count]


def _candidate_ads(video, ads, per_video, seed):
    title_terms = _tokens(video["video_title"])
    rows = [row for row in ads.to_dict("records") if str(row.get("ad_name", "")).strip() and str(row.get("description", "")).strip()]
    selected = {}
    # Topic-term overlap is a transparent retrieval heuristic, not a relevance label.
    lexical = []
    for row in rows:
        ad_terms = _tokens(f"{row['ad_name']} {row['description']}")
        union = title_terms | ad_terms
        score = len(title_terms & ad_terms) / len(union) if union else 0.0
        if score > 0:
            lexical.append((score, row))
    lexical.sort(key=lambda pair: (-pair[0], _stable(f"{seed}|{video['video_id']}|{pair[1]['ad_name']}")))
    for _, row in lexical[:2]:
        selected[row["ad_name"]] = row

    compatible = ADJACENT_AD_CATEGORIES.get(video["source_category"], set())
    category_candidates = [row for row in rows if str(row.get("category", "")).casefold() in compatible]
    category_candidates.sort(key=lambda row: _stable(f"category|{seed}|{video['video_id']}|{row['ad_name']}"))
    for row in category_candidates:
        if len(selected) >= min(per_video, 4):
            break
        selected.setdefault(row["ad_name"], row)

    # Seeded full-catalogue sampling contributes cross-category and ambiguous alternatives.
    remaining = [row for row in rows if row["ad_name"] not in selected]
    remaining.sort(key=lambda row: _stable(f"catalogue|{seed}|{video['video_id']}|{row['ad_name']}"))
    categories = {}
    for row in remaining:
        categories.setdefault(str(row.get("category", "")), []).append(row)
    category_names = sorted(categories, key=lambda category: _stable(f"category-sample|{seed}|{video['video_id']}|{category}"))
    while len(selected) < min(per_video, len(rows)) and category_names:
        for category in list(category_names):
            if categories[category] and len(selected) < min(per_video, len(rows)):
                row = categories[category].pop(0)
                selected[row["ad_name"]] = row
            if not categories[category]:
                category_names.remove(category)
    return [selected[name] for name in sorted(selected, key=lambda name: _stable(f"packet|{seed}|{video['video_id']}|{name}"))]


def build_labeling_set(video_count=12, ads_per_video=10, seed=20261019, videos_path=VIDEO_DATA, ads=None):
    if video_count < 1 or ads_per_video < 1:
        raise ValueError("video_count and ads_per_video must be positive")
    if ads is None:
        ads, _ = load_ad_catalog()
    records = _pick_videos(_video_records(videos_path), video_count, seed)
    if not records:
        raise ValueError("No source video records available for the labeling packet")
    heldout = {_stable(f"heldout|{seed}|{row['video_id']}") for row in records}
    heldout_ids = set(sorted(heldout)[:max(1, round(len(records) * 0.25))])
    packet = []
    for video in records:
        split = "held_out" if _stable(f"heldout|{seed}|{video['video_id']}") in heldout_ids else "development"
        candidates = _candidate_ads(video, ads, ads_per_video, seed)
        for ad in candidates:
            packet.append({
                **video,
                "split": split,
                "ad_id": str(ad["ad_name"]),  # ad_name is the SQLite ads primary key
                "ad_name": str(ad["ad_name"]),
                "ad_description": str(ad.get("description", "")),
                "ad_category": str(ad.get("category", "")),
                "ad_mode": str(ad.get("mode", "")),
                "judgment_status": "pending",
                "relevance": "",
                "label_notes": "",
            })
    return pd.DataFrame(packet)


def write_labeling_set(packet, output, force=False):
    output = Path(output)
    if output.exists() and not force:
        existing = pd.read_csv(output)
        has_status = "judgment_status" in existing
        has_labels = "relevance" in existing and existing["relevance"].notna().any()
        has_review_state = has_status and existing["judgment_status"].fillna("pending").ne("pending").any()
        if has_labels or has_review_state:
            raise FileExistsError(
                f"Refusing to overwrite human-reviewed labels at {output}; choose a new output path or use --force to discard them."
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    packet.to_csv(output, index=False)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="docs/recommendation-labels.csv")
    parser.add_argument("--videos", type=int, default=12, help="maximum one source video per category")
    parser.add_argument("--ads-per-video", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20261019)
    parser.add_argument("--force", action="store_true", help="overwrite a reviewed packet and discard its labels")
    args = parser.parse_args()
    catalog, source = load_ad_catalog()
    packet = build_labeling_set(args.videos, args.ads_per_video, args.seed, ads=catalog)
    packet["ad_catalog_source"] = source
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    write_labeling_set(packet, output, force=args.force)
    report = {
        "output": str(output), "seed": args.seed, "videos": int(packet.video_id.nunique()),
        "candidate_pairs": len(packet), "ads_per_video": args.ads_per_video,
        "video_categories": sorted(packet.source_category.unique().tolist()),
        "catalog_source": source,
        "labels_created": 0,
        "note": "All relevance labels are blank and pending human judgment.",
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
