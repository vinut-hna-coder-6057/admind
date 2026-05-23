import streamlit as st
import plotly.graph_objects as go


def plot_cfg():

    return {
        "paper_bgcolor": "#111111",
        "plot_bgcolor": "#111111",
        "font": {
            "color": "white"
        }
    }


# ─────────────────────────────────────
# BAR CHART
# ─────────────────────────────────────

def chart_ab(df):

    if df.empty:

        st.info(
            "No analytics data yet."
        )

        return

    fig = go.Figure()

    fig.add_bar(
        x=df["ad_name"],
        y=df["shown"],
        name="Shown"
    )

    fig.add_bar(
        x=df["ad_name"],
        y=df["clicked"],
        name="Clicked"
    )

    fig.update_layout(
        title="Ad Performance",
        barmode="group",
        **plot_cfg()
    )

    
    st.plotly_chart(
        fig,
        width="stretch"
    )


# ─────────────────────────────────────
# CTR CHART
# ─────────────────────────────────────

def chart_ctr(df):

    if df.empty:

        st.info(
            "No CTR data available."
        )

        return

    d = df.copy()

    d["ctr"] = d.apply(
        lambda r:
        (
            r["clicked"]
            / r["shown"]
            * 100
        )
        if r["shown"] > 0
        else 0,
        axis=1
    )

    fig = go.Figure()

    fig.add_scatter(
        x=d["ad_name"],
        y=d["ctr"],
        mode="lines+markers"
    )

    fig.update_layout(
        title="CTR Trend",
        **plot_cfg()
    )

    st.plotly_chart(
    fig,
    width="stretch"
)


# ─────────────────────────────────────
# DONUT CHART
# ─────────────────────────────────────

def chart_donut(pos, neg):

    fig = go.Figure(
        data=[
            go.Pie(
                labels=[
                    "Positive",
                    "Negative"
                ],

                values=[
                    pos,
                    neg
                ],

                hole=0.6
            )
        ]
    )

    fig.update_layout(
        title="Feedback Sentiment",
        **plot_cfg()
    )

    
    st.plotly_chart(
    fig,
    width="stretch"
)