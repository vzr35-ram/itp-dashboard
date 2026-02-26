"""
dashboard/app.py

Streamlit entry point for the AI Ecosystem Dashboard.

Run locally with:
    streamlit run dashboard/app.py

This file is intentionally minimal for now — it connects to the DB,
runs a basic query, and renders a table. Each dimension (Innovation,
Competition, etc.) will live in its own file under dashboard/pages/
as we build them out.
"""

import streamlit as st
import pandas as pd
from db.connection import get_session, init_db
from db.models import SemanticScholarPaper

# ------------------------------------------------------------------
# Page config — must be the first Streamlit call in the file
# ------------------------------------------------------------------
st.set_page_config(
    page_title="AI Ecosystem Dashboard",
    page_icon="🤖",
    layout="wide",
)

# Ensure tables exist (safe no-op if already created)
init_db()


# ------------------------------------------------------------------
# Data loading — cached so it doesn't re-query on every interaction
# st.cache_data caches for the duration of the session by default.
# Set ttl= to auto-refresh after N seconds if you want live updates.
# ------------------------------------------------------------------

@st.cache_data
def load_papers() -> pd.DataFrame:
    """Loads all Semantic Scholar papers from the DB into a DataFrame."""
    with get_session() as session:
        rows = session.query(SemanticScholarPaper).all()
        return pd.DataFrame([
            {
                "paper_id": r.paper_id,
                "title": r.title,
                "citation_count": r.citation_count,
                "influential_citation_count": r.influential_citation_count,
                "url": r.url,
                "query": r.query,
                "collected_at": r.collected_at,
            }
            for r in rows
        ])


# ------------------------------------------------------------------
# Layout
# ------------------------------------------------------------------

st.title("🤖 AI Ecosystem Dashboard")
st.caption("Tracking AI progress across Innovation, Competition, Adoption, Accessibility, and Economics.")

st.divider()

# -- Semantic Scholar section --
st.header("📄 Recent AI Papers (Semantic Scholar)")

df = load_papers()

if df.empty:
    st.info(
        "No data yet. Run the collector first:\n\n"
        "```bash\npython -m collectors.semantic_scholar\n```"
    )
else:
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Papers", len(df))
    col2.metric("Avg Citations", f"{df['citation_count'].mean():.0f}")
    col3.metric("Collection Days", df["collected_at"].dt.date.nunique())

    st.subheader("Top Papers by Citation Count")
    top = df.sort_values("citation_count", ascending=False).head(20)
    st.dataframe(
        top[["title", "citation_count", "influential_citation_count", "query", "collected_at"]],
        use_container_width=True,
    )

    st.subheader("Citations Over Time")
    daily = (
        df.groupby(df["collected_at"].dt.date)["citation_count"]
        .mean()
        .reset_index()
    )
    daily.columns = ["date", "avg_citation_count"]
    st.line_chart(daily.set_index("date"))
