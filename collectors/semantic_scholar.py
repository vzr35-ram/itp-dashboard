"""
collectors/semantic_scholar.py

Collects recent AI/ML papers from the Semantic Scholar Academic Graph API.

API docs:  https://api.semanticscholar.org/graph/v1
Rate limits:
  - Authenticated (x-api-key header): 1 req/sec dedicated per key.
  - Requires SEMANTIC_SCHOLAR_API_KEY environment variable.
    Locally: set in .env. In GitHub Actions: set as a repository Secret.

Run directly:
    python -m collectors.semantic_scholar
"""

import os
import logging
import time
import requests
from datetime import datetime, date

from collectors.base import BaseCollector
from db.models import SemanticScholarPaper

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

# Fields we ask the API to return.
# Requesting only what we need keeps response size small and fast.
FIELDS = "title,citationCount,influentialCitationCount,url,authors"

# The searches we want to run each collection cycle.
# Each entry is a (query, year_range) tuple.
# Keeping queries here as a constant makes it easy to add more later.
QUERIES = [
    ("large language models", "2025-2026"),
    ("computer vision transformer", "2025-2026"),
]

# Max results per query. API hard cap is 100 for /paper/search.
RESULTS_PER_QUERY = 100

# Respect the 1 req/sec rate limit for authenticated requests.
# Add a small buffer to be safe.
REQUEST_DELAY_SECONDS = 1.1


class SemanticScholarCollector(BaseCollector):
    """
    Fetches recent papers from Semantic Scholar and stores them in SQLite.

    fetch()  → calls the API for each query in QUERIES, returns flat list
    save()   → upserts each paper into semantic_scholar_papers table
    """

    def fetch(self) -> list[dict]:
        """
        Calls the Semantic Scholar /paper/search endpoint for each query
        in QUERIES. Returns a flat list of paper dicts.

        Raises requests.HTTPError on a bad response so BaseCollector
        can catch it and retry.
        """
        api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "SEMANTIC_SCHOLAR_API_KEY is not set. "
                "Add it to your .env file locally, or as a GitHub Actions Secret."
            )
        headers = {"x-api-key": api_key}

        all_papers = []

        for query, year in QUERIES:
            logger.info(f"Fetching query='{query}' year='{year}'...")

            params = {
                "query": query,
                "year": year,
                "fields": FIELDS,
                "limit": RESULTS_PER_QUERY,
            }

            response = requests.get(
                BASE_URL,
                params=params,
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()  # → triggers BaseCollector retry on 4xx/5xx

            payload = response.json()
            papers = payload.get("data", [])

            # Tag each paper with the query it came from before returning.
            # This gets stored in the DB so we know which search surface
            # each paper came from.
            for paper in papers:
                paper["_query"] = query

            all_papers.extend(papers)
            logger.info(f"  Got {len(papers)} papers for '{query}'.")

            # Small pause between queries to be a considerate API consumer.
            time.sleep(REQUEST_DELAY_SECONDS)

        return all_papers

    def save(self, data: list[dict]) -> None:
        """
        Upserts papers into the database.

        "Upsert" here means: insert if this (paper_id, today's date)
        combination doesn't already exist. This makes the collector
        safe to re-run on the same day without creating duplicate rows.
        """
        today = date.today()
        inserted = 0
        skipped = 0

        for raw in data:
            paper_id = raw.get("paperId")
            if not paper_id:
                skipped += 1
                continue

            # Check if we already collected this paper today.
            already_exists = (
                self.db.query(SemanticScholarPaper)
                .filter(
                    SemanticScholarPaper.paper_id == paper_id,
                    # Cast collected_at to date for comparison
                    SemanticScholarPaper.collected_at >= datetime.combine(today, datetime.min.time()),
                    SemanticScholarPaper.collected_at < datetime.combine(today, datetime.max.time()),
                )
                .first()
            )

            if already_exists:
                skipped += 1
                continue

            record = SemanticScholarPaper(
                paper_id=paper_id,
                title=raw.get("title"),
                authors=raw.get("authors"),           # list of {authorId, name}
                citation_count=raw.get("citationCount"),
                influential_citation_count=raw.get("influentialCitationCount"),
                url=raw.get("url"),
                query=raw.get("_query"),
                collected_at=self.collected_at,
            )
            self.db.add(record)
            inserted += 1

        logger.info(f"save() complete: {inserted} inserted, {skipped} skipped.")

    def validate(self, data: list[dict]) -> None:
        """
        Extends BaseCollector's default validation with a field check.
        Warns (but doesn't fail) if papers are missing expected fields.
        """
        super().validate(data)  # checks data is not empty

        missing_fields = [
            p for p in data
            if not p.get("paperId") or not p.get("title")
        ]
        if missing_fields:
            logger.warning(
                f"{len(missing_fields)} papers missing paperId or title. "
                f"They will be skipped in save()."
            )


# ------------------------------------------------------------------
# Entrypoint — called by GitHub Actions:
#   python -m collectors.semantic_scholar
# ------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from db.connection import get_session, init_db

    # Ensure the table exists before trying to write to it.
    init_db()

    with get_session() as session:
        collector = SemanticScholarCollector(db_session=session)
        success = collector.collect()

    exit(0 if success else 1)
