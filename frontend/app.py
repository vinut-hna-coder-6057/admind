import streamlit as st
import logging
import sys
import os

sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            ".."
        )
    )
)
from backend.services.vector_store import (
    vector_store
)
from streamlit_option_menu import option_menu

from backend.database import (
    init_db,
    insert_ads
)

from ui.styles import load_styles

from ui.dashboard_page import dashboard_page
from ui.analytics_page import analytics_page
from ui.admin_page import admin_page

from backend.config.config import (
    ADMIN_PASSWORD
)
# ─────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────

if "admin_logged_in" not in st.session_state:

    st.session_state.admin_logged_in = False


# ─────────────────────────────────────────────────────
# PAGE.config
# ─────────────────────────────────────────────────────

st.set_page_config(
    page_title="AdMind",
    page_icon="▶️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ─────────────────────────────────────────────────────
# GOOGLE FONTS
# ─────────────────────────────────────────────────────

st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>

<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Nunito:wght@300;400;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────
# LOAD CUSTOM STYLES
# ─────────────────────────────────────────────────────

load_styles()


# ─────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────

with st.sidebar:

    # LOGO
    st.markdown(
        """
        <h2 style='color:white;margin-bottom:0'>
        ▶️ AdMind
        </h2>

        <p style='color:#666;font-size:12px'>
        Smart Ad Engine
        </p>
        """,
        unsafe_allow_html=True
    )

    st.markdown("---")

    # MENU OPTIONS
    menu_options = [
        "Dashboard",
        "Analytics"
    ]

    menu_icons = [
        "house",
        "bar-chart"
    ]

    # SHOW ADMIN ONLY AFTER LOGIN
    if st.session_state.admin_logged_in:

        menu_options.append("Admin")

        menu_icons.append("shield-lock")

    # SIDEBAR MENU
    selected = option_menu(

        menu_title=None,

        options=menu_options,

        icons=menu_icons,

        default_index=0
    )

    st.markdown("---")

    # ─────────────────────────────────────────────
    # ADMIN LOGIN
    # ─────────────────────────────────────────────

    if not st.session_state.admin_logged_in:

        with st.expander("Admin Login"):

            password = st.text_input(
                "Enter Admin Password",
                type="password"
            )

            if st.button("Login"):

                if password == ADMIN_PASSWORD:

                    st.session_state.admin_logged_in = True

                    st.success(
                        "Admin login successful"
                    )

                    st.rerun()

                else:

                    st.error(
                        "Invalid password"
                    )

    else:

        st.success("Admin Logged In")

        if st.button("Logout"):

            st.session_state.admin_logged_in = False

            st.rerun()


# ─────────────────────────────────────────────────────
#database INIT
# ─────────────────────────────────────────────────────

init_db()
insert_ads()

# ─────────────────────────────────────────────────────
# ROUTING
# ─────────────────────────────────────────────────────

if selected == "Dashboard":

    dashboard_page()

elif selected == "Analytics":

    analytics_page()

elif selected == "Admin":

    if st.session_state.admin_logged_in:

        admin_page()

    else:

        st.error(
            "Unauthorized Access"
        )