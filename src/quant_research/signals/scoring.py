"""Composite signal score (-10..+10) and the per-holding rule overrides."""

from __future__ import annotations

from collections.abc import Mapping


def score_to_signal(score: float) -> str:
    if score > 3:
        return "BUY"
    if score > 1:
        return "TRIM"
    if score >= -1:
        return "HOLD"
    if score >= -3:
        return "WATCH"
    return "SELL"


def holding_override(
    ticker: str, price: float, pnl: float, day_chg: float, hi52: float | None
) -> tuple[str, str] | None:
    """Hard rules for specific holdings that take precedence over the score.

    Returns ``(signal, reason)`` or ``None`` if no rule applies.
    """
    if ticker == "OKLO":
        if price >= 85:
            return "SELL", "Price exceeded $85 target -- take profit"
        if pnl > 30:
            return "TRIM", f"Up {pnl:+.1f}% -- take profit before Q1 volatility"
        if pnl < -20:
            return "WATCH", f"Down {pnl:+.1f}% -- pre-revenue risk"
        if day_chg < -5:
            return "SELL", f"Sharp {day_chg:+.1f}% drop -- protect capital"
    elif ticker in ("VOO", "SCHD"):
        if ticker == "VOO" and price < 615:
            return "BUY", "Below $615 threshold -- accumulate"
        if day_chg < -3:
            return "BUY", f"Down {day_chg:+.1f}% -- discount, accumulate"
    elif ticker == "EWY":
        dfh = (hi52 - price) / hi52 if hi52 and hi52 > 0 else None
        if dfh is not None and dfh < 0.02:
            return "TRIM", "Near 52W high -- upside capped, take 25% profit"
        if pnl > 25:
            return "TRIM", f"Up {pnl:+.1f}% -- lock in international gains"
    return None


def compute_signal_score(
    ticker: str,
    technicals: Mapping,
    financials: Mapping,
    analyst_data: Mapping,
    news: Mapping | None,
    price: float = 0,
    pnl: float = 0,
    day_chg: float = 0,
    hi52: float | None = None,
) -> dict:
    """Sum of weighted components, clamped to [-10, 10], mapped to a signal.

    Returns ``{"score", "signal", "breakdown", "reasoning"}`` where ``breakdown``
    holds each component's contribution.
    """
    breakdown: dict[str, float] = {}
    parts: list[str] = []

    # Technical components
    rsi = technicals.get("rsi")
    if rsi is not None:
        if rsi < 30:
            s = 2.0
        elif rsi < 45:
            s = 1.0
        elif rsi <= 55:
            s = 0.0
        elif rsi <= 70:
            s = -0.5
        else:
            s = -2.0
        breakdown["rsi"] = s
        if s != 0:
            parts.append(f"RSI {rsi:.0f} ({'oversold' if s > 0 else 'overbought'})")
    else:
        breakdown["rsi"] = 0.0

    macd_lbl = technicals.get("macd_label", "NEUTRAL")
    if "BULLISH" in macd_lbl:
        breakdown["macd"] = 2.0
        parts.append("MACD bullish crossover")
    elif "BEARISH" in macd_lbl:
        breakdown["macd"] = -2.0
        parts.append("MACD bearish crossover")
    else:
        breakdown["macd"] = 0.0

    bb_lbl = technicals.get("bb_label", "N/A")
    if bb_lbl == "NEAR LOWER":
        breakdown["bollinger"] = 1.0
        parts.append("Near lower Bollinger band")
    elif bb_lbl == "NEAR UPPER":
        breakdown["bollinger"] = -1.0
        parts.append("Near upper Bollinger band")
    else:
        breakdown["bollinger"] = 0.0

    ema_lbl = technicals.get("ema_label", "N/A")
    if ema_lbl == "GOLDEN CROSS":
        breakdown["ema_cross"] = 1.5
        parts.append("EMA golden cross")
    elif ema_lbl == "DEATH CROSS":
        breakdown["ema_cross"] = -1.5
        parts.append("EMA death cross")
    else:
        breakdown["ema_cross"] = 0.0

    vol_up = technicals.get("vol_up_day", True)
    if technicals.get("vol_label", "NORMAL") == "HIGH VOLUME":
        breakdown["volume"] = 0.5 if vol_up else -0.5
        parts.append(f"High volume {'up' if vol_up else 'down'} day")
    else:
        breakdown["volume"] = 0.0

    # Valuation
    pe = financials.get("trail_pe") or financials.get("fwd_pe")
    if pe is not None:
        if pe < 15:
            breakdown["pe_ratio"] = 1.0
            parts.append(f"Deep value PE {pe:.1f}")
        elif pe <= 25:
            breakdown["pe_ratio"] = 0.0
        elif pe <= 40:
            breakdown["pe_ratio"] = -0.5
        else:
            breakdown["pe_ratio"] = -1.0
            parts.append(f"High PE {pe:.1f}")
    else:
        breakdown["pe_ratio"] = 0.0

    # Analyst consensus
    buys = analyst_data.get("rec_buy", 0)
    sells = analyst_data.get("rec_sell", 0)
    if buys > sells * 2:
        breakdown["analyst_consensus"] = 1.0
        parts.append("Strong analyst buy consensus")
    elif sells > buys:
        breakdown["analyst_consensus"] = -1.0
        parts.append("Analyst consensus bearish")
    else:
        breakdown["analyst_consensus"] = 0.0

    # Insider activity
    ins_buys = analyst_data.get("insider_buys", 0)
    ins_sells = analyst_data.get("insider_sells", 0)
    if ins_buys > ins_sells:
        breakdown["insider_activity"] = 0.5
        parts.append("Net insider buying")
    elif ins_sells > ins_buys:
        breakdown["insider_activity"] = -0.5
        parts.append("Net insider selling")
    else:
        breakdown["insider_activity"] = 0.0

    # News sentiment (already in [-1, 1])
    sent = news.get("sentiment_score", 0.0) if isinstance(news, Mapping) else 0.0
    breakdown["news_sentiment"] = round(max(-1.0, min(1.0, sent)), 2)
    if abs(sent) > 0.3:
        parts.append(f"News sentiment {'bullish' if sent > 0 else 'bearish'} ({sent:+.2f})")

    score = round(max(-10.0, min(10.0, sum(breakdown.values()))), 1)
    signal = score_to_signal(score)
    reasoning = ". ".join(parts) + "." if parts else "No strong signals detected."

    override = holding_override(ticker, price, pnl, day_chg, hi52)
    if override:
        signal, reasoning = override

    return {"score": score, "signal": signal, "breakdown": breakdown, "reasoning": reasoning}


def signal_logic(
    tk: str, price: float, pnl: float, pe: float | None, day_chg: float, hi52: float | None
) -> tuple[str, str]:
    """Rule-only signal used for user-entered portfolios in the dashboard (no scoring)."""
    dfh = (hi52 - price) / hi52 if hi52 and hi52 > 0 else None

    if tk == "OKLO":
        if price >= 85:
            return "SELL", "Price exceeded $85 target -- take profit"
        if pnl > 30:
            return "TRIM", f"Up {pnl:+.1f}% -- take profit before Q1 volatility"
        if pnl < -20:
            return "WATCH", f"Down {pnl:+.1f}% -- pre-revenue risk"
        if day_chg < -5:
            return "SELL", f"Sharp {day_chg:+.1f}% drop -- protect capital"
        return "WATCH", "Hold until July 2026 DOE milestones; sell if >$85"

    if tk in ("VOO", "SCHD"):
        if tk == "VOO" and price < 615:
            return "BUY", "Below $615 threshold -- accumulate"
        if day_chg < -3:
            return "BUY", f"Down {day_chg:+.1f}% -- discount, accumulate"
        if day_chg < -2:
            return "BUY", f"Dip of {day_chg:+.1f}% -- good DCA entry"
        return "HOLD", "Long-term compounding in progress"

    if tk == "EWY":
        if dfh is not None and dfh < 0.02:
            return "TRIM", "Near 52W high -- upside capped, take 25% profit"
        if pnl > 25:
            return "TRIM", f"Up {pnl:+.1f}% -- lock in international gains"
        if day_chg < -3:
            return "BUY", f"Down {day_chg:+.1f}% -- EM dip opportunity"
        return "HOLD", "Healthy international exposure"

    if day_chg < -5:
        return "SELL", f"Sharp {day_chg:+.1f}% drop"
    if pnl > 30 and pe and pe > 35:
        return "SELL", f"Up {pnl:+.1f}% w/ high PE"
    if pe and pe < 15:
        return "BUY", f"Deep value -- PE {pe:.1f}"
    return "HOLD", "No action needed"
