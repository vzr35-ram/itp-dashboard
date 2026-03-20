"""
dashboard/app.py

Streamlit entry point for the AI Ecosystem Dashboard.

"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from db.connection import get_session, init_db
from db.models import SemanticScholarPaper

# ------------------------------------------------------------------
# Page config
# ------------------------------------------------------------------
st.set_page_config(
    page_title="AI Ecosystem Dashboard",
    page_icon="🤖",
    layout="wide",
)

# ------------------------------------------------------------------
# Custom CSS
# ------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Syne', sans-serif; }

.stApp {
    background-color: #0a0a0f;
    background-image:
        radial-gradient(ellipse 80% 50% at 20% 10%, rgba(99, 60, 255, 0.12) 0%, transparent 60%),
        radial-gradient(ellipse 60% 40% at 80% 80%, rgba(0, 210, 190, 0.08) 0%, transparent 55%);
}

#MainMenu, footer, header {visibility: hidden;}
.block-container { padding-top: 2rem; padding-bottom: 2rem; }

.hero { padding: 3rem 0 2rem 0; border-bottom: 1px solid rgba(255,255,255,0.07); margin-bottom: 2rem; }
.hero-eyebrow { font-family: 'Space Mono', monospace; font-size: 0.7rem; letter-spacing: 0.25em; text-transform: uppercase; color: #00d2be; margin-bottom: 0.75rem; }
.hero-title { font-family: 'Syne', sans-serif; font-size: 3.2rem; font-weight: 800; line-height: 1.05; color: #ffffff; margin: 0 0 0.75rem 0; }
.hero-title span { background: linear-gradient(135deg, #633cff 0%, #00d2be 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.hero-sub { font-size: 1rem; color: rgba(255,255,255,0.45); font-weight: 400; max-width: 520px; }

.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }
.kpi-card { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 1.4rem 1.5rem; position: relative; overflow: hidden; }
.kpi-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, #633cff, #00d2be); opacity: 0.7; }
.kpi-label { font-family: 'Space Mono', monospace; font-size: 0.65rem; letter-spacing: 0.18em; text-transform: uppercase; color: rgba(255,255,255,0.4); margin-bottom: 0.5rem; }
.kpi-value { font-size: 2.2rem; font-weight: 800; color: #ffffff; line-height: 1; }
.kpi-sub { font-size: 0.75rem; color: rgba(255,255,255,0.3); margin-top: 0.35rem; }

.section-header { display: flex; align-items: center; gap: 0.75rem; margin: 2.5rem 0 1.25rem 0; }
.section-tag { font-family: 'Space Mono', monospace; font-size: 0.65rem; letter-spacing: 0.2em; text-transform: uppercase; color: #00d2be; background: rgba(0, 210, 190, 0.1); padding: 0.3rem 0.7rem; border-radius: 4px; border: 1px solid rgba(0, 210, 190, 0.2); }
.section-title { font-size: 1.35rem; font-weight: 700; color: #ffffff; margin: 0; }

.fancy-divider { height: 1px; background: linear-gradient(90deg, transparent, rgba(99,60,255,0.4), rgba(0,210,190,0.4), transparent); margin: 2rem 0; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# DB
# ------------------------------------------------------------------
init_db()

@st.cache_data
def load_papers() -> pd.DataFrame:
    with get_session() as session:
        rows = session.query(SemanticScholarPaper).all()
        import json
        records = []
        for r in rows:
            authors_raw = r.authors if r.authors else "[]"
            try:
                authors_list = json.loads(authors_raw) if isinstance(authors_raw, str) else authors_raw
                author_names = ", ".join([a.get("name", "") for a in authors_list[:3]])
                if len(authors_list) > 3:
                    author_names += f" +{len(authors_list)-3} more"
            except Exception:
                author_names = ""
            records.append({
                "paper_id": r.paper_id,
                "title": r.title,
                "authors": author_names,
                "citation_count": r.citation_count,
                "influential_citation_count": r.influential_citation_count,
                "url": r.url,
                "query": r.query,
                "collected_at": r.collected_at,
            })
        return pd.DataFrame(records)

df = load_papers()

# ------------------------------------------------------------------
# Hero
# ------------------------------------------------------------------
st.markdown("""
<div class="hero">
    <div class="hero-eyebrow">Live Research Intelligence</div>
    <h1 class="hero-title">AI <span>Ecosystem</span><br>Dashboard</h1>
    <p class="hero-sub">Tracking innovation across large language models and computer vision — updated daily.</p>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# KPI Cards
# ------------------------------------------------------------------
if not df.empty:
    llm_df = df[df["query"] == "large language models"]
    cv_df  = df[df["query"] == "computer vision transformer"]

    st.markdown(f"""
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-label">Total Papers</div>
            <div class="kpi-value">{len(df):,}</div>
            <div class="kpi-sub">across both topics</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">LLM Papers</div>
            <div class="kpi-value">{len(llm_df):,}</div>
            <div class="kpi-sub">large language models</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">CV Papers</div>
            <div class="kpi-value">{len(cv_df):,}</div>
            <div class="kpi-sub">computer vision transformer</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Avg Citations</div>
            <div class="kpi-value">{df['citation_count'].mean():.0f}</div>
            <div class="kpi-sub">across all papers</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ------------------------------------------------------------------
# Filters
# ------------------------------------------------------------------
st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)

col_f1, col_f2, col_f3 = st.columns([2, 2, 3])
with col_f1:
    topic_filter = st.selectbox(
        "Filter by topic",
        ["All Topics", "large language models", "computer vision transformer"],
        label_visibility="collapsed"
    )
with col_f2:
    sort_by = st.selectbox(
        "Sort by",
        ["citation_count", "influential_citation_count", "collected_at"],
        format_func=lambda x: {"citation_count": "📊 Most Cited", "influential_citation_count": "⭐ Most Influential", "collected_at": "🕐 Most Recent"}[x],
        label_visibility="collapsed"
    )
with col_f3:
    search = st.text_input("Search", placeholder="🔍  Search titles…", label_visibility="collapsed")

filtered = df.copy()
if topic_filter != "All Topics":
    filtered = filtered[filtered["query"] == topic_filter]
if search:
    filtered = filtered[filtered["title"].str.contains(search, case=False, na=False)]
filtered = filtered.sort_values(sort_by, ascending=False)

# ------------------------------------------------------------------
# Table
# ------------------------------------------------------------------
st.markdown("""
<div class="section-header">
    <span class="section-tag">Papers</span>
    <h2 class="section-title">Top Research Papers</h2>
</div>
""", unsafe_allow_html=True)

display_df = filtered[["title", "authors", "citation_count", "influential_citation_count", "query", "collected_at"]].head(50).copy()
display_df.columns = ["Title", "Authors", "Citations", "Influential Citations", "Topic", "Collected"]
display_df["Collected"] = pd.to_datetime(display_df["Collected"]).dt.strftime("%b %d, %Y")

st.dataframe(
    display_df,
    use_container_width=True,
    height=400,
    column_config={
        "Title": st.column_config.TextColumn("Title", width="large"),
        "Authors": st.column_config.TextColumn("Authors", width="medium"),
        "Citations": st.column_config.NumberColumn("Citations", format="%d"),
        "Influential Citations": st.column_config.NumberColumn("Influential", format="%d"),
        "Topic": st.column_config.TextColumn("Topic", width="medium"),
        "Collected": st.column_config.TextColumn("Date", width="small"),
    },
    hide_index=True,
)

# ------------------------------------------------------------------
# Charts
# ------------------------------------------------------------------
st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)

color_map = {
    "large language models": "#633cff",
    "computer vision transformer": "#00d2be",
}

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("""
    <div class="section-header">
        <span class="section-tag">Trend</span>
        <h2 class="section-title">Avg Citations Over Time</h2>
    </div>
    """, unsafe_allow_html=True)

    daily = (
        df.groupby([df["collected_at"].dt.date, "query"])["citation_count"]
        .mean().reset_index()
    )
    daily.columns = ["date", "topic", "avg_citations"]

    fig1 = px.line(daily, x="date", y="avg_citations", color="topic",
                   color_discrete_map=color_map,
                   labels={"avg_citations": "Avg Citations", "date": "", "topic": ""})
    fig1.update_traces(line_width=2.5)
    fig1.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Syne", color="rgba(255,255,255,0.6)", size=11),
        legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="rgba(255,255,255,0.1)",
                    font=dict(size=10), orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)", linecolor="rgba(255,255,255,0.1)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)", linecolor="rgba(255,255,255,0.1)"),
        margin=dict(l=0, r=0, t=30, b=0), height=280,
    )
    st.plotly_chart(fig1, use_container_width=True)

with chart_col2:
    st.markdown("""
    <div class="section-header">
        <span class="section-tag">Distribution</span>
        <h2 class="section-title">Citation Spread by Topic</h2>
    </div>
    """, unsafe_allow_html=True)

    fig2 = px.box(df[df["citation_count"] < 300], x="query", y="citation_count",
                  color="query", color_discrete_map=color_map,
                  labels={"citation_count": "Citations", "query": ""})
    fig2.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Syne", color="rgba(255,255,255,0.6)", size=11),
        showlegend=False,
        xaxis=dict(gridcolor="rgba(255,255,255,0.05)", linecolor="rgba(255,255,255,0.1)",
                   ticktext=["LLMs", "Computer Vision"],
                   tickvals=["large language models", "computer vision transformer"]),
        yaxis=dict(gridcolor="rgba(255,255,255,0.05)", linecolor="rgba(255,255,255,0.1)"),
        margin=dict(l=0, r=0, t=30, b=0), height=280,
    )
    st.plotly_chart(fig2, use_container_width=True)

# ------------------------------------------------------------------
# Top 15 bar chart
# ------------------------------------------------------------------
st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)
st.markdown("""
<div class="section-header">
    <span class="section-tag">Top 15</span>
    <h2 class="section-title">Most Cited Papers</h2>
</div>
""", unsafe_allow_html=True)

top15 = df.nlargest(15, "citation_count").copy()
top15["short_title"] = top15["title"].str[:55] + "…"
color_seq = [color_map.get(q, "#633cff") for q in top15["query"]]

fig3 = go.Figure(go.Bar(
    x=top15["citation_count"], y=top15["short_title"],
    orientation="h",
    marker=dict(color=color_seq, opacity=0.85),
    text=top15["citation_count"], textposition="outside",
    textfont=dict(color="rgba(255,255,255,0.7)", size=10),
))
fig3.update_layout(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Syne", color="rgba(255,255,255,0.6)", size=10),
    xaxis=dict(gridcolor="rgba(255,255,255,0.05)", linecolor="rgba(255,255,255,0.1)"),
    yaxis=dict(gridcolor="rgba(0,0,0,0)", linecolor="rgba(255,255,255,0.1)", autorange="reversed"),
    margin=dict(l=0, r=60, t=10, b=0), height=460,
)
st.plotly_chart(fig3, use_container_width=True)

# ------------------------------------------------------------------
# Footer
# ------------------------------------------------------------------
st.markdown('<div class="fancy-divider"></div>', unsafe_allow_html=True)
st.markdown("""
<p style="font-family: 'Space Mono', monospace; font-size: 0.65rem; color: rgba(255,255,255,0.2); text-align: center; letter-spacing: 0.1em;">
    DATA SOURCE: SEMANTIC SCHOLAR API &nbsp;·&nbsp; UPDATED DAILY &nbsp;·&nbsp; AI ECOSYSTEM DASHBOARD
</p>
""", unsafe_allow_html=True)
