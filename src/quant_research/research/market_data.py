"""Thin, cached access to live market data providers (yfinance and Finnhub).

Every call degrades to an empty result instead of raising, because one flaky
ticker should never take down the report or the dashboard.
"""

from __future__ import annotations

import functools
import logging
import time

import pandas as pd
import yfinance as yf

from quant_research.config import get_settings

log = logging.getLogger(__name__)

try:  # Streamlit's cache is shared across dashboard sessions; it also works outside Streamlit.
    import streamlit as _st
except ImportError:  # pragma: no cover - streamlit is a runtime dependency
    _st = None


def _get_info_impl(ticker: str) -> dict:
    try:
        return yf.Ticker(ticker).info or {}
    except Exception:
        return {}


def _get_hist_impl(ticker: str, period: str, interval: str) -> pd.DataFrame:
    try:
        return yf.Ticker(ticker).history(period=period, interval=interval)
    except Exception:
        return pd.DataFrame()


if _st is not None:

    @_st.cache_data(ttl=60)
    def get_info(ticker: str) -> dict:
        return _get_info_impl(ticker)

    @_st.cache_data(ttl=60)
    def get_hist(ticker: str, period: str = "30d", interval: str = "1d") -> pd.DataFrame:
        return _get_hist_impl(ticker, period, interval)
else:  # pragma: no cover

    def get_info(ticker: str) -> dict:
        return _get_info_impl(ticker)

    def get_hist(ticker: str, period: str = "30d", interval: str = "1d") -> pd.DataFrame:
        return _get_hist_impl(ticker, period, interval)


@functools.lru_cache(maxsize=1)
def _finnhub_client():
    key = get_settings().finnhub_api_key
    if not key:
        return None
    try:
        import finnhub

        return finnhub.Client(api_key=key)
    except Exception as exc:
        log.warning("Finnhub client unavailable: %s", exc)
        return None


def fh_call(func_name: str, *args, **kwargs):
    """Rate-limited Finnhub call. Returns ``None`` if there is no key or the call fails."""
    client = _finnhub_client()
    if client is None:
        return None
    fn = getattr(client, func_name, None)
    if fn is None:
        return None
    try:
        time.sleep(get_settings().finnhub_rate_limit_delay)
        return fn(*args, **kwargs)
    except Exception:
        return None


def quote_from_info(info: dict) -> tuple[float, float]:
    """``(current, previous_close)`` from a yfinance info dict, 0 when unknown."""
    cur = info.get("currentPrice") or info.get("regularMarketPrice") or 0
    prev = info.get("previousClose") or info.get("regularMarketPreviousClose") or 0
    return cur, prev
