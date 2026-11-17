"""Daily OHLCV from yfinance, normalised to one tidy shape."""

from __future__ import annotations

import logging

import pandas as pd

log = logging.getLogger(__name__)

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]
MIN_BARS = 20


def normalize_ohlcv(raw: pd.DataFrame | None, ticker: str, min_bars: int = MIN_BARS) -> pd.DataFrame | None:
    """Turn a ``yf.download`` result into ``[ticker, open, high, low, close, volume]`` indexed by date.

    Recent yfinance versions return MultiIndex columns such as ``("Close", "SPY")``
    even for a single ticker; older ones return flat ``"Close"``. Both are handled.
    Returns ``None`` when the frame is empty, too short, or missing a required column.
    """
    if raw is None or raw.empty:
        return None
    df = raw.copy()
    if isinstance(df.columns, pd.MultiIndex):
        # Keep the price-field level (Open/High/...), whichever level it sits on.
        fields = {c.lower() for c in OHLCV_COLUMNS}
        level = next(
            (i for i in range(df.columns.nlevels) if {str(v).lower() for v in df.columns.get_level_values(i)} & fields),
            0,
        )
        df.columns = df.columns.get_level_values(level)
    df.columns = [str(c).lower() for c in df.columns]
    df = df.loc[:, ~pd.Index(df.columns).duplicated()]
    if any(c not in df.columns for c in OHLCV_COLUMNS):
        return None
    df = df[OHLCV_COLUMNS].dropna(subset=["close"])
    if len(df) < min_bars:
        return None
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    df.insert(0, "ticker", ticker)
    return df


def fetch_ohlcv(ticker: str, period: str = "5y") -> pd.DataFrame | None:
    """Fetch split/dividend-adjusted OHLCV from yfinance. Returns ``None`` on failure."""
    try:
        import yfinance as yf

        raw = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    except Exception as exc:
        log.warning("yfinance fetch failed for %s: %s", ticker, exc)
        return None
    return normalize_ohlcv(raw, ticker)
