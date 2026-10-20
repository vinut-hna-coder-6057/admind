import logging
import uuid

import streamlit as st

from backend.config.config import API_KEY
from backend.database import (
    get_feedback_stats,
    save_feedback,
    track_shown,
)
from backend.services.analytics_service import get_ab
from backend.services.recommender_engine import recommender_engine
from backend.services.youtube_api import extract_video_id, get_video_details, choose_video_title
from ui.charts import chart_ab
from ui.components import kpi_row, page_header, section_tag, pipeline_visual

logger = logging.getLogger(__name__)
MODES = ["study", "focus", "casual", "silent"]
AUDIENCES = ["student", "developer", "gamer", "professional", "casual"]


def feedback_vote_value(vote):
    return {"Relevant": "positive", "Irrelevant": "negative"}.get(vote)


def dashboard_page():
    page_header("Watch & Match", "Paste a YouTube URL and request a relevant ad match")
    analytics = get_ab()
    feedback_stats = get_feedback_stats()
    shown = int(analytics["shown"].sum()) if not analytics.empty else 0
    clicked = int(analytics["clicked"].sum()) if not analytics.empty else 0
    ctr = clicked / shown * 100 if shown else 0
    kpi_row(shown, clicked, ctr, feedback_stats.get("positive", 0), feedback_stats.get("negative", 0))
    st.caption("Impression = a recommendation displayed. CTR = recorded destination clicks ÷ impressions. Feedback is reported separately.")

    if "admind_session_id" not in st.session_state:
        st.session_state.admind_session_id = str(uuid.uuid4())
    if "recommendation" not in st.session_state:
        st.session_state.recommendation = None

    with st.form("recommendation_request"):
        section_tag("YouTube Video")
        url = st.text_input("YouTube URL", placeholder="https://youtube.com/watch?v=...")
        title_override = st.text_input(
            "Video title (optional)",
            help="Enter or correct the title if YouTube metadata is unavailable. A title is required to match ads.",
            max_chars=500,
        )
        mode = st.selectbox("Viewing mode", MODES, index=MODES.index(st.session_state.get("mode", "study")))
        audience = st.selectbox("Audience", AUDIENCES)
        submitted = st.form_submit_button("Get recommendation", type="primary")

    if submitted:
        video_id = extract_video_id(url)
        if not video_id:
            st.session_state.recommendation = None
            st.error("Enter a valid YouTube video URL.")
        else:
            details = None
            if not title_override.strip() and API_KEY:
                with st.spinner("Fetching video details…"):
                    details = get_video_details(url)
                if not details:
                    st.info("Video details were unavailable; a descriptive title is needed to recommend an ad.")
            elif not title_override.strip():
                st.info("YouTube API key is not set; a descriptive video title is needed to recommend an ad.")
            title = choose_video_title(title_override, details)
            request_id = str(uuid.uuid4())
            try:
                with st.spinner("Matching relevant ads…"):
                    result = recommender_engine.rank(
                        title, mode, audience,
                        session_id=st.session_state.admind_session_id,
                    )
                if not result:
                    st.session_state.recommendation = None
                    st.warning("No ad could be matched from the available video title and ad descriptions.")
                else:
                    result.update({"title": title, "video_id": video_id, "mode": mode, "request_id": request_id})
                    st.session_state.recommendation = result
                    track_shown(result["ad_name"], request_id=request_id)
            except Exception as exc:
                logger.error("Recommendation request failed; exception_type=%s", type(exc).__name__)
                st.session_state.recommendation = None
                st.error("Recommendations are temporarily unavailable. Please try again.")

    result = st.session_state.recommendation
    if not result:
        st.info("Submit a YouTube URL to see the video category and ad recommendation.")
        return

    st.subheader(result["title"])
    st.video(f"https://www.youtube.com/watch?v={result['video_id']}")
    st.caption(f"Viewing mode: {result['mode']}")
    pipeline_visual(result["title"], result["video_type"], result["ad_name"])
    st.markdown("### Recommended ad")
    st.success(result["ad_name"])
    score_label = "Title-to-offering cosine" if result.get("relevance_basis") == "cosine" else "Lexical overlap fallback"
    st.caption(f"{score_label}: {result['relevance_score']:.3f} (raw ranking signal; not a probability)")
    if result.get("explanation"):
        st.caption("Ranking signals: " + ", ".join(result["explanation"]))
    if result.get("mode_conflict"):
        st.warning(result["mode_message"])

    feedback_key = f"feedback_submitted_{result['request_id']}"
    with st.form(f"feedback_{result['request_id']}"):
        vote = st.radio("Was this ad relevant?", ["Select one", "Relevant", "Irrelevant"], index=0, horizontal=True)
        feedback_submitted = st.form_submit_button("Submit feedback")
    if feedback_submitted:
        if st.session_state.get(feedback_key):
            st.info("Feedback for this recommendation was already recorded.")
        elif feedback_vote_value(vote) is None:
            st.warning("Choose Relevant or Irrelevant before submitting feedback.")
        else:
            save_feedback(result["ad_name"], feedback_vote_value(vote))
            st.session_state[feedback_key] = True
            st.success("Feedback saved. Feedback does not count as a click.")
    st.markdown("### Aggregate ad performance")
    chart_ab(get_ab())
