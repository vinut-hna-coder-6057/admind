import re
import logging

import streamlit as st

from googleapiclient.discovery import build

from backend.config.config import (
    API_KEY
)

from backend.database import (
    save_feedback,
    track_clicked,
    track_shown,
    get_feedback_stats
)

from backend.services.analytics_service import (
    get_ab
)

from backend.services.recommender_engine import (
    recommender_engine
)

from ui.charts import (
    chart_ab
)

from ui.components import (
    page_header,
    kpi_row,
    section_tag,
    ad_card_3d,
    pipeline_visual
)


# ─────────────────────────────────────────────────────
# LOGGER
# ─────────────────────────────────────────────────────

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────
# DASHBOARD PAGE
# ─────────────────────────────────────────────────────

def dashboard_page():

    page_header(
        "Watch & Match",
        "Paste a YouTube URL and AdMind will recommend relevant ads"
    )

    # ─────────────────────────────────────
    # ANALYTICS SUMMARY
    # ─────────────────────────────────────

    ab_df = get_ab()

    fb = get_feedback_stats()

    pos = int(
        fb.get("positive") or 0
    )

    neg = int(
        fb.get("negative") or 0
    )

    shown = (
        int(ab_df["shown"].sum())
        if not ab_df.empty
        else 0
    )

    clicked = (
        int(ab_df["clicked"].sum())
        if not ab_df.empty
        else 0
    )

    ctr = (
        clicked / shown * 100
        if shown > 0
        else 0
    )

    kpi_row(
        shown,
        ctr,
        pos,
        neg
    )

    st.markdown(
        '<div style="height:1rem"></div>',
        unsafe_allow_html=True
    )
    if "mode" not in st.session_state:

        st.session_state.mode = "study"
    # ─────────────────────────────────────
    # LAYOUT
    # ─────────────────────────────────────

    left_col, right_col = st.columns(
        [1.1, 1],
        gap="large"
    )

    # ─────────────────────────────────────
    # LEFT PANEL
    # ─────────────────────────────────────

    with left_col:

        section_tag(
            "YouTube Video"
        )

        url = st.text_input(
            "Paste YouTube URL",
            placeholder="https://youtube.com/watch?v=...",
            label_visibility="collapsed"
        )
        mode = st.selectbox(
            "Viewing Mode",
        [
            "study",
            "focus",
            "casual",
            "silent"
        ],
        index=[
            "study",
            "focus",
            "casual",
            "silent"
         ].index(st.session_state.mode)
        )

        user_type = st.selectbox(
            "User Type",
            [
                "student",
                "developer",
                "gamer",
                "professional",
                "casual"
            ]
        )

        # ─────────────────────────────────
        # PROCESS VIDEO
        # ─────────────────────────────────

        if url:

            match = re.search(
                r"(?:v=|\/)([0-9A-Za-z_-]{11})",
                url
            )

            if not match:

                st.error(
                    "Invalid YouTube URL"
                )

                return

            video_id = match.group(1)

            title = "Untitled Video"

            # ─────────────────────────────
            # FETCH VIDEO TITLE
            # ─────────────────────────────

            if API_KEY:

                with st.spinner(
                    "Fetching video details..."
                ):

                    try:

                        youtube = build(
                            "youtube",
                            "v3",
                            developerKey=API_KEY
                        )

                        response = (
                            youtube.videos()
                            .list(
                                part="snippet",
                                id=video_id
                            )
                            .execute()
                        )

                        if response.get("items"):

                            title = response[
                                "items"
                            ][0]["snippet"][
                                "title"
                            ]

                    except Exception as e:

                        logger.exception(
                            "Failed to fetch YouTube details"
                        )

                        st.error(
                            "Failed to fetch YouTube video details."
                        )

            # ─────────────────────────────
            # VIDEO PLAYER
            # ─────────────────────────────

            st.video(
                f"https://www.youtube.com/watch?v={video_id}"
            )

            st.subheader(title)

            st.caption(
                f"MODE · {mode.upper()}"
            )

            # ─────────────────────────────
            # RECOMMENDATION ENGINE
            # ─────────────────────────────

            with st.spinner(
                "Matching relevant ads..."
            ):

                result = recommender_engine.rank(
                    title,
                    mode,
                    user_type
                )

            if not result:

                st.error(
                    "Unable to generate recommendation."
                )

                return

            ad_name = result["ad_name"]

            video_type = result["video_type"]

            confidence = result["confidence"]

            conflict = result["mode_conflict"]

            conflict_msg = result["mode_message"]

            adaptive_popup = result.get(
                "adaptive_popup",
                False
            )

            # ─────────────────────────────
            # ADAPTIVE MODE SWITCH
            # ─────────────────────────────

            if adaptive_popup:

                st.warning(
                    "You have been watching entertainment "
                    "content frequently in study mode. "
                    "Would you like to switch to casual mode?"
                )

                if st.button(
                    "Switch to Casual Mode"
                ):

                    st.session_state.mode = "casual"

                    st.success(
                            "Mode switched to casual."
                        )

                    st.rerun()

            # ─────────────────────────────
            # TRACK IMPRESSION
            # ─────────────────────────────

            track_key = f"tracked_{ad_name}"

            if track_key not in st.session_state:

                track_shown(
                    ad_name
                )

                st.session_state[
                    track_key
                ] = True

            # ─────────────────────────────
            # PIPELINE VISUAL
            # ─────────────────────────────

            pipeline_visual(
                title,
                video_type,
                ad_name
            )

            # ─────────────────────────────
            # MODE CONFLICT
            # ─────────────────────────────

            if conflict:

                st.warning(
                    conflict_msg
                )

    # ─────────────────────────────────────
    # RIGHT PANEL
    # ─────────────────────────────────────

    with right_col:

        if url:

            section_tag(
                "Matched Ad"
            )

            # ─────────────────────────────
            # AD CARD
            # ─────────────────────────────

            ad_card_3d(
                ad_name,
                video_type,
                tag=f"{confidence}% Match"
            )

            # ─────────────────────────────
            # EXPLAINABILITY
            # ─────────────────────────────

            st.info(
                f"Recommended because you are "
                f"watching '{video_type}' "
                f"content in '{mode}' mode."
            )

            # ─────────────────────────────
            # TABS
            # ─────────────────────────────

            tab1, tab2 = st.tabs([
                "Feedback",
                "Performance"
            ])

            # ─────────────────────────────
            # FEEDBACK TAB
            # ─────────────────────────────

            with tab1:

                feedback_ui = st.radio(
                    "Was this ad relevant?",
                    [
                        "👍 Relevant",
                        "👎 Irrelevant"
                    ],
                    horizontal=True
                )

                feedback = (
                    "positive"
                    if "Relevant" in feedback_ui
                    else "negative"
                )

                if st.button(
                    "Submit Feedback",
                    use_container_width=True
                ):

                    save_feedback(
                        ad_name,
                        feedback
                    )

                    if feedback == "positive":

                        track_clicked(
                            ad_name
                        )

                        st.success(
                            "Feedback saved successfully."
                        )

                    else:

                        st.warning(
                            "Feedback noted."
                        )

            # ─────────────────────────────
            # PERFORMANCE TAB
            # ─────────────────────────────

            with tab2:

                chart_ab(
                    get_ab()
                )

        else:

            st.info(
                "Paste a YouTube URL to start recommendation."
            )