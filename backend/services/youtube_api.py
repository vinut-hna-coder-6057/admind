from urllib.parse import parse_qs, urlparse
import re

from backend.config.config import API_KEY

import logging

logger = logging.getLogger(__name__)
# ─────────────────────────────────────────────────────
# EXTRACT VIDEO ID
# ─────────────────────────────────────────────────────

def extract_video_id(url):
    if not isinstance(url, str) or not url.strip() or len(url) > 2048:
        return None
    try:
        parsed = urlparse(url.strip())
        host = (parsed.hostname or "").lower().removeprefix("www.")
        if parsed.scheme not in {"http", "https"}:
            return None
        if host in {"youtube.com", "m.youtube.com", "music.youtube.com"} and parsed.path.startswith("/shorts/"):
            video_id = parsed.path.split("/")[2]
        elif host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
            video_id = parse_qs(parsed.query).get("v", [None])[0]
            if parsed.path not in {"/watch", "/"}:
                return None
        elif host == "youtu.be":
            video_id = parsed.path.strip("/").split("/")[0]
        else:
            return None
        return video_id if video_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) else None
    except (ValueError, IndexError):
        return None


# ─────────────────────────────────────────────────────
# GET VIDEO DETAILS
# ─────────────────────────────────────────────────────

def get_video_details(video_url):

    try:

        video_id = extract_video_id(
            video_url
        )

        if not video_id:

            return None

        if not API_KEY:
            return None

        from googleapiclient.discovery import build
        import httplib2
        youtube = build(

            "youtube",

            "v3",

            developerKey=API_KEY,
            http=httplib2.Http(timeout=5)
        )

        request = youtube.videos().list(

            part="snippet",

            id=video_id
        )

        response = request.execute()


        items = response.get(
            "items",
            []
        )

        if not items:

            return None

        snippet = items[0][
            "snippet"
        ]

        title = snippet.get(
            "title",
            "Untitled Video"
        )

        tags = snippet.get(
            "tags",
            []
        )

        return (

            title,

            tags
        )

    except Exception:

        logger.warning("YouTube video details are unavailable")

        return None


def choose_video_title(title_override, details):
    """Prefer an explicit user correction, then fall back to fetched metadata."""
    override = (title_override or "").strip()
    if override:
        return override
    if details and details[0]:
        return str(details[0]).strip()
    return ""
