"""Data-quality checks run on every fetched OHLCV series before it is stored.

Each check returns issue codes that land in the ``data_quality`` table. A series
with issues is still stored (except when there is no data at all); the codes are
there so a bad feed is visible instead of silently skewing indicators.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

STALE_AFTER_DAYS = 3


def check_ohlcv(df: pd.DataFrame | None, today: dt.date, stale_after_days: int = STALE_AFTER_DAYS) -> list[str]:
    """Return a list of issue codes for one ticker's OHLCV frame (empty list = clean).

    Codes:
      ``no_ohlcv``            nothing came back
      ``stale_YYYY-MM-DD``    last bar older than ``stale_after_days`` calendar days
      ``duplicate_dates``     the same date appears more than once
      ``nonpositive_close``   a close at or below zero
      ``high_below_low``      a bar whose high is under its low
      ``missing_values``      NaN in open/high/low/close
    """
    if df is None or df.empty:
        return ["no_ohlcv"]

    issues: list[str] = []
    last_date = pd.Timestamp(df.index[-1]).date()
    if (today - last_date).days > stale_after_days:
        issues.append(f"stale_{last_date.isoformat()}")
    if df.index.duplicated().any():
        issues.append("duplicate_dates")
    if (df["close"] <= 0).any():
        issues.append("nonpositive_close")
    if (df["high"] < df["low"]).any():
        issues.append("high_below_low")
    if df[["open", "high", "low", "close"]].isna().any().any():
        issues.append("missing_values")
    return issues
