import streamlit as st


# ─────────────────────────────────────────────────────
# YOUTUBE LOGO
# ─────────────────────────────────────────────────────

YT_LOGO_HTML = """
<div style="
display:flex;
align-items:center;
gap:10px;
padding:1.3rem 0 0.3rem 0;
">

    <div style="
    width:34px;
    height:24px;
    background:#FF0000;
    border-radius:6px;
    display:flex;
    align-items:center;
    justify-content:center;
    ">

        <div style="
        width:0;
        height:0;
        border-top:6px solid transparent;
        border-bottom:6px solid transparent;
        border-left:10px solid white;
        margin-left:2px;
        ">
        </div>

    </div>

    <div>

        <div style="
        font-family:'Bebas Neue',sans-serif;
        font-size:1.35rem;
        color:#fff;
        letter-spacing:0.07em;
        line-height:1.1;
        ">
            AdMind
        </div>

        <div style="
        font-family:'JetBrains Mono',monospace;
        font-size:0.55rem;
        color:#666;
        letter-spacing:0.12em;
        text-transform:uppercase;
        ">
            Smart Ad Engine
        </div>

    </div>

</div>
"""


# ─────────────────────────────────────────────────────
# PAGE HEADER
# ─────────────────────────────────────────────────────

def page_header(title, sub):

    st.markdown(f"""
    <div style="
      padding-bottom:1rem;
      margin-bottom:1.4rem;
      border-bottom:1px solid #1f1f1f;
    ">

      <h1 style="
        font-family:'Bebas Neue',sans-serif;
        font-size:2.1rem;
        color:#fff;
        letter-spacing:0.05em;
        margin:0 0 3px 0;
      ">
        {title}
      </h1>

      <p style="
        font-family:'Nunito',sans-serif;
        font-size:0.82rem;
        color:#666;
        margin:0;
      ">
        {sub}
      </p>

    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────
# SECTION TAG
# ─────────────────────────────────────────────────────

def section_tag(text):

    st.markdown(f"""
    <div style="
      display:flex;
      align-items:center;
      gap:7px;
      font-family:'JetBrains Mono',monospace;
      font-size:0.63rem;
      letter-spacing:0.14em;
      color:#FF0000;
      text-transform:uppercase;
      margin-bottom:0.55rem;
    ">

      <span style="
        display:inline-block;
        width:14px;
        height:1px;
        background:#FF0000;
      "></span>

      {text}

    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────
# KPI ROW
# ─────────────────────────────────────────────────────

def kpi_row(shown, ctr, pos, neg):

    pos = int(pos or 0)

    neg = int(neg or 0)

    shown = int(shown or 0)

    total = pos + neg

    sent = (
        round(pos / total * 100, 1)
        if total
        else 0
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Impressions",
        f"{shown:,}"
    )

    c2.metric(
        "CTR",
        f"{ctr:.1f}%"
    )

    c3.metric(
        "👍 Positive",
        pos
    )

    c4.metric(
        "Sentiment",
        f"{sent}%"
    )


# ─────────────────────────────────────────────────────
# AD CARD
# ─────────────────────────────────────────────────────

def ad_card_3d(
    ad_name,
    category,
    tag="Best Match"
):

    st.success(
        f"⚡ {tag}"
    )

    st.markdown(f"""
### {ad_name}

Category: `{category}`
""")
def pipeline_visual(
    video_title,
    detected,
    ad_name
):

    c1, c2, c3 = st.columns(3)

    with c1:

        st.markdown("##### VIDEO")

        st.info(video_title)

    with c2:

        st.markdown("##### AI TAG")

        st.warning(detected)

    with c3:

        st.markdown("##### MATCHED AD")

        st.success(ad_name)
# ─────────────────────────────────────────────────────
# PLOTLYbackend.config
# ─────────────────────────────────────────────────────

def plotly_cfg():

    return dict(
        plot_bgcolor="rgba(0,0,0,0)",

        paper_bgcolor="rgba(0,0,0,0)",

        font=dict(
            family="JetBrains Mono,monospace",
            color="#555",
            size=10
        ),

        margin=dict(
            l=0,
            r=0,
            t=42,
            b=0
        )
    )