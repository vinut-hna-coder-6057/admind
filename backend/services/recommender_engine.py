import math
import re
import unicodedata

from backend.database import load_ads, save_history, get_recent_mode_mismatches
from backend.services.embedding_service import embedding_service
from backend.services.video_understanding import detect_video_category


_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
_GENERIC = {"the", "and", "for", "with", "from", "your", "you", "how", "what", "this", "that", "are", "was", "best", "new", "review", "guide", "learn"}


def _text(value):
    if value is None:
        return ""
    try:
        if value != value:  # NaN
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _tokens(value):
    normalized = unicodedata.normalize("NFKC", _text(value)).casefold()
    return {token for token in _TOKEN_RE.findall(normalized) if token not in _GENERIC}


def _cosine(left, right):
    try:
        score = float(embedding_service.similarity(left, right))
        return max(-1.0, min(1.0, score)) if math.isfinite(score) else None
    except Exception:
        return None


def detect_mode_conflict(mode, video_type):
    if mode == "study" and video_type in ["entertainment", "fashion", "food"]:
        return True, "You are watching entertainment content in study mode. Switch to casual mode?"
    return False, ""


class AdRecommenderEngine:
    """Rank ads by video-title to advertised-offering evidence.

    The returned relevance_score is a raw cosine when the local encoder works;
    lexical overlap is a deterministic fallback. Neither is a probability.
    """

    def rank(self, title, mode, user_type, session_id=None):
        video_title = _text(title)
        # YouTube IDs are opaque identifiers, not descriptive video metadata.
        if not _tokens(video_title) or re.fullmatch(r"[A-Za-z0-9_-]{11}", video_title):
            return None

        ads = load_ads()
        if ads is None or ads.empty:
            return None

        try:
            video_type, _ = detect_video_category(video_title)
        except Exception:
            video_type = "general"
        video_type = _text(video_type) or "general"
        title_tokens = _tokens(video_title)

        try:
            title_embedding = embedding_service.encode(video_title)
        except Exception:
            title_embedding = None

        scored = []
        seen_offerings = set()
        for _, row in ads.iterrows():
            name = _text(row.get("ad_name"))
            description = _text(row.get("description"))
            # Missing offering copy is not evidence of relevance.
            if not name or not description:
                continue
            offering = f"{name}. {description}"
            canonical = " ".join(sorted(_tokens(offering)))
            if not canonical or canonical in seen_offerings:
                continue
            seen_offerings.add(canonical)

            overlap = title_tokens & _tokens(offering)
            lexical_score = len(overlap) / max(1, len(title_tokens | _tokens(offering)))
            semantic_score = None
            if title_embedding is not None:
                try:
                    ad_embedding = embedding_service.encode(offering)
                    semantic_score = _cosine(title_embedding, ad_embedding)
                except Exception:
                    semantic_score = None

            # Use one ranking signal consistently. Lexical overlap only breaks
            # semantic ties; on encoder failure it is the safe local fallback.
            score = semantic_score if semantic_score is not None else lexical_score
            if not math.isfinite(float(score)):
                continue
            explanations = []
            if overlap:
                explanations.append("matching terms: " + ", ".join(sorted(overlap)))
            if semantic_score is not None and not overlap:
                explanations.append("title-to-ad-offering semantic match")
            if _text(row.get("category")).casefold() == video_type.casefold():
                explanations.append("same broad category (context only)")

            scored.append({
                "ad_name": name,
                "category": _text(row.get("category")),
                "score": float(score),
                "semantic": semantic_score,
                "lexical": lexical_score,
                "overlap": overlap,
                "explanation": explanations,
            })

        if not scored:
            return None
        # Specific lexical evidence resolves close semantic ties, never overrides
        # a semantic ordering. Stable name ordering makes equal inputs repeatable.
        scored.sort(key=lambda item: (-item["score"], -item["lexical"], item["ad_name"].casefold()))
        best = scored[0]

        # No relevance cutoff is claimed without human labels. Return no ad when
        # the available signals show no positive connection at all.
        if best["score"] <= 0:
            return None

        save_history(video_title, video_type, mode, ad_category=best["category"], session_id=session_id)
        conflict, message = detect_mode_conflict(mode, video_type)
        return {
            "ad_name": best["ad_name"],
            "video_type": video_type,
            "relevance_score": best["semantic"] if best["semantic"] is not None else best["lexical"],
            "relevance_basis": "cosine" if best["semantic"] is not None else "lexical_fallback",
            "ranking_score": best["score"],
            "explanation": best["explanation"],
            "mode_conflict": conflict,
            "mode_message": message,
            "adaptive_popup": get_recent_mode_mismatches(mode, session_id=session_id),
        }


recommender_engine = AdRecommenderEngine()
