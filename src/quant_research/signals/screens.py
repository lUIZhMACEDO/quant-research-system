"""The five rule-based screens. Each takes the technical snapshot (and analyst/earnings data) and returns a bool."""

from __future__ import annotations

from collections.abc import Mapping

STRATEGY_NAMES: dict[str, str] = {
    "RSI_MACD": "RSI Momentum + MACD Cross",
    "BB_MEAN_REVERSION": "Bollinger Band Mean Reversion",
    "GOLDEN_CROSS": "EMA Golden Cross Breakout",
    "EARNINGS_REBOUND": "Earnings Dip Buy",
    "INSTITUTIONAL": "Smart Money / Institutional Accumulation",
    "MANUAL": "Manual Thesis",
}


def strategy_rsi_macd(tech: Mapping) -> bool:
    """RSI below 45 on the bar MACD crosses above its signal line."""
    rsi = tech.get("rsi")
    return rsi is not None and rsi < 45 and tech.get("macd_label") == "BULLISH CROSS"


def strategy_bb_mean_reversion(tech: Mapping) -> bool:
    """Price near the lower Bollinger band with RSI below 40."""
    rsi = tech.get("rsi")
    return tech.get("bb_label") == "NEAR LOWER" and rsi is not None and rsi < 40


def strategy_golden_cross(tech: Mapping) -> bool:
    """EMA20 above EMA50 confirmed by a high-volume session."""
    return tech.get("ema_label") == "GOLDEN CROSS" and tech.get("vol_label") == "HIGH VOLUME"


def strategy_earnings_rebound(tech: Mapping, days_since_earnings: int | None) -> bool:
    """Deeply oversold (RSI < 35) within five days of earnings."""
    rsi = tech.get("rsi")
    return rsi is not None and rsi < 35 and days_since_earnings is not None and days_since_earnings <= 5


def strategy_institutional(analyst: Mapping) -> bool:
    """Any insider buying in the last 30 days."""
    return analyst.get("insider_buys", 0) > 0


def detect_strategy(tech: Mapping, analyst: Mapping, earnings: Mapping) -> str:
    """First screen that fires, in priority order; ``MANUAL`` if none do."""
    if strategy_rsi_macd(tech):
        return "RSI_MACD"
    if strategy_bb_mean_reversion(tech):
        return "BB_MEAN_REVERSION"
    if strategy_golden_cross(tech):
        return "GOLDEN_CROSS"
    if strategy_earnings_rebound(tech, earnings.get("days_to_earnings")):
        return "EARNINGS_REBOUND"
    if strategy_institutional(analyst):
        return "INSTITUTIONAL"
    return "MANUAL"
