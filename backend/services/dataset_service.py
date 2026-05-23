import os
import logging
import pandas as pd


# ─────────────────────────────────────────────────────
# LOGGER
# ─────────────────────────────────────────────────────

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────
# LOAD DATASET
# ─────────────────────────────────────────────────────

def load_youtube_dataset():

    try:

        # backend folder path
        BASE_DIR = os.path.dirname(
            os.path.dirname(__file__)
        )

        # full dataset path
        dataset_path = os.path.join(
            BASE_DIR,
            "datasets",
            "youtube_analytics.csv"
        )

        df = pd.read_csv(

            dataset_path,

            sep="\t",

            encoding="utf-8",

            on_bad_lines="skip"
        )

        logger.info(
            "YouTube dataset loaded successfully."
        )

        return df

    except Exception as e:

        logger.exception(
            "Failed to load YouTube dataset"
        )

        return pd.DataFrame()


# ─────────────────────────────────────────────────────
# CLEAN DATASET
# ─────────────────────────────────────────────────────

def prepare_dataset(df):

    try:

        if df.empty:

            return pd.DataFrame()

        # lowercase column names
        df.columns = [

            c.lower().strip()

            for c in df.columns
        ]

        # useful columns
        keep = [

            "title",

            "category_id",

            "view_count",

            "like_count",

            "comment_count",

            "engagement_rate",

            "duration_seconds"
        ]

        # keep only required columns
        df = df[keep]

        # remove missing rows
        df = df.dropna()

        logger.info(
            "Dataset prepared successfully."
        )

        return df

    except Exception as e:

        logger.exception(
            "Failed to prepare dataset"
        )

        return pd.DataFrame()