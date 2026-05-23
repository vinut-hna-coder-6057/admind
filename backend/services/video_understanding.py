from collections import Counter

from backend.services.vector_store import (
    vector_store
)

from backend.services.category_map import (
    CATEGORY_MAP
)


# ─────────────────────────────────────────────────────
# DETECT VIDEO CATEGORY
# ─────────────────────────────────────────────────────

def detect_video_category(
    title
):

    # get top-k semantic matches
    results = vector_store.search(

        title,

        k=5
    )

    categories = []

    scores = []

    for row, score in results:

        cat_id = int(
            row["category_id"]
        )

        category = (
            CATEGORY_MAP.get(
                cat_id,
                "general"
            )
        )

        categories.append(
            category
        )

        scores.append(
            score
        )

    # ─────────────────────────────────
    # FALLBACK SAFETY
    # ─────────────────────────────────

    if not categories:

        return (
            "general",
            0.0
        )

    # ─────────────────────────────────
    # MAJORITY VOTING
    # ─────────────────────────────────

    final_category = (
        Counter(categories)
        .most_common(1)[0][0]
    )

    # ─────────────────────────────────
    # AVERAGE CONFIDENCE
    # ─────────────────────────────────

    avg_score = (
        sum(scores)
        / len(scores)
    )

    return (
        final_category,
        avg_score
    )