import streamlit as st


def load_styles():

    st.markdown("""
<style>
/* ── Variables ── */
:root {
  --yt-red:       #FF0000;
  --yt-red-dark:  #CC0000;
  --yt-red-glow:  rgba(255,0,0,0.18);
  --bg-base:      #0F0F0F;
  --bg-raised:    #161616;
  --bg-card:      #1C1C1C;
  --bg-card2:     #212121;
  --border:       #2a2a2a;
  --border-soft:  #1f1f1f;
  --text-bright:  #FFFFFF;
  --text-body:    #AAAAAA;
  --text-muted:   #555555;
  --text-dim:     #333333;
  --green:        #00E676;
  --orange:       #FF6D00;
  --font-display: 'Bebas Neue', sans-serif;
  --font-body:    'Nunito', sans-serif;
  --font-mono:    'JetBrains Mono', monospace;
}

/* ── Reset ── */
*, *::before, *::after { box-sizing: border-box; }

 html, body, .stApp {
  font-family: var(--font-body) !important;
  background-color: var(--bg-base) !important;
  color: var(--text-body) !important;
}


/* ── Sidebar ── */
section[data-testid="stSidebar"] {
  background: var(--bg-raised) !important;
  border-right: 1px solid var(--border) !important;
  z-index: 10 !important;
}

/* ── Option Menu ── */
.nav-link {
  font-family: var(--font-body) !important;
  font-size: 0.88rem !important;
  font-weight: 600 !important;
  border-radius: 10px !important;
  transition: all 0.2s ease !important;
}

.nav-link-selected {
  background: rgba(255,0,0,0.1) !important;
  color: #FF4444 !important;
  border: 1px solid rgba(255,0,0,0.22) !important;
}

/* ── Text Inputs ── */
.stTextInput > div > div > input,
.stSelectbox > div > div {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  color: var(--text-bright) !important;
  font-family: var(--font-body) !important;
  font-size: 0.9rem !important;
  transition: all 0.2s ease !important;
}

.stTextInput > div > div > input:focus {
  border-color: var(--yt-red) !important;
  box-shadow: 0 0 0 3px var(--yt-red-glow) !important;
}

.stTextInput > label,
.stSelectbox > label {
  font-family: var(--font-mono) !important;
  font-size: 0.68rem !important;
  text-transform: uppercase !important;
  letter-spacing: 0.1em !important;
  color: var(--text-muted) !important;
}

/* ── Buttons ── */
.stButton > button {
  background: var(--yt-red) !important;
  color: #fff !important;
  font-family: var(--font-body) !important;
  font-size: 0.88rem !important;
  font-weight: 800 !important;
  letter-spacing: 0.04em !important;
  border: none !important;
  border-radius: 10px !important;
  padding: 0.6rem 1.6rem !important;
  transition: all 0.2s cubic-bezier(.34,1.56,.64,1) !important;
}

.stButton > button:hover {
  background: var(--yt-red-dark) !important;
  transform: translateY(-2px) scale(1.02) !important;
  box-shadow: 0 8px 24px rgba(255,0,0,0.35) !important;
}

.stButton > button:active {
  transform: scale(0.97) !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
  background: transparent !important;
  border-bottom: 1px solid var(--border) !important;
  gap: 4px !important;
}

.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  color: var(--text-muted) !important;
  font-family: var(--font-body) !important;
  font-size: 0.8rem !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
  padding: 0.65rem 1.1rem !important;
  transition: all 0.2s ease !important;
}

.stTabs [aria-selected="true"] {
  color: var(--text-bright) !important;
  border-bottom-color: var(--yt-red) !important;
}

/* ── Metric Cards ── */
[data-testid="metric-container"] {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: 14px !important;
  padding: 1.1rem 1.3rem !important;
  position: relative;
  overflow: hidden;
  transition: all 0.25s ease !important;
}

[data-testid="metric-container"]:hover {
  border-color: rgba(255,0,0,0.35) !important;
  transform: translateY(-2px) !important;
  box-shadow: 0 8px 28px rgba(255,0,0,0.1) !important;
}

[data-testid="metric-container"]::before {
  content: '';
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--yt-red), var(--orange), transparent);
}

[data-testid="stMetricLabel"] {
  font-family: var(--font-mono) !important;
  font-size: 0.63rem !important;
  letter-spacing: 0.12em !important;
  color: var(--text-muted) !important;
  text-transform: uppercase !important;
}

[data-testid="stMetricValue"] {
  font-family: var(--font-display) !important;
  font-size: 2rem !important;
  color: var(--text-bright) !important;
  letter-spacing: 0.04em !important;
}

/* ── Layout ── */
.block-container {
  padding-top: 1.2rem !important;
  position: relative;
  z-index: 2;
}

#MainMenu,
footer{
  visibility: hidden !important;
}
</style>
""", unsafe_allow_html=True)