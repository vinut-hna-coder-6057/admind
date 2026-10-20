"""Compare frozen content baseline and current ranker on human-labeled pairs.

Input CSV columns: video_id, video_title, ad_name, relevance (0..3).
The generated packet also carries source details, split, ad_id, and judgment_status.
"""
import argparse
import json
import math
import re
import unicodedata
from pathlib import Path

import pandas as pd

from backend.services.embedding_service import embedding_service
from backend.services.video_understanding import detect_video_category


GENERIC = {"the", "and", "for", "with", "from", "your", "you", "how", "what", "this", "that", "are", "was", "best", "new", "review", "guide", "learn"}
TOKEN = re.compile(r"[a-z0-9]{2,}")


def _tokens(text):
    text = unicodedata.normalize("NFKC", str(text or "")).casefold()
    return {term for term in TOKEN.findall(text) if term not in GENERIC}


def ranking_metrics(items, k=5):
    """NDCG/Precision/Recall/MRR; ineligible candidate rows count as not shown."""
    eligible = [item for item in items if item.get("eligible", True)]
    ordered = sorted(eligible, key=lambda item: (-item["score"], -item.get("tie_breaker", 0.0), item["ad_name"].casefold()))
    top = ordered[:k]
    dcg = sum((2 ** item["relevance"] - 1) / math.log2(rank + 1) for rank, item in enumerate(top, 1))
    ideal = sorted((item["relevance"] for item in items), reverse=True)[:k]
    idcg = sum((2 ** rel - 1) / math.log2(rank + 1) for rank, rel in enumerate(ideal, 1))
    relevant_total = sum(item["relevance"] >= 2 for item in items)
    precision = sum(item["relevance"] >= 2 for item in top) / k
    recall = sum(item["relevance"] >= 2 for item in top) / relevant_total if relevant_total else 0.0
    first_useful = next((rank for rank, item in enumerate(ordered, 1) if item["relevance"] >= 2), None)
    return {"ndcg_at_k": dcg / idcg if idcg else 0.0, "precision_at_k": precision,
            "recall_at_k": recall, "mrr": 1 / first_useful if first_useful else 0.0}


def _metric_summary(grouped, score_key, k, tie_key=None, eligible_key=None):
    if not grouped:
        return None
    per_video = {}
    for video_id, frame in grouped.items():
        rows = []
        for item in frame.itertuples(index=False):
            rows.append({
                "ad_name": item.ad_name,
                "relevance": int(item.relevance),
                "score": float(getattr(item, score_key)),
                "tie_breaker": float(getattr(item, tie_key)) if tie_key else 0.0,
                "eligible": bool(getattr(item, eligible_key)) if eligible_key else True,
            })
        per_video[video_id] = ranking_metrics(rows, k)
    return {
        "macro": {name: sum(value[name] for value in per_video.values()) / len(per_video) for name in next(iter(per_video.values()))},
        "per_video": per_video,
    }


def _score_rows(labels):
    ads_csv = Path(__file__).resolve().parents[1] / "datasets" / "ads_dataset.csv"
    ads = pd.read_csv(ads_csv).fillna("").set_index("ad_name")
    has_catalog_snapshot = {"ad_description", "ad_category"}.issubset(labels.columns)
    unknown = sorted(set(labels.ad_name) - set(ads.index)) if not has_catalog_snapshot else []
    if unknown:
        raise ValueError(f"Unknown ad_name values in the versioned catalogue: {', '.join(unknown)}")

    labels = labels.copy().reset_index(drop=True)
    labels["baseline_score"] = 0.0
    labels["candidate_score"] = 0.0
    labels["candidate_lexical_tiebreak"] = 0.0
    labels["candidate_eligible"] = True

    for video_id, indexes in labels.groupby("video_id").groups.items():
        title = str(labels.at[indexes[0], "video_title"])
        title_vector = embedding_service.encode(title)
        video_category, _ = detect_video_category(title)
        category_vector = embedding_service.encode(str(video_category))
        title_terms = _tokens(title)
        signatures = set()
        ordered_indexes = sorted(indexes, key=lambda index: str(labels.at[index, "ad_name"]).casefold())
        for index in ordered_indexes:
            name = str(labels.at[index, "ad_name"])
            description = (str(labels.at[index, "ad_description"]) if "ad_description" in labels
                           else str(ads.at[name, "description"]))
            category = (str(labels.at[index, "ad_category"]) if "ad_category" in labels
                        else str(ads.at[name, "category"]))
            baseline = max(
                embedding_service.similarity(title_vector, embedding_service.encode(description)),
                embedding_service.similarity(category_vector, embedding_service.encode(category)),
            )
            offering = f"{name}. {description}"
            candidate = embedding_service.similarity(title_vector, embedding_service.encode(offering))
            ad_terms = _tokens(offering)
            union = title_terms | ad_terms
            lexical = len(title_terms & ad_terms) / len(union) if union else 0.0
            signature = " ".join(sorted(ad_terms))
            labels.at[index, "baseline_score"] = float(baseline)
            labels.at[index, "candidate_score"] = float(candidate)
            labels.at[index, "candidate_lexical_tiebreak"] = lexical
            # Match current live duplicate suppression (catalogue primary-key order).
            if not description.strip() or not signature or signature in signatures:
                labels.at[index, "candidate_eligible"] = False
            else:
                signatures.add(signature)
        if labels.loc[indexes, "candidate_score"].max() <= 0:
            labels.loc[indexes, "candidate_eligible"] = False
    return labels


def _examples(scored, k, worse_only=False):
    result = []
    for video_id, rows in scored.groupby("video_id"):
        baseline_items = [{"ad_name": row.ad_name, "relevance": int(row.relevance), "score": row.baseline_score} for row in rows.itertuples()]
        candidate_items = [{"ad_name": row.ad_name, "relevance": int(row.relevance), "score": row.candidate_score,
                            "tie_breaker": row.candidate_lexical_tiebreak, "eligible": bool(row.candidate_eligible)}
                           for row in rows.itertuples()]
        base = ranking_metrics(baseline_items, k)
        candidate = ranking_metrics(candidate_items, k)
        if worse_only and candidate["ndcg_at_k"] >= base["ndcg_at_k"]:
            continue
        top = sorted((row for row in rows.itertuples() if row.candidate_eligible),
                     key=lambda row: (-row.candidate_score, -row.candidate_lexical_tiebreak, row.ad_name.casefold()))
        if top:
            first = top[0]
            result.append({
                "video_id": str(video_id), "video_title": str(first.video_title),
                "top_ad_name": str(first.ad_name), "relevance": int(first.relevance),
                "interpretation": {0: "irrelevant", 1: "weak/incidental", 2: "relevant", 3: "highly relevant/useful"}[int(first.relevance)],
                f"candidate_ndcg_at_{k}": candidate["ndcg_at_k"], f"baseline_ndcg_at_{k}": base["ndcg_at_k"],
            })
    return result


def _complete_queries(labels):
    if "judgment_status" not in labels:
        status = labels["relevance"].notna().map({True: "rated", False: "pending"})
        labels = labels.copy()
        labels["judgment_status"] = status
    allowed = {"pending", "rated", "insufficient_information"}
    invalid = sorted(set(labels.judgment_status.fillna("pending")) - allowed)
    if invalid:
        raise ValueError(f"Invalid judgment_status values: {invalid}")
    relevance = pd.to_numeric(labels.relevance, errors="coerce")
    if ((labels.judgment_status == "rated") & relevance.isna()).any():
        raise ValueError("Rated rows must have a relevance label.")
    if ((labels.judgment_status != "rated") & relevance.notna()).any():
        raise ValueError("Only rated rows may have a relevance label.")
    if ((labels.judgment_status == "rated") & ~relevance.between(0, 3)).any():
        raise ValueError("Relevance labels must be integer values from 0 through 3.")
    if ((labels.judgment_status == "rated") & (relevance % 1 != 0)).any():
        raise ValueError("Relevance labels must be integers from 0 through 3.")
    labels = labels.copy()
    labels["relevance"] = relevance
    complete, excluded = [], []
    for video_id, frame in labels.groupby("video_id"):
        if (frame.judgment_status == "rated").all():
            complete.append(video_id)
        else:
            excluded.append({
                "video_id": str(video_id), "split": str(frame.split.iloc[0]) if "split" in frame else "all",
                "pending_pairs": int((frame.judgment_status == "pending").sum()),
                "insufficient_information_pairs": int((frame.judgment_status == "insufficient_information").sum()),
            })
    return labels[labels.video_id.isin(complete)], excluded


def evaluate(labels_path, output_path, k=5):
    labels = pd.read_csv(labels_path)
    required = {"video_id", "video_title", "ad_name", "relevance"}
    if not required.issubset(labels.columns):
        raise ValueError(f"Labels require columns: {', '.join(sorted(required))}")
    if labels.empty:
        raise ValueError("No video-ad pairs found in label file.")
    if labels[["video_id", "video_title", "ad_name"]].isna().any().any():
        raise ValueError("video_id, video_title, and ad_name cannot be blank.")
    if labels.duplicated(["video_id", "ad_name"]).any():
        raise ValueError("Duplicate video_id/ad_name pairs found.")
    if (labels.groupby("video_id").video_title.nunique() != 1).any():
        raise ValueError("Each video_id must have one consistent video_title.")
    if "split" not in labels:
        labels["split"] = "all"
    if not set(labels.split.dropna().unique()).issubset({"development", "held_out", "all"}):
        raise ValueError("split must be development, held_out, or all.")

    complete, excluded = _complete_queries(labels)
    rated_values = pd.to_numeric(labels.loc[labels.get("judgment_status", pd.Series("rated", index=labels.index)) == "rated", "relevance"], errors="coerce").dropna()
    relevance_distribution = {str(value): int((rated_values == value).sum()) for value in range(4)}
    base_report = {
        "status": "awaiting_labels" if complete.empty else "evaluated",
        "candidate_packet_videos": int(labels.video_id.nunique()),
        "candidate_packet_pairs": len(labels),
        "rated_pairs": int((labels.judgment_status == "rated").sum()) if "judgment_status" in labels else int(labels.relevance.notna().sum()),
        "pending_pairs": int((labels.judgment_status.fillna("pending") == "pending").sum()) if "judgment_status" in labels else int(labels.relevance.isna().sum()),
        "insufficient_information_pairs": int((labels.judgment_status == "insufficient_information").sum()) if "judgment_status" in labels else 0,
        "complete_labeled_videos": int(complete.video_id.nunique()),
        "excluded_incomplete_videos": excluded,
        "k": k,
        "label_scale": "0 irrelevant; 1 weak/incidental; 2 relevant; 3 highly relevant and useful",
        "relevance_distribution": relevance_distribution,
        "metrics": None,
        "top_candidate_examples": [],
        "candidate_worse_than_baseline_examples": [],
        "limitations": [
            "The content baseline is max(title-description cosine, inferred-category-ad-category cosine); it excludes historical production mode, CTR, feedback, and session signals.",
            "The candidate replays title-to-offering cosine, lexical tie-breaks, and duplicate suppression on judged candidates; it does not claim intent understanding.",
            "Metrics use fully judged candidate sets only. Recall is relative to the packet candidates, not every possible ad.",
            "The selected sample is small and the held-out split is diagnostic, not statistically conclusive.",
        ],
    }
    if not complete.empty:
        complete = _score_rows(complete)
        base_report["metrics"] = {}
        base_report["relevance_distribution_by_split"] = {}
        for split in sorted(complete.split.unique()):
            frame = complete[complete.split == split]
            grouped = {key: group for key, group in frame.groupby("video_id")}
            split_counts = frame.relevance.value_counts().to_dict()
            base_report["relevance_distribution_by_split"][str(split)] = {
                str(value): int(split_counts.get(value, 0)) for value in range(4)
            }
            base_report["metrics"][split] = {
                "videos": int(frame.video_id.nunique()), "labeled_pairs": len(frame),
                "baseline": _metric_summary(grouped, "baseline_score", k),
                "candidate": _metric_summary(grouped, "candidate_score", k, "candidate_lexical_tiebreak", "candidate_eligible"),
            }
        held = complete[complete.split == "held_out"]
        if not held.empty:
            base_report["top_candidate_examples"] = _examples(held, k)[:20]
            base_report["candidate_worse_than_baseline_examples"] = _examples(held, k, worse_only=True)[:20]
        scored_path = Path(output_path).with_name(Path(output_path).stem + "-scored-pairs.csv")
        scored_path.parent.mkdir(parents=True, exist_ok=True)
        complete.to_csv(scored_path, index=False)
        base_report["scored_pairs_file"] = str(scored_path)
    else:
        base_report["note"] = "No fully judged videos: quality metrics and human-labeled failure examples are not available. No labels were inferred."

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(base_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return base_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", required=True, help="Human-labeled packet CSV")
    parser.add_argument("--output", default="artifacts/recommendation-evaluation.json")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    if args.k < 1:
        parser.error("--k must be positive")
    print(json.dumps(evaluate(args.labels, args.output, args.k), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
