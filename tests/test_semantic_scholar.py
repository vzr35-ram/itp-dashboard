"""
tests/test_semantic_scholar.py

Unit tests for SemanticScholarCollector.

Philosophy:
  - We NEVER call the real API in tests. All HTTP is mocked.
  - We use an in-memory SQLite DB (not dashboard.db) so tests are
    isolated and leave no state behind.
  - Tests are organized around the three methods we care about:
    fetch(), validate(), and save().

Run with:
    pytest tests/test_semantic_scholar.py -v
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.connection import Base
from db.models import SemanticScholarPaper
from collectors.semantic_scholar import SemanticScholarCollector


# ------------------------------------------------------------------
# Fixtures — shared setup used across multiple tests
# ------------------------------------------------------------------

@pytest.fixture
def in_memory_session():
    """
    Creates a fresh in-memory SQLite database for each test.

    'In-memory' means the DB exists only in RAM for the duration of
    the test — it's created and destroyed automatically. No files
    written to disk, no cleanup needed.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)          # create all tables
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)            # clean slate for next test


@pytest.fixture
def collector(in_memory_session):
    """Returns a SemanticScholarCollector wired to the in-memory DB."""
    return SemanticScholarCollector(db_session=in_memory_session)


@pytest.fixture
def sample_api_response():
    """
    A realistic mock of what the Semantic Scholar API returns.
    Matches the actual response shape so tests reflect real behavior.
    """
    return {
        "total": 2,
        "offset": 0,
        "next": 2,
        "data": [
            {
                "paperId": "abc123",
                "title": "Attention Is All You Need",
                "authors": [
                    {"authorId": "1", "name": "Ashish Vaswani"},
                    {"authorId": "2", "name": "Noam Shazeer"},
                ],
                "citationCount": 95000,
                "influentialCitationCount": 12000,
                "url": "https://www.semanticscholar.org/paper/abc123",
            },
            {
                "paperId": "def456",
                "title": "BERT: Pre-training of Deep Bidirectional Transformers",
                "authors": [
                    {"authorId": "3", "name": "Jacob Devlin"},
                ],
                "citationCount": 60000,
                "influentialCitationCount": 8000,
                "url": "https://www.semanticscholar.org/paper/def456",
            },
        ],
    }


# ------------------------------------------------------------------
# fetch() tests
# ------------------------------------------------------------------

class TestFetch:

    def test_fetch_returns_list_of_papers(self, collector, sample_api_response):
        """Happy path: API returns data, fetch() returns a flat list."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status.return_value = None

        with patch("collectors.semantic_scholar.requests.get", return_value=mock_response):
            with patch.dict("os.environ", {"SEMANTIC_SCHOLAR_API_KEY": "test-key"}):
                result = collector.fetch()

        # One response per query in QUERIES (2 queries × 2 papers = 4 total)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_fetch_tags_papers_with_query(self, collector, sample_api_response):
        """Each paper should be tagged with the query that found it."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status.return_value = None

        with patch("collectors.semantic_scholar.requests.get", return_value=mock_response):
            with patch.dict("os.environ", {"SEMANTIC_SCHOLAR_API_KEY": "test-key"}):
                result = collector.fetch()

        assert all("_query" in paper for paper in result)

    def test_fetch_raises_on_http_error(self, collector):
        """
        If the API returns a 4xx/5xx, fetch() should raise so that
        BaseCollector's retry logic can catch it.
        """
        import requests as req

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = req.HTTPError("429 Too Many Requests")

        with patch("collectors.semantic_scholar.requests.get", return_value=mock_response):
            with patch.dict("os.environ", {"SEMANTIC_SCHOLAR_API_KEY": "test-key"}):
                with pytest.raises(req.HTTPError):
                    collector.fetch()

    def test_fetch_sends_api_key_header(self, collector, sample_api_response):
        """The x-api-key header must be present on every request."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status.return_value = None

        with patch("collectors.semantic_scholar.requests.get", return_value=mock_response) as mock_get:
            with patch.dict("os.environ", {"SEMANTIC_SCHOLAR_API_KEY": "test-key-123"}):
                collector.fetch()

        call_kwargs = mock_get.call_args_list[0].kwargs
        assert call_kwargs["headers"]["x-api-key"] == "test-key-123"

    def test_fetch_raises_without_api_key(self, collector):
        """fetch() should raise EnvironmentError if the API key is not set."""
        with patch.dict("os.environ", {}, clear=True):
            # Ensure the key is definitely absent
            os.environ.pop("SEMANTIC_SCHOLAR_API_KEY", None)
            with pytest.raises(EnvironmentError, match="SEMANTIC_SCHOLAR_API_KEY"):
                collector.fetch()


# ------------------------------------------------------------------
# validate() tests
# ------------------------------------------------------------------

class TestValidate:

    def test_validate_passes_on_valid_data(self, collector):
        """Non-empty list with paperId and title should pass silently."""
        data = [{"paperId": "abc", "title": "Test Paper"}]
        collector.validate(data)  # should not raise

    def test_validate_raises_on_empty_list(self, collector):
        """Empty list should raise ValueError (from BaseCollector)."""
        with pytest.raises(ValueError):
            collector.validate([])

    def test_validate_warns_on_missing_fields(self, collector, caplog):
        """Papers missing paperId or title should trigger a warning, not a crash."""
        import logging
        data = [{"paperId": None, "title": None}]
        with caplog.at_level(logging.WARNING):
            collector.validate(data)
        assert "missing paperId or title" in caplog.text


# ------------------------------------------------------------------
# save() tests
# ------------------------------------------------------------------

class TestSave:

    def test_save_inserts_new_papers(self, collector, in_memory_session):
        """New papers should be written to the database."""
        data = [
            {
                "paperId": "abc123",
                "title": "Attention Is All You Need",
                "authors": [{"authorId": "1", "name": "Vaswani"}],
                "citationCount": 95000,
                "influentialCitationCount": 12000,
                "url": "https://semanticscholar.org/abc",
                "_query": "large language models",
            }
        ]
        collector.save(data)
        in_memory_session.commit()

        rows = in_memory_session.query(SemanticScholarPaper).all()
        assert len(rows) == 1
        assert rows[0].paper_id == "abc123"
        assert rows[0].citation_count == 95000

    def test_save_skips_duplicate_same_day(self, collector, in_memory_session):
        """
        Calling save() twice with the same paper on the same day
        should result in only one row — not two.
        """
        data = [
            {
                "paperId": "abc123",
                "title": "Attention Is All You Need",
                "authors": [],
                "citationCount": 95000,
                "influentialCitationCount": 12000,
                "url": "https://semanticscholar.org/abc",
                "_query": "large language models",
            }
        ]
        collector.save(data)
        in_memory_session.commit()

        collector.save(data)  # second call — same paper, same day
        in_memory_session.commit()

        rows = in_memory_session.query(SemanticScholarPaper).all()
        assert len(rows) == 1  # still only one row

    def test_save_skips_papers_without_paper_id(self, collector, in_memory_session):
        """Papers with no paperId should be silently skipped."""
        data = [{"paperId": None, "title": "Ghost Paper", "_query": "test"}]
        collector.save(data)
        in_memory_session.commit()

        rows = in_memory_session.query(SemanticScholarPaper).all()
        assert len(rows) == 0

    def test_save_stores_authors_as_json(self, collector, in_memory_session):
        """Authors list should be stored and retrievable as a Python list."""
        authors = [{"authorId": "1", "name": "Alice"}, {"authorId": "2", "name": "Bob"}]
        data = [
            {
                "paperId": "xyz789",
                "title": "Test Paper",
                "authors": authors,
                "citationCount": 10,
                "influentialCitationCount": 1,
                "url": "https://example.com",
                "_query": "test",
            }
        ]
        collector.save(data)
        in_memory_session.commit()

        row = in_memory_session.query(SemanticScholarPaper).first()
        assert isinstance(row.authors, list)
        assert row.authors[0]["name"] == "Alice"


# ------------------------------------------------------------------
# collect() integration test (mocked end-to-end)
# ------------------------------------------------------------------

class TestCollect:

    def test_collect_returns_true_on_success(self, collector, sample_api_response):
        """collect() should return True when the full pipeline succeeds."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status.return_value = None

        with patch("collectors.semantic_scholar.requests.get", return_value=mock_response):
            with patch.dict("os.environ", {"SEMANTIC_SCHOLAR_API_KEY": "test-key"}):
                result = collector.collect()

        assert result is True

    def test_collect_returns_false_after_all_retries_fail(self, collector):
        """collect() should return False (not raise) when all retries are exhausted."""
        import requests as req

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = req.HTTPError("500 Server Error")

        with patch("collectors.semantic_scholar.requests.get", return_value=mock_response):
            with patch("collectors.base.time.sleep"):  # skip actual waiting in tests
                with patch.dict("os.environ", {"SEMANTIC_SCHOLAR_API_KEY": "test-key"}):
                    result = collector.collect()

        assert result is False
