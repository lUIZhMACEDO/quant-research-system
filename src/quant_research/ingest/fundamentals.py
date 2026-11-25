"""Fundamental ratio snapshot per ticker (yfinance ``.info``)."""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Mapping

log = logging.getLogger(__name__)

# fundamentals table column -> yfinance .info key
INFO_FIELD_MAP: dict[str, str] = {
    "pe_ttm": "trailingPE",
    "pe_forward": "forwardPE",
    "pb": "priceToBook",
    "ps_ttm": "priceToSalesTrailing12Months",
    "ev_ebitda": "enterpriseToEbitda",
    "ev_revenue": "enterpriseToRevenue",
    "earnings_growth_yoy": "earningsGrowth",
    "revenue_growth_yoy": "revenueGrowth",
    "debt_to_equity": "debtToEquity",
    "current_ratio": "currentRatio",
    "roe": "returnOnEquity",
    "profit_margin": "profitMargins",
    "analyst_target_price": "targetMeanPrice",
    "analyst_rating": "recommendationMean",  # 1 = Strong Buy, 5 = Sell
    "num_analysts": "numberOfAnalystOpinions",
    "short_pct_float": "shortPercentOfFloat",
    "insider_pct": "heldPercentInsiders",
}


def safe_fcf_yield(info: Mapping) -> float | None:
    """Free cash flow / market cap, or ``None`` when either is missing or market cap <= 0."""
    try:
        fcf = info.get("freeCashflow")
        mcap = info.get("marketCap")
        if fcf is not None and mcap and mcap > 0:
            return round(float(fcf) / float(mcap), 6)
    except (TypeError, ValueError):
        pass
    return None


def parse_fundamentals(ticker: str, info: Mapping | None, date: str | None = None) -> dict:
    """Map a yfinance ``.info`` dict onto the ``fundamentals`` table's columns."""
    row: dict = {"ticker": ticker, "date": date or dt.date.today().isoformat()}
    info = info or {}
    for column, key in INFO_FIELD_MAP.items():
        row[column] = info.get(key)
    row["fcf_yield"] = safe_fcf_yield(info)
    return row


def fetch_fundamentals(ticker: str) -> dict:
    """Fetch and parse fundamentals. On failure returns just ``ticker`` and ``date``."""
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info
    except Exception as exc:
        log.warning("Fundamentals fetch failed for %s: %s", ticker, exc)
        return {"ticker": ticker, "date": dt.date.today().isoformat()}
    return parse_fundamentals(ticker, info)
