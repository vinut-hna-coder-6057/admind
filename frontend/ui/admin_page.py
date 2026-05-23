import streamlit as st

from backend.database import (
    load_ads
)

from ui.components import (
    page_header
)


def admin_page():

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