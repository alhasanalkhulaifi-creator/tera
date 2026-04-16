"""High-resolution request-phase timing helpers (opt-in logging)."""

from __future__ import annotations

import os
import time

from infrastructure.logger import logger

PERF_LOG = os.getenv("TERA_PERF_LOG", "").lower() in ("1", "true", "yes")


def log_cards_buy(*, redis_ms: float, db_ms: float, total_ms: float, path: str = "cards.buy") -> None:
    if not PERF_LOG:
        return
    logger.info(
        "perf %s redis_ms=%.3f db_ms=%.3f total_ms=%.3f",
        path,
        redis_ms,
        db_ms,
        total_ms,
    )


def monotonic_ms() -> float:
    return time.perf_counter_ns() / 1_000_000.0
