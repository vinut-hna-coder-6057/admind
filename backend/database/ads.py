import os
import logging
import pandas as pd

from datetime import datetime

from .connection import get_connection


# ─────────────────────────────────────────────────────
# LOGGER
# ─────────────────────────────────────────────────────

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────
# INSERT ADS FROM CSV
# ─────────────────────────────────────────────────────

def insert_ads():

    try:

        # backend folder path
        BASE_DIR = os.path.dirname(
            os.path.dirname(__file__)
        )

        # full csv path
        csv_path = os.path.join(
            BASE_DIR,
            "datasets",
            "ads_dataset.csv"
        )

        ads = pd.read_csv(
            csv_path
        )

        with get_connection() as conn:

            cursor = conn.cursor()

            for _, ad in ads.iterrows():

                cursor.execute("""
INSERT OR IGNORE INTO ads (

    ad_name,
    description,
    category,
    mode,
    created_at

)
VALUES (?, ?, ?, ?, ?)
""", (

    ad["ad_name"],
    ad["description"],
    ad["category"],
    ad["mode"],
    datetime.now().isoformat()

))

            conn.commit()

            logger.info(
                "Ads inserted successfully."
            )

    except Exception as e:

        logger.exception(
            "Failed to insert ads"
        )


# ─────────────────────────────────────────────────────
# LOAD ADS
# ─────────────────────────────────────────────────────

def load_ads():

    with get_connection() as conn:

        try:

            df = pd.read_sql_query(
                "SELECT * FROM ads",
                conn
            )

            if df.empty:

                return pd.DataFrame(
                    columns=[
                        "ad_name",
                        "description",
                        "category",
                        "mode"
                    ]
                )

            df["mode"] = df["mode"].apply(

                lambda x: [

                    m.strip()

                    for m in str(x).split(",")
                ]
            )

            return df

        except Exception as e:

            logger.exception(
                "Failed to load ads"
            )

            return pd.DataFrame()