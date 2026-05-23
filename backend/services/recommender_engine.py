from backend.database import (
    load_ads,
    get_feedback_score,
    save_history,
    get_ctr_scores
)
from backend.database import (
    get_recent_ads
)
from backend.services.embedding_service import (
    embedding_service
)
from backend.services.video_understanding import (
    detect_video_category
)
from backend.config.config import (
    SEMANTIC_WEIGHT,
    CTR_WEIGHT,
    FEEDBACK_WEIGHT,
    MODE_WEIGHT,
    PERSONALIZATION_WEIGHT,
    DIVERSITY_PENALTY
)
from backend.database import (
    get_recent_mode_mismatches
)
# ─────────────────────────────────────────────────────
# MODE CONFLICT DETECTION
# ─────────────────────────────────────────────────────

def detect_mode_conflict(
    mode,
    video_type
):

    if (
        mode == "study"
        and video_type in [
            "entertainment",
            "fashion",
            "food"
        ]
    ):

        return (
            True,
            "You are watching entertainment "
            "content in study mode. "
            "Switch to casual mode?"
        )

    return False, ""


# ─────────────────────────────────────────────────────
# RECOMMENDER ENGINE
# ─────────────────────────────────────────────────────
class AdRecommenderEngine:

    def rank(
        self,
        title,
        mode,
        user_type
    ):

        # ─────────────────────────────────────
        # LOAD ADS
        # ─────────────────────────────────────

        ads = load_ads()

        if ads.empty:

            return None

        # ─────────────────────────────────────
        # DETECT VIDEO CATEGORY
        # ─────────────────────────────────────

        video_type, semantic_confidence = (
            detect_video_category(
                title
            )
        )

        # ─────────────────────────────────────
        # FEEDBACK SCORES
        # ─────────────────────────────────────

        feedback_scores = (
            get_feedback_score()
        )

        # ─────────────────────────────────────
        # CTR SCORES
        # ─────────────────────────────────────

        ctr_scores = (
            get_ctr_scores()
        )
        recent_ads = (
        get_recent_ads()
        )

        scored = []

        # ─────────────────────────────────────
        # RANK ADS
        # ─────────────────────────────────────
        title_embedding = embedding_service.encode(title)

        video_type_embedding = embedding_service.encode(video_type)
        for _, row in ads.iterrows():

            # ─────────────────────────────
            # TITLE ↔ DESCRIPTION SIMILARITY
            # ─────────────────────────────

            description_embedding = embedding_service.encode(
                row["description"]
            )

            description_similarity = (
                embedding_service.similarity(
                title_embedding,
                description_embedding
                )
            )

            # ─────────────────────────────
            # CATEGORY ↔ CATEGORY SIMILARITY
            # ─────────────────────────────

            category_embedding = embedding_service.encode(
                row["category"]
            )

            category_similarity = (
                embedding_service.similarity(
                video_type_embedding,
                category_embedding
                )
            )
            # ─────────────────────────────
            # FINAL SEMANTIC SCORE
            # ─────────────────────────────

            semantic_score = max(

                description_similarity,

                category_similarity
            )

            # base score
            score = semantic_score * SEMANTIC_WEIGHT

            # ─────────────────────────────
            # MODE MATCH
            # ─────────────────────────────

            if mode in row["mode"]:

                score += MODE_WEIGHT

            # ─────────────────────────────
            # USER PERSONALIZATION
            # ─────────────────────────────

            if user_type == "student":

                if row["category"] in [
                    "education",
                    "programming",
                    "devices"
                ]:

                    score += PERSONALIZATION_WEIGHT

            elif user_type == "developer":

                if row["category"] in [
                    "programming",
                    "devices",
                    "technology"
                ]:

                    score += PERSONALIZATION_WEIGHT

            elif user_type == "gamer":

                if row["category"] in [
                    "gaming",
                    "entertainment",
                    "devices"
                ]:

                    score += PERSONALIZATION_WEIGHT

            elif user_type == "professional":

                if row["category"] in [
                    "finance",
                    "devices",
                    "productivity"
                ]:

                    score += PERSONALIZATION_WEIGHT

            elif user_type == "casual":

                if row["category"] in [
                    "fashion",
                    "food",
                    "entertainment"
                ]:

                    score += PERSONALIZATION_WEIGHT
            # ─────────────────────────────
            # DIVERSITY CONTROL
            # ─────────────────────────────

            if row["category"] in recent_ads:

                score -= DIVERSITY_PENALTY
            # ─────────────────────────────
            # FEEDBACK LEARNING
            # ─────────────────────────────

            score += (

                feedback_scores.get(
                    row["ad_name"],
                    0
                ) * FEEDBACK_WEIGHT
            )

            # ─────────────────────────────
            # CTR OPTIMIZATION
            # ─────────────────────────────

            score += (

                ctr_scores.get(
                    row["ad_name"],
                    0
                ) * CTR_WEIGHT
            )

            scored.append(

                (
                    row,
                    score,
                    semantic_score
                )
            )

        # ─────────────────────────────────────
        # SORT ADS
        # ─────────────────────────────────────

        scored.sort(

            key=lambda x: x[1],

            reverse=True
        )

        best = scored[0]

        best_ad = best[0]

        # ─────────────────────────────────────
        # CONFIDENCE SCORE
        # ─────────────────────────────────────

        confidence = min(

            99,

            int(semantic_confidence * 100)
        )

        # ─────────────────────────────────────
        # SAVE HISTORY
        # ─────────────────────────────────────
        save_history(

            title,

            video_type,

            mode
        )

        # ─────────────────────────────────────
        # MODE CONFLICT
        # ─────────────────────────────────────

        conflict, message = (

            detect_mode_conflict(

                mode,

                video_type
            )
        )
        adaptive_popup = (
        get_recent_mode_mismatches(mode)
        )
        # ─────────────────────────────────────
        # FINAL RESPONSE
        # ─────────────────────────────────────

        return {

            "ad_name":
                best_ad["ad_name"],

            "video_type":
                video_type,

            "confidence":
                confidence,

            "mode_conflict":
                conflict,

            "mode_message":
                message,
            "adaptive_popup":
              adaptive_popup
        }


# ─────────────────────────────────────────────────────
# GLOBAL INSTANCE
# ─────────────────────────────────────────────────────

recommender_engine = (
    AdRecommenderEngine()
)