import os

from dotenv import load_dotenv


load_dotenv()


# ─────────────────────────────────────────────────────
# YOUTUBE API
# ─────────────────────────────────────────────────────

API_KEY = os.getenv(
    "YOUTUBE_API_KEY"
)


# ─────────────────────────────────────────────────────
# ADMIN PASSWORD
# ─────────────────────────────────────────────────────

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD"
)

if not ADMIN_PASSWORD:

    raise ValueError(

        "ADMIN_PASSWORD is missing in .env file"
    )
# ─────────────────────────────────────────────────────
# RANKING WEIGHTS
# ─────────────────────────────────────────────────────

SEMANTIC_WEIGHT = 10

CTR_WEIGHT = 3

FEEDBACK_WEIGHT = 1.5

MODE_WEIGHT = 2

PERSONALIZATION_WEIGHT = 4

DIVERSITY_PENALTY = 4