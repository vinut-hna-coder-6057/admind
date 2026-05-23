from googleapiclient.discovery import build

from backend.config.config import API_KEY

import logging

logger = logging.getLogger(__name__)
# ─────────────────────────────────────────────────────
# EXTRACT VIDEO ID
# ─────────────────────────────────────────────────────

def extract_video_id(url):

    try:

        if "watch?v=" in url:

            return (
                url.split("watch?v=")[1]
                .split("&")[0]
            )

        elif "youtu.be/" in url:

            return (
                url.split("youtu.be/")[1]
                .split("?")[0]
            )

        return None

    except Exception as e:

        logger.exception(
            "Failed to fetch YouTube details"
        )

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

        youtube = build(

            "youtube",

            "v3",

            developerKey=API_KEY
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

    except Exception as e:

        logger.exception(
            "Failed to fetch YouTube details"
        )

        return None