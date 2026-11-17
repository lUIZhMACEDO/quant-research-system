"""Research configuration: the portfolio, watchlists, curated picks and rule tables.

This is data, not logic. The portfolio itself lives in ``data/master_portfolio.json``
(edited from the GitHub Pages dashboard); everything else here is the owner's
hand-maintained research view and is not tuned for anyone else.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def load_portfolio(path: Path) -> list[dict]:
    """Read holdings from the portfolio JSON file.

    The file stores ``avgPrice`` (the Pages UI's field name); the rest of the code
    uses ``avg_cost``. Returns an empty list if the file is missing or malformed.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("Could not load portfolio JSON %s: %s", path, exc)
        return []
    holdings = []
    for h in data.get("portfolio", []):
        try:
            holdings.append({"ticker": h["ticker"], "shares": h["shares"], "avg_cost": h["avgPrice"]})
        except (KeyError, TypeError):
            log.warning("Skipping malformed portfolio row: %r", h)
    return holdings


PORTFOLIO_STRATEGIES: dict[str, str] = {
    "OKLO": "Hold until July 2026 DOE milestones; Sell if >$85.",
    "VOO": "Core position. Buy more if price dips below $615.",
    "SCHD": "Dividend play. Reinvest distributions quarterly.",
    "EWY": "Take 25% profit now; South Korea index is at 52W highs.",
}

ALERT_RULES: dict[str, dict[str, float]] = {
    "OKLO": {"price_move_pct": 3.0, "min_score_change": 3, "earnings_days": 2},
    "VOO": {"price_move_pct": 2.0, "min_score_change": 4, "earnings_days": 1},
    "EWY": {"price_move_pct": 3.0, "min_score_change": 3, "earnings_days": 2},
    "SCHD": {"price_move_pct": 2.5, "min_score_change": 4, "earnings_days": 2},
    "_default": {"price_move_pct": 3.0, "min_score_change": 3, "earnings_days": 2},
}

# Smart picks. entry=0 means "derive from the live price and ATR" (see signals.trade_plan).
MOMENTUM_PICKS: list[dict] = [
    {
        "ticker": "AMD",
        "name": "Advanced Micro Devices",
        "strategy_type": "RSI_MACD",
        "entry": 0,
        "reason": "AI capex super-cycle intact. Meta/Alphabet GPU spend accelerating. "
        "Buying the pullback toward ATR support — not chasing.",
    },
    {
        "ticker": "NVDA",
        "name": "NVIDIA Corporation",
        "strategy_type": "RSI_MACD",
        "entry": 0,
        "reason": "Blackwell ramp intact. Tariff/macro fears creating oversold RSI. "
        "Best-in-class AI infrastructure play — buy weakness.",
    },
]

SWING_PICKS: list[dict] = [
    {
        "ticker": "PEP",
        "name": "PepsiCo",
        "strategy_type": "INSTITUTIONAL",
        "entry": 0,
        "reason": "Defensive rotation play. RSI oversold, high institutional support. "
        "Dividend yield near 4% — income + capital appreciation.",
    },
    {
        "ticker": "TMUS",
        "name": "T-Mobile US",
        "strategy_type": "RSI_MACD",
        "entry": 0,
        "reason": "Best telecom relative strength. Tariff-immune domestic revenue. "
        "Breaking above 200-day MA — momentum building.",
    },
]

STRATEGY_TIMELINE: list[dict] = [
    {
        "period": "Immediate",
        "action": "Execute EWY Trim",
        "detail": "Lock in 26% gain on international ETF. Prudent given new 10% global tariff uncertainty.",
    },
    {
        "period": "This Week",
        "action": "Monitor NVDA Earnings (Wed)",
        "detail": "Nvidia results will dictate whether OKLO and VOO face a sector-wide AI correction.",
    },
    {
        "period": "April 2026",
        "action": "Trim OKLO if >$82",
        "detail": "Likely volatility spike before Q1 earnings. Lock in any gains above $80.",
    },
    {
        "period": "Late 2026",
        "action": "Accumulate SCHD",
        "detail": "Value stocks are predicted to outperform tech in H2 2026.",
    },
    {
        "period": "July 2026",
        "action": "OKLO DOE Deadline",
        "detail": "If they miss the criticality milestone the stock will likely retrace to the $40 range.",
    },
]

# Tickers to check for earnings this week
WATCHLIST: list[str] = ["NVDA", "AAPL", "MSFT", "GOOGL", "META", "AMZN", "TSLA", "JPM"]

MACRO_KEYWORDS: dict[str, dict] = {
    "tariff": {"tickers": ["EWY"], "level": "HIGH", "reason": "International trade risk"},
    "china": {"tickers": ["EWY"], "level": "HIGH", "reason": "China geopolitical risk"},
    "sanctions": {"tickers": ["EWY"], "level": "HIGH", "reason": "Sanctions risk"},
    "fed": {"tickers": ["SCHD", "VOO"], "level": "MEDIUM", "reason": "Fed policy change"},
    "rate hike": {"tickers": ["SCHD", "VOO"], "level": "MEDIUM", "reason": "Rate hike risk"},
    "rate cut": {"tickers": ["SCHD", "VOO"], "level": "MEDIUM", "reason": "Rate cut signal"},
    "inflation": {"tickers": ["SCHD", "VOO"], "level": "MEDIUM", "reason": "Inflation impact"},
    "recession": {"tickers": ["*"], "level": "MEDIUM", "reason": "Recession risk"},
    "gdp": {"tickers": ["*"], "level": "MEDIUM", "reason": "GDP growth concern"},
    "war": {"tickers": ["*"], "level": "HIGH", "reason": "Geopolitical conflict"},
    "opec": {"tickers": ["*"], "level": "MEDIUM", "reason": "Energy price impact"},
    "earnings miss": {"tickers": ["*"], "level": "MEDIUM", "reason": "Earnings concern"},
}

SECTOR_ETF_MAP: dict[str, str] = {
    "OKLO": "NLR",
    "EWY": "EEM",
    "SCHD": "DVY",
    "VOO": "SPY",
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}
