import streamlit as st

from backend.database import (
    load_ads
)

from ui.components import (
    page_header
)


def admin_authorized(session_state):
    return bool(session_state.get("admin_logged_in", False))


def admin_page():

    if not admin_authorized(st.session_state):
        st.error("Unauthorized Access")
        return

    page_header(
        "Admin",
        "Manage ads"
    )

    ads = load_ads()

    if ads.empty:

        st.warning(
            "No ads available."
        )

    else:

       st.dataframe(
    ads,
    width="stretch",
    hide_index=True
)
