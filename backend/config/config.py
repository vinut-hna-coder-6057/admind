import os
from pathlib import Path
import hashlib
import hmac
import sqlite3
from contextlib import closing
from urllib.parse import quote

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


# ─────────────────────────────────────────────────────
# YOUTUBE API
# ─────────────────────────────────────────────────────

API_KEY = os.getenv(
    "YOUTUBE_API_KEY"
)

ADMIND_ENV = os.getenv("ADMIND_ENV", "development").casefold()
STREAMLIT_COOKIE_SECRET = os.getenv("STREAMLIT_SERVER_COOKIE_SECRET", "")


# ─────────────────────────────────────────────────────
# ADMIN PASSWORD
# ─────────────────────────────────────────────────────

ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")

# Dashboard and recommendation use do not require admin credentials.
# ─────────────────────────────────────────────────────
# RANKING WEIGHTS
# ─────────────────────────────────────────────────────

SEMANTIC_WEIGHT = 10

CTR_WEIGHT = 3

FEEDBACK_WEIGHT = 1.5

MODE_WEIGHT = 2

PERSONALIZATION_WEIGHT = 4

DIVERSITY_PENALTY = 4


def verify_admin_password(password):
    """Verify pbkdf2_sha256$iterations$salt_hex$digest_hex credentials."""
    if not ADMIN_PASSWORD_HASH or not isinstance(password, str):
        return False
    try:
        algorithm, iterations_text, salt_hex, expected_hex = ADMIN_PASSWORD_HASH.split("$", 3)
        iterations = int(iterations_text)
        if algorithm != "pbkdf2_sha256" or not 100_000 <= iterations <= 2_000_000:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _valid_admin_password_hash(value):
    try:
        algorithm, iterations_text, salt_hex, digest_hex = value.split("$", 3)
        return (
            algorithm == "pbkdf2_sha256"
            and 100_000 <= int(iterations_text) <= 2_000_000
            and len(bytes.fromhex(salt_hex)) >= 16
            and len(bytes.fromhex(digest_hex)) == hashlib.sha256().digest_size
        )
    except (ValueError, TypeError):
        return False


def validate_production_settings():
    """Reject unsafe implicit development defaults in production mode."""
    if ADMIND_ENV != "production":
        return

    configured_db = os.getenv("DB_NAME", "")
    if not configured_db or configured_db == ":memory:" or not Path(configured_db).is_absolute():
        raise RuntimeError("Production requires an absolute DB_NAME outside the application directory")
    database_path = Path(configured_db).resolve()
    if PROJECT_ROOT == database_path or PROJECT_ROOT in database_path.parents:
        raise RuntimeError("Production DB_NAME must be on persistent storage outside the application directory")
    if not database_path.is_file():
        raise RuntimeError("Production database must be provisioned and seeded before application startup")
    if len(STREAMLIT_COOKIE_SECRET) < 32:
        raise RuntimeError("Production requires STREAMLIT_SERVER_COOKIE_SECRET with at least 32 characters")
    if not _valid_admin_password_hash(ADMIN_PASSWORD_HASH):
        raise RuntimeError("Production requires a valid ADMIN_PASSWORD_HASH; see the setup documentation")

    uri = f"file:{quote(database_path.as_posix(), safe='/:')}?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as conn:
            usable_ads = conn.execute(
                "SELECT COUNT(*) FROM ads WHERE trim(COALESCE(ad_name, '')) <> '' "
                "AND trim(COALESCE(description, '')) <> ''"
            ).fetchone()[0]
        if usable_ads < 1:
            raise RuntimeError("Production database needs at least one usable catalogue ad")
    except sqlite3.Error as exc:
        raise RuntimeError("Production database is not readable or has not been initialized") from exc
