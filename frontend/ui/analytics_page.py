import streamlit as st

from backend.services.analytics_service import (
    get_ab
)

from ui.charts import (
    chart_ab,
    chart_ctr,
    chart_donut
)

from backend.database import (
    get_feedback_stats
)

from ui.components import (
    page_header,
    kpi_row
)


# ─────────────────────────────────────────────────────
# ANALYTICS PAGE
# ─────────────────────────────────────────────────────

def analytics_page():

    page_header(
        "Analytics",
        "Ad performance and feedback insights"
    )

    # analytics
    ab = get_ab()

    # feedback stats
    fb = get_feedback_stats()

    pos = int(
        fb.get("positive") or 0
    )

    neg = int(
        fb.get("negative") or 0
    )

    # totals
    shown = (
        int(ab["shown"].sum())
        if not ab.empty
        else 0
    )

    clicked = (
        int(ab["clicked"].sum())
        if not ab.empty
        else 0
    )

    ctr = (
        clicked / shown * 100
        if shown > 0
        else 0
    )

    # ─────────────────────────────────────
    # KPI ROW
    # ─────────────────────────────────────

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

    # ─────────────────────────────────────
    # TABS
    # ─────────────────────────────────────

    t1, t2, t3 = st.tabs([
        "Performance",
        "CTR",
        "Feedback"
    ])

    # ─────────────────────────────────────
    # PERFORMANCE
    # ─────────────────────────────────────

    with t1:

        chart_ab(ab)

    # ─────────────────────────────────────
    # CTR
    # ─────────────────────────────────────

    with t2:

        chart_ctr(ab)

    # ─────────────────────────────────────
    # FEEDBACK
    # ─────────────────────────────────────

    with t3:

        c1, c2 = st.columns(2)

        with c1:

            chart_donut(
                pos,
                neg
            )

        with c2:

            st.metric(
                "Positive 👍",
                pos
            )

            st.metric(
                "Negative 👎",
                neg
            )

            st.metric(
                "Total Feedback",
                pos + neg
            )

    # ─────────────────────────────────────
    # RAW DATA
    # ─────────────────────────────────────

    st.markdown("### Raw Analytics",unsafe_allow_html=True)

    if not ab.empty:

        
       st.dataframe(
    ab,
    width="stretch",
    hide_index=True
)

    else:

        st.info(
            "No analytics available yet."
        )