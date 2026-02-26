"""
collectors/base.py

Abstract base class for all data collectors.

Every collector in the project inherits from this. It defines:
  - The public interface:  collect()
  - The contract:          fetch() and save() must be implemented
  - Shared infrastructure: retry logic, logging, optional failure hook

To add a new data source:
  1. Create a new file in collectors/
  2. Subclass BaseCollector
  3. Implement fetch() and save()
  4. That's it — retry logic, logging, and error handling come for free.
"""

import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class BaseCollector(ABC):

    # How many times to attempt fetch() before giving up.
    MAX_RETRIES = 3

    # Seconds to wait after the first failure.
    # Doubles on each subsequent failure (exponential backoff):
    #   attempt 1 fails → wait 5s
    #   attempt 2 fails → wait 10s
    #   attempt 3 fails → give up
    RETRY_DELAY_SECONDS = 5

    def __init__(self, db_session):
        """
        db_session: a live SQLAlchemy session, injected from outside.

        We inject it rather than creating it here so that:
          1. Tests can pass a mock session without touching the real DB.
          2. The caller controls transaction scope — one session can span
             multiple collectors if needed.
        """
        self.db = db_session
        self.collected_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # ------------------------------------------------------------------
    # PUBLIC INTERFACE
    # Called by GitHub Actions workflow scripts and by tests.
    # ------------------------------------------------------------------

    def collect(self) -> bool:
        """
        The single public entrypoint. Call this to run a full collection.

        Orchestrates fetch() → validate() → save() with retry logic.
        Returns True on success, False if all retries are exhausted.
        """
        collector_name = self.__class__.__name__
        logger.info(f"[{collector_name}] Starting collection...")

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                data = self.fetch()
                self.validate(data)
                self.save(data)
                logger.info(
                    f"[{collector_name}] Success on attempt {attempt}. "
                    f"Collected {self._count(data)} records."
                )
                return True

            except Exception as e:
                wait = self.RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                if attempt < self.MAX_RETRIES:
                    logger.warning(
                        f"[{collector_name}] Attempt {attempt} failed: {e}. "
                        f"Retrying in {wait}s..."
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        f"[{collector_name}] All {self.MAX_RETRIES} attempts failed. "
                        f"Last error: {e}"
                    )
                    self.on_failure(e)
                    return False

    # ------------------------------------------------------------------
    # ABSTRACT METHODS
    # Subclasses MUST implement both of these.
    # ------------------------------------------------------------------

    @abstractmethod
    def fetch(self) -> dict | list:
        """
        Call the external API and return the raw data.

        Rules:
          - Do NOT write to the database here.
          - Raise an exception on any failure (HTTP error, timeout, etc.)
            so that collect() can catch it and retry.
          - Return whatever structure makes sense for this source —
            save() will receive exactly what fetch() returns.
        """
        ...

    @abstractmethod
    def save(self, data: dict | list) -> None:
        """
        Persist the fetched data to the database.

        Rules:
          - Receives the return value of fetch().
          - Should upsert where possible (skip rows that already exist)
            so re-running the collector is always safe.
          - Do NOT call self.db.commit() here — the caller (collect())
            owns the transaction. The context manager in get_session()
            commits on clean exit.
        """
        ...

    # ------------------------------------------------------------------
    # OPTIONAL HOOKS
    # Subclasses CAN override these for custom behavior.
    # ------------------------------------------------------------------

    def validate(self, data: dict | list) -> None:
        """
        Sanity-check the fetched data before saving.
        Default: just ensures data is not empty/None.
        Override to add source-specific checks (e.g. required fields).
        """
        if not data:
            raise ValueError(
                f"[{self.__class__.__name__}] fetch() returned empty data."
            )

    def on_failure(self, error: Exception) -> None:
        """
        Called when all retries are exhausted.
        Default: no-op (the error is already logged by collect()).
        Override to send an alert, write a failure record, etc.
        """
        pass

    # ------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _count(data: dict | list) -> int:
        """Returns a sensible record count for logging."""
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            # Common pattern: {"data": [...], "total": N}
            return len(data.get("data", data))
        return 1
