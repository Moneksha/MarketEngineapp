"""
Candle Store — Durable in-process store for completed NIFTY OHLCV candles.

Architecture choice: Option B (persist candles, compute EMA from stored history)
  - EMA is deterministic: same candles → same EMA, every time
  - Resilient: if Kite API hiccups mid-session, we still have the full candle history
  - Auditable: every completed candle is retained in memory for the session
  - Replayable: strategy can be re-run on the exact same candle sequence

Design:
  - Candles are keyed by (interval, rounded_timestamp) — upsert is idempotent
  - Only COMPLETED candles are stored (the live "forming" candle is excluded)
  - get_candles() always returns candles sorted by time, newest last
  - Thread-safe via a simple dict (asyncio single-threaded event loop)
"""

from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger


class CandleStore:
    """Per-interval in-memory candle repository."""

    def __init__(self):
        # { interval: { timestamp_str: candle_dict } }
        self._store: Dict[str, Dict[str, dict]] = {}
        self._initialized: Dict[str, bool] = {}

    # ── Write ──────────────────────────────────────────────────────────────────

    def upsert_candles(self, interval: str, candles: List[dict]) -> int:
        """
        Bulk-upsert a list of candle dicts into the store.

        Each candle must have at minimum: date, open, high, low, close, volume.
        'date' may be a datetime object or an ISO 8601 string.

        Returns the total number of candles now in the store for this interval.
        """
        if interval not in self._store:
            self._store[interval] = {}

        bucket = self._store[interval]
        for candle in candles:
            key = self._candle_key(candle)
            if key:
                bucket[key] = candle

        count = len(bucket)
        return count

    def mark_initialized(self, interval: str):
        self._initialized[interval] = True

    def is_initialized(self, interval: str) -> bool:
        return self._initialized.get(interval, False)

    # ── Read ───────────────────────────────────────────────────────────────────

    def get_candles(self, interval: str, n: Optional[int] = None) -> List[dict]:
        """
        Return the last N completed candles for the given interval,
        sorted ascending by time (oldest first, newest last — same as Kite).

        If n is None, returns all stored candles.
        """
        bucket = self._store.get(interval, {})
        if not bucket:
            return []

        sorted_candles = sorted(bucket.values(), key=lambda c: c.get("date", ""))
        if n is not None:
            sorted_candles = sorted_candles[-n:]
        return sorted_candles

    def candle_count(self, interval: str) -> int:
        return len(self._store.get(interval, {}))

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _candle_key(candle: dict) -> Optional[str]:
        """
        Create a stable string key from the candle's date field.
        Handles both datetime objects and ISO string formats.
        Only uses the minute component so partial updates are idempotent.
        """
        d = candle.get("date")
        if d is None:
            return None
        if isinstance(d, datetime):
            # Truncate to the minute so forming-candle updates don't pollute
            return d.strftime("%Y-%m-%dT%H:%M")
        # ISO string — truncate to minute
        s = str(d)
        return s[:16]   # "YYYY-MM-DDTHH:MM"


# Module-level singleton
candle_store = CandleStore()
