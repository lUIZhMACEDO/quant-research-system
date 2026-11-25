"""SQLite persistence layer (schema + idempotent upserts)."""

from quant_research.storage.db import (
    connect,
    count_quality_issues,
    init_schema,
    log_data_quality,
    log_proxy_scores,
    upsert_fundamentals,
    upsert_indicators,
    upsert_macro,
    upsert_prices,
)

__all__ = [
    "connect",
    "count_quality_issues",
    "init_schema",
    "log_data_quality",
    "log_proxy_scores",
    "upsert_fundamentals",
    "upsert_indicators",
    "upsert_macro",
    "upsert_prices",
]
