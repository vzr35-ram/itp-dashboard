"""
db/models.py

ORM table definitions. Each class = one database table.

Design notes:
- Every table has a collected_at timestamp so we can track when each
  snapshot was taken. This is what makes time series analysis possible.
- paper_id is the Semantic Scholar stable identifier — we use it as the
  natural key for upsert logic (skip if already exists).
- authors is stored as JSON — a list of {authorId, name} dicts. Storing
  it flat avoids needing a separate authors table for now.
"""

from datetime import datetime
from sqlalchemy import Integer, String, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from db.connection import Base


class SemanticScholarPaper(Base):
    """
    One row per paper per collection run.

    Why not one row per paper total? Because citation counts change over
    time — that's one of the metrics we want to track. Storing a new
    snapshot each collection run lets us plot citationCount over time
    for the same paper.

    The unique constraint on (paper_id, collected_at date) prevents
    duplicate rows if the workflow runs twice in one day.
    """
    __tablename__ = "semantic_scholar_papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Semantic Scholar's stable paper identifier (e.g. "649def34f8be52c8b66281af98ae884c09aef38b")
    paper_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    title: Mapped[str] = mapped_column(String, nullable=True)

    # List of {authorId: str, name: str} dicts
    authors: Mapped[list] = mapped_column(JSON, nullable=True)

    citation_count: Mapped[int] = mapped_column(Integer, nullable=True)
    influential_citation_count: Mapped[int] = mapped_column(Integer, nullable=True)

    # The Semantic Scholar URL for the paper
    url: Mapped[str] = mapped_column(String, nullable=True)

    # The query used to fetch this paper — lets us run multiple queries
    # and know which results came from which search.
    query: Mapped[str] = mapped_column(String, nullable=True)

    # UTC timestamp of when this row was inserted.
    # This is the backbone of all time series analysis.
    collected_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Prevent inserting the same paper twice on the same calendar day.
    # Allows re-running the collector safely without duplicating rows.
    __table_args__ = (
        UniqueConstraint("paper_id", "collected_at", name="uq_paper_collected"),
    )

    def __repr__(self) -> str:
        return (
            f"<SemanticScholarPaper "
            f"paper_id={self.paper_id!r} "
            f"citations={self.citation_count} "
            f"collected_at={self.collected_at.date()}>"
        )
