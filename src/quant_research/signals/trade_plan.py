"""Entry, stop, target and sizing for the curated picks.

Invariants enforced for every plan: ``stop < entry < target`` and reward/risk of
at least 2:1. Breakout strategies enter above the market; everything else uses
a limit at or below it.
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Mapping

BREAKOUT_STRATEGIES = frozenset({"GOLDEN_CROSS", "ASCENDING_TRIANGLE", "BREAKOUT"})
RISK_PER_TRADE = 0.01  # fraction of account risked per trade
MIN_REWARD_RISK = 2.0


def compute_trade_levels(
    price: float, atr: float | None, strategy: str, cfg_entry: float = 0, cfg_stop: float = 0, cfg_target: float = 0
) -> dict:
    """Validate configured levels against the live price, filling gaps from ATR.

    * Entry: a configured limit above the market is stale and is reset to 0.8%
      under it; breakouts default to 0.5% over it.
    * Stop: configured value if it sits under the entry, else entry - 1.5 ATR.
    * Target: configured value or entry + 3 ATR, never below a 2:1 reward/risk.
    """
    atr = atr or price * 0.02
    is_breakout = strategy in BREAKOUT_STRATEGIES

    if cfg_entry and cfg_entry > 0:
        if is_breakout:
            entry = cfg_entry
        else:
            entry = cfg_entry if cfg_entry <= price * 1.001 else round(price * 0.992, 2)
    else:
        entry = round(price * 1.005, 2) if is_breakout else round(price * 0.992, 2)

    stop = cfg_stop if cfg_stop and 0 < cfg_stop < entry else round(entry - 1.5 * atr, 2)

    min_tgt = round(entry + MIN_REWARD_RISK * (entry - stop), 2)
    if cfg_target and cfg_target > entry:
        target = max(round(cfg_target, 2), min_tgt)
    else:
        target = max(round(entry + 3.0 * atr, 2), min_tgt)

    risk_pct = (entry - stop) / entry * 100 if entry else 0
    reward_pct = (target - entry) / entry * 100 if entry else 0
    rr = reward_pct / risk_pct if risk_pct > 0 else 0
    return {
        "entry": entry,
        "stop": stop,
        "target": target,
        "risk_pct": risk_pct,
        "reward_pct": reward_pct,
        "rr": rr,
        "is_breakout": is_breakout,
    }


def fill_guidance(price: float, entry: float, is_breakout: bool) -> str:
    """Plain-language note on how close the order is to filling."""
    try:
        if is_breakout:
            pct_away = (entry - price) / price * 100 if price else 0
            if price >= entry:
                return "Price at/above breakout trigger -- enter at market NOW"
            if pct_away < 0.5:
                return f"Within 0.5pct of trigger ${entry:.2f} -- set alert"
            if pct_away < 2.0:
                return f"Breakout ${entry:.2f} is {pct_away:.1f}pct away -- could trigger today"
            return f"Breakout trigger ${entry:.2f} is {pct_away:.1f}pct above market -- monitor"
        pct_away = (price - entry) / price * 100 if price else 0
        if price <= entry * 1.002:
            return f"Limit ${entry:.2f} in range -- place GTC order NOW"
        if pct_away < 1.5:
            return f"Limit ${entry:.2f} is {pct_away:.1f}pct below -- likely fill on any intraday dip"
        if pct_away < 4.0:
            return f"Limit ${entry:.2f} is {pct_away:.1f}pct below market -- expect fill in 1-3 sessions"
        return f"Limit ${entry:.2f} is {pct_away:.1f}pct below market -- GTC order, patient entry"
    except Exception:
        return "Monitor open"


def pick_status(price: float, entry: float, is_breakout: bool) -> str:
    """ACTIVE when the entry is reachable now, WATCH within 6%, otherwise PENDING."""
    if (is_breakout and price >= entry * 0.99) or (not is_breakout and price <= entry * 1.01):
        return "ACTIVE"
    return "WATCH" if price <= entry * 1.06 else "PENDING"


def compute_position_size(entry: float | None, stop: float | None, account_size: float) -> int:
    """Shares such that hitting the stop loses ``RISK_PER_TRADE`` of the account (min 1)."""
    try:
        if entry is None or stop is None:
            return 1
        risk = entry - stop
        if risk <= 0 or math.isnan(risk) or math.isinf(risk):
            return 1
        shares = account_size * RISK_PER_TRADE / risk
        if math.isnan(shares) or math.isinf(shares):
            return 1
        return max(1, int(shares))
    except Exception:
        return 1


def holding_action(signal: str, shares: float, price: float, account_size: float, today: dt.date | None = None) -> str:
    """Concrete next step for a holding given its signal."""
    today30 = ((today or dt.date.today()) + dt.timedelta(days=30)).strftime("%B %d, %Y")
    if signal == "HOLD":
        return f"Thesis intact. Next review: {today30}"
    if signal == "TRIM":
        n = max(1, int(shares * 0.25))
        return f"Sell {n} shares. Suggested limit: ${price:.2f}"
    if signal == "SELL":
        return f"Exit full position. Target exit: ${price:.2f}"
    if signal == "BUY":
        risk = account_size * RISK_PER_TRADE
        n = max(1, int(risk / (price * 0.02))) if price else 1
        return f"Add {n} shares. Limit order at: ${price * 0.995:.2f}"
    if signal == "WATCH":
        return f"Monitor closely. Next review: {today30}"
    return f"Next review: {today30}"


def holding_timeline(ticker: str, price: float, tech: Mapping, earnings: Mapping) -> dict:
    """Short/medium/long-term notes for a holding. Named holdings carry the owner's thesis."""
    ed = earnings.get("next_earnings")
    ed_str = ed.strftime("%b %d") if ed else "TBD"
    atr_s = tech.get("atr_stop") or price * 0.95
    atr_t = tech.get("atr_target") or price * 1.10
    bb = tech.get("bb_label", "N/A")

    tl = {
        "short_level": f"Support: ${atr_s:.2f}  |  Resistance: ${atr_t:.2f}  |  BB: {bb}",
        "short_trigger": "",
        "med_catalyst": f"Next earnings: {ed_str}",
        "med_target": "",
        "long_thesis": "",
        "long_invalidate": "",
    }
    theses = {
        "OKLO": (
            "Sell if price breaks below $55 or drops >5% in a day",
            "Trim at $82-$85 range (analyst consensus)",
            "Nuclear micro-reactor play -- DOE milestones in 2027",
            "Miss July 2026 DOE criticality deadline",
        ),
        "VOO": (
            "Buy more if price dips below $615",
            "S&P target ~7,000 by Q3 2026",
            "Core index -- long-term compounding",
            "Only sell in cash emergency",
        ),
        "SCHD": (
            "Accumulate on any >2% weekly dip",
            "Value rotation expected in H2 2026",
            "Dividend growth + value factor play",
            "Dividend cut or major sector rotation away from value",
        ),
        "EWY": (
            "Trim 25% now -- near 52W high with tariff headwinds",
            "Re-enter on a 10%+ pullback",
            "South Korea EM diversification",
            "New tariffs >15% or China-Taiwan escalation",
        ),
    }
    short, med, long_, invalidate = theses.get(
        ticker,
        (
            f"Stop loss at ${atr_s:.2f} (ATR-based)",
            f"Target ${atr_t:.2f}",
            "Monitor fundamentals quarterly",
            "Thesis break if PE > 40 or revenue declines 2 quarters",
        ),
    )
    tl.update(short_trigger=short, med_target=med, long_thesis=long_, long_invalidate=invalidate)
    return tl
