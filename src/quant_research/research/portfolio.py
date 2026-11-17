"""Portfolio and pick analysis: combines live data with the pure signal functions."""

from __future__ import annotations

import logging
from collections.abc import Iterable

from quant_research.config import get_settings
from quant_research.research.market_data import get_hist, get_info, quote_from_info
from quant_research.research.news import get_ticker_news, strategy_note
from quant_research.research.ticker_data import (
    compute_technicals,
    get_analyst_data,
    get_earnings_info,
    get_financials,
    get_relative_strength,
)
from quant_research.signals.risk import portfolio_risk
from quant_research.signals.scoring import compute_signal_score, signal_logic
from quant_research.signals.screens import STRATEGY_NAMES, detect_strategy
from quant_research.signals.trade_plan import (
    compute_position_size,
    compute_trade_levels,
    fill_guidance,
    holding_action,
    holding_timeline,
    pick_status,
)
from quant_research.signals.valuation import format_market_cap
from quant_research.watchlist import MOMENTUM_PICKS, PORTFOLIO_STRATEGIES, SWING_PICKS, WATCHLIST

log = logging.getLogger(__name__)


def position_metrics(
    shares: float, avg: float, cur: float, prev: float, hi52: float | None, lo52: float | None
) -> dict:
    """Cost, value, open/day P&L and 52-week range position for one holding."""
    tc = shares * avg
    mv = shares * cur
    rng = (cur - lo52) / (hi52 - lo52) * 100 if hi52 and lo52 and hi52 != lo52 else None
    return {
        "total_cost": tc,
        "market_value": mv,
        "open_pnl": mv - tc,
        "open_pnl_pct": (cur - avg) / avg * 100 if avg else 0,
        "day_pnl": (cur - prev) * shares if prev else 0,
        "day_pnl_pct": (cur - prev) / prev * 100 if prev else 0,
        "range_pct": rng,
    }


def _holding_base(tk: str, shares: float, avg: float) -> tuple[dict, dict]:
    info = get_info(tk)
    cur, prev = quote_from_info(info)
    pe = info.get("trailingPE") or info.get("forwardPE")
    hi52 = info.get("fiftyTwoWeekHigh")
    lo52 = info.get("fiftyTwoWeekLow")
    m = position_metrics(shares, avg, cur, prev, hi52, lo52)
    base = {
        "ticker": tk,
        "name": info.get("shortName") or info.get("longName") or tk,
        "shares": shares,
        "avg_cost": avg,
        "current_price": round(cur, 2),
        "prev_close": round(prev, 2),
        "total_cost": round(m["total_cost"], 2),
        "market_value": round(m["market_value"], 2),
        "open_pnl": round(m["open_pnl"], 2),
        "open_pnl_pct": round(m["open_pnl_pct"], 2),
        "day_pnl": round(m["day_pnl"], 2),
        "day_pnl_pct": round(m["day_pnl_pct"], 2),
        "pe": round(pe, 2) if pe else None,
        "market_cap": format_market_cap(info.get("marketCap")),
        "hi52": round(hi52, 2) if hi52 else None,
        "lo52": round(lo52, 2) if lo52 else None,
        "range_pct": round(m["range_pct"], 1) if m["range_pct"] is not None else None,
    }
    raw = {"cur": cur, "pe": pe, "hi52": hi52, "open_pnl_pct": m["open_pnl_pct"], "day_pnl_pct": m["day_pnl_pct"]}
    return base, raw


def analyse_portfolio(portfolio: list[dict]) -> list[dict]:
    """Full composite-score analysis of the owner's holdings (used by the daily report)."""
    account = get_settings().account_size
    results = []
    for pos in portfolio:
        tk, shares, avg = pos["ticker"], pos["shares"], pos["avg_cost"]
        base, raw = _holding_base(tk, shares, avg)
        cur = raw["cur"]

        tech = compute_technicals(tk)
        fins = get_financials(tk)
        earn = get_earnings_info(tk)
        anly = get_analyst_data(tk)
        news = get_ticker_news(tk)
        rel_str = get_relative_strength(tk)

        scoring = compute_signal_score(
            tk, tech, fins, anly, news, price=cur, pnl=raw["open_pnl_pct"], day_chg=raw["day_pnl_pct"], hi52=raw["hi52"]
        )
        sig = scoring["signal"]
        results.append(
            {
                **base,
                "signal": sig,
                "reason": scoring["reasoning"],
                "action": holding_action(sig, shares, cur, account),
                "score": scoring["score"],
                "score_breakdown": scoring["breakdown"],
                "strategy": PORTFOLIO_STRATEGIES.get(tk, ""),
                "tech": tech,
                "fins": fins,
                "earn": earn,
                "analyst": anly,
                "news": news,
                "timeline": holding_timeline(tk, cur, tech, earn),
                "relative_strength": rel_str,
            }
        )
        log.info(
            "[PORT] %-6s $%8.2f  P&L %+.2f%%  -> %s (score %+.1f)", tk, cur, raw["open_pnl_pct"], sig, scoring["score"]
        )
    return results


def analyse_user_portfolio(portfolio: list[dict]) -> list[dict]:
    """Rule-based analysis for any user's holdings (dashboard), with an LLM-written strategy note."""
    account = get_settings().account_size
    results = []
    for pos in portfolio:
        tk, shares, avg = pos["ticker"].upper().strip(), pos["shares"], pos["avg_cost"]
        base, raw = _holding_base(tk, shares, avg)
        cur = raw["cur"]

        sig, reason = signal_logic(tk, cur, raw["open_pnl_pct"], raw["pe"], raw["day_pnl_pct"], raw["hi52"])
        tech = compute_technicals(tk)
        fins = get_financials(tk)
        earn = get_earnings_info(tk)
        anly = get_analyst_data(tk)
        news = get_ticker_news(tk)
        note = strategy_note(
            tk,
            sig,
            tech.get("rsi") or 50,
            anly.get("rec_buy", 0),
            anly.get("rec_sell", 0),
            fallback=PORTFOLIO_STRATEGIES.get(tk, "Monitor position and reassess on next earnings."),
        )
        results.append(
            {
                **base,
                "signal": sig,
                "reason": reason,
                "action": holding_action(sig, shares, cur, account),
                "strategy_note": note,
                "strategy": "",
                "tech": tech,
                "fins": fins,
                "earn": earn,
                "analyst": anly,
                "news": news,
                "timeline": holding_timeline(tk, cur, tech, earn),
            }
        )
    return results


def enrich_picks(picks: list[dict]) -> list[dict]:
    """Attach live price, screens, score and a validated entry/stop/target plan to each pick."""
    account = get_settings().account_size
    out = []
    for p in picks:
        tk = p["ticker"]
        cur, prev = quote_from_info(get_info(tk))
        day_chg = (cur - prev) / prev * 100 if prev else 0

        tech = compute_technicals(tk)
        earn = get_earnings_info(tk)
        anly = get_analyst_data(tk)
        news = get_ticker_news(tk)
        fins = get_financials(tk)
        scoring = compute_signal_score(tk, tech, fins, anly, news, price=cur, day_chg=day_chg)

        # Prefer the configured strategy label; auto-detect only when it is MANUAL
        strat = p.get("strategy_type", "MANUAL")
        if strat == "MANUAL":
            strat = detect_strategy(tech, anly, earn)

        lv = compute_trade_levels(cur, tech.get("atr"), strat, p.get("entry", 0), p.get("stop", 0), p.get("target", 0))
        status = pick_status(cur, lv["entry"], lv["is_breakout"])
        out.append(
            {
                **p,
                "current_price": round(cur, 2),
                "day_chg": round(day_chg, 2),
                "status": status,
                "strategy_key": strat,
                "strategy_name": STRATEGY_NAMES.get(strat, strat),
                "entry": round(lv["entry"], 2),
                "target": round(lv["target"], 2),
                "stop": round(lv["stop"], 2),
                "risk_pct": round(lv["risk_pct"], 2),
                "reward_pct": round(lv["reward_pct"], 2),
                "rr": round(lv["rr"], 1),
                "pos_size": compute_position_size(lv["entry"], lv["stop"], account),
                "fill_window": fill_guidance(cur, lv["entry"], lv["is_breakout"]),
                "tech": tech,
                "earn": earn,
                "analyst": anly,
                "news": news,
                "fins": fins,
                "score": scoring["score"],
                "score_breakdown": scoring["breakdown"],
            }
        )
        log.info(
            "[PICK] %-6s $%8.2f  Day %+.2f%%  -> %s  [%s] (score %+.1f)",
            tk,
            cur,
            day_chg,
            status,
            strat,
            scoring["score"],
        )
    return out


def compute_risk_dashboard(holdings: list[dict]) -> dict:
    """Portfolio risk using each holding's last 30 sessions of returns."""
    returns = {}
    for h in holdings:
        hist = get_hist(h["ticker"], "30d", "1d")
        if not hist.empty and len(hist) > 1:
            returns[h["ticker"]] = hist["Close"].pct_change().dropna().to_numpy()
    return portfolio_risk(holdings, returns)


def catalyst_universe(portfolio: Iterable[dict]) -> set[str]:
    """Tickers checked for upcoming earnings: watchlist + holdings + curated picks."""
    tickers = set(WATCHLIST)
    tickers.update(p["ticker"] for p in portfolio)
    tickers.update(p["ticker"] for p in MOMENTUM_PICKS + SWING_PICKS)
    return tickers
