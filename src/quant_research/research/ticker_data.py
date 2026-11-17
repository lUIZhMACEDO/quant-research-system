"""Per-ticker enrichment from live providers: technicals, financials, earnings, analysts, relative strength."""

from __future__ import annotations

import datetime as dt
from datetime import timedelta

import pandas as pd
import yfinance as yf

from quant_research.research.market_data import fh_call, get_hist, get_info
from quant_research.signals.technicals import technical_snapshot
from quant_research.signals.valuation import (
    altman_label,
    altman_z,
    earnings_surprise_pct,
    estimate_revision_label,
    peg_label,
    peg_ratio,
)
from quant_research.watchlist import SECTOR_ETF_MAP

try:
    from pyfinviz.stock import Stock as _FinvizStock

    _HAS_FINVIZ = True
except Exception:
    _HAS_FINVIZ = False


def compute_technicals(ticker: str) -> dict:
    """Technical snapshot from the last 90 daily bars."""
    return technical_snapshot(get_hist(ticker, "90d", "1d"))


def _row(frame: pd.DataFrame, *labels: str, default=0):
    for label in labels:
        if label in frame.index:
            return frame.loc[label].iloc[0]
    return default


def _altman_from_statements(ticker: str, market_cap: float) -> float | None:
    tkr = yf.Ticker(ticker)
    bs, inc = tkr.balance_sheet, tkr.income_stmt
    if bs is None or bs.empty or inc is None or inc.empty:
        return None
    total_assets = _row(bs, "Total Assets", default=None)
    if not total_assets or total_assets <= 0:
        return None
    if "Current Assets" in bs.index and "Current Liabilities" in bs.index:
        wc = bs.loc["Current Assets"].iloc[0] - bs.loc["Current Liabilities"].iloc[0]
    else:
        wc = 0
    if "Total Liabilities Net Minority Interest" in bs.index:
        tl = bs.loc["Total Liabilities Net Minority Interest"].iloc[0]
    else:
        tl = total_assets - _row(bs, "Total Equity Gross Minority Interest")
    return altman_z(
        working_capital=wc,
        retained_earnings=_row(bs, "Retained Earnings"),
        ebit=_row(inc, "EBIT", "Operating Income"),
        market_cap=market_cap,
        total_liabilities=tl,
        revenue=_row(inc, "Total Revenue"),
        total_assets=total_assets,
    )


def get_financials(ticker: str) -> dict:
    info = get_info(ticker)
    fwd_pe = info.get("forwardPE")
    eg = info.get("earningsGrowth")
    short_pct = info.get("shortPercentOfFloat")

    # Finviz backup for short float
    if short_pct is None and _HAS_FINVIZ:
        try:
            sf = _FinvizStock(ticker).ticker_fundament.get("Short Float")
            if sf and "%" in str(sf):
                short_pct = float(str(sf).replace("%", "")) / 100
        except Exception:
            pass

    peg = peg_ratio(fwd_pe, eg)

    z_score = None
    try:
        z_score = _altman_from_statements(ticker, info.get("marketCap") or 0)
    except Exception:
        pass

    est_revision = "N/A"
    try:
        est_data = fh_call("company_eps_estimates", ticker, freq="quarterly")
        if est_data and isinstance(est_data, dict):
            est_revision = estimate_revision_label(est_data.get("data", []))
    except Exception:
        pass

    return {
        "fwd_pe": fwd_pe,
        "trail_pe": info.get("trailingPE"),
        "pb": info.get("priceToBook"),
        "ps": info.get("priceToSalesTrailing12Months"),
        "eps": info.get("trailingEps"),
        "earnings_growth": eg,
        "revenue_growth": info.get("revenueGrowth"),
        "profit_margins": info.get("profitMargins"),
        "debt_to_equity": info.get("debtToEquity"),
        "fcf": info.get("freeCashflow"),
        "beta": info.get("beta"),
        "div_yield": info.get("dividendYield"),
        "short_float": short_pct,
        "inst_pct": info.get("heldPercentInstitutions"),
        "sector": info.get("sector", "Unknown"),
        "peg": peg,
        "peg_label": peg_label(peg),
        "z_score": z_score,
        "z_label": altman_label(z_score),
        "est_revision": est_revision,
    }


def _next_earnings_date(cal) -> dt.date | None:
    if cal is None:
        return None
    if isinstance(cal, pd.DataFrame) and "Earnings Date" in cal.columns:
        ed = cal["Earnings Date"].iloc[0]
    elif isinstance(cal, dict):
        ed = cal.get("Earnings Date")
        if isinstance(ed, list) and ed:
            ed = ed[0]
    else:
        ed = None
    if ed is not None and hasattr(ed, "date"):
        ed = ed.date() if callable(ed.date) else ed
    return ed if isinstance(ed, dt.date) else None


def get_earnings_info(ticker: str) -> dict:
    """Next earnings date and the last quarter's EPS surprise."""
    result = {
        "next_earnings": None,
        "days_to_earnings": None,
        "last_eps_actual": None,
        "last_eps_est": None,
        "last_surprise_pct": None,
    }
    try:
        ed = _next_earnings_date(yf.Ticker(ticker).calendar)
        if ed is not None:
            result["next_earnings"] = ed
            result["days_to_earnings"] = (ed - dt.date.today()).days
    except Exception:
        pass

    data = fh_call("company_earnings", ticker, limit=1)
    if data and isinstance(data, list):
        q = data[0]
        result["last_eps_actual"] = q.get("actual")
        result["last_eps_est"] = q.get("estimate")
        result["last_surprise_pct"] = earnings_surprise_pct(q.get("actual"), q.get("estimate"))
    return result


def get_weekly_catalysts(tickers: set[str]) -> list[dict]:
    """Earnings reports in the next 7 days for the given tickers."""
    today = dt.date.today()
    week = today + timedelta(days=7)
    cal = fh_call("earnings_calendar", _from=today.strftime("%Y-%m-%d"), to=week.strftime("%Y-%m-%d"))
    fh_earnings = {}
    if cal and isinstance(cal, dict):
        for ev in cal.get("earningsCalendar", []):
            fh_earnings[ev.get("symbol", "")] = ev

    catalysts = []
    for tk in sorted(tickers):
        ei = get_earnings_info(tk)
        days = ei.get("days_to_earnings")
        if days is not None and 0 <= days <= 7:
            catalysts.append(
                {
                    "ticker": tk,
                    "date": ei["next_earnings"],
                    "days": days,
                    "eps_est": fh_earnings.get(tk, {}).get("epsEstimate"),
                }
            )
    return catalysts


def get_analyst_data(ticker: str) -> dict:
    result = {
        "rec_buy": 0,
        "rec_hold": 0,
        "rec_sell": 0,
        "target_mean": None,
        "target_high": None,
        "target_low": None,
        "insider_buys": 0,
        "insider_sells": 0,
    }

    rec = fh_call("recommendation_trends", ticker)
    if rec and isinstance(rec, list):
        r = rec[0]
        result["rec_buy"] = (r.get("buy", 0) or 0) + (r.get("strongBuy", 0) or 0)
        result["rec_hold"] = r.get("hold", 0) or 0
        result["rec_sell"] = (r.get("sell", 0) or 0) + (r.get("strongSell", 0) or 0)

    pt = fh_call("price_target", ticker)
    if pt and isinstance(pt, dict):
        result["target_mean"] = pt.get("targetMean")
        result["target_high"] = pt.get("targetHigh")
        result["target_low"] = pt.get("targetLow")

    today = dt.date.today()
    ago = today - timedelta(days=30)
    txns = fh_call("stock_insider_transactions", ticker, _from=ago.strftime("%Y-%m-%d"), to=today.strftime("%Y-%m-%d"))
    if txns and isinstance(txns, dict):
        for t in txns.get("data", []):
            chg = t.get("change", 0) or 0
            if chg > 0:
                result["insider_buys"] += 1
            elif chg < 0:
                result["insider_sells"] += 1
    return result


def get_relative_strength(ticker: str, period_days: int = 20) -> dict:
    """Ticker return minus its sector ETF's return over ``period_days``."""
    default = {"ticker_return": 0, "sector_return": 0, "relative_strength": 0, "outperforming": False}
    try:
        sector_etf = SECTOR_ETF_MAP.get(ticker)
        if not sector_etf:
            sector_etf = SECTOR_ETF_MAP.get(get_info(ticker).get("sector", ""), "SPY")
        period_str = f"{period_days + 5}d"
        tk_hist = get_hist(ticker, period_str, "1d")
        se_hist = get_hist(sector_etf, period_str, "1d")
        if tk_hist.empty or se_hist.empty or len(tk_hist) < 2 or len(se_hist) < 2:
            return default
        tk_ret = (tk_hist["Close"].iloc[-1] / tk_hist["Close"].iloc[-min(period_days, len(tk_hist))] - 1) * 100
        se_ret = (se_hist["Close"].iloc[-1] / se_hist["Close"].iloc[-min(period_days, len(se_hist))] - 1) * 100
        rs = tk_ret - se_ret
        return {
            "ticker_return": round(tk_ret, 2),
            "sector_return": round(se_ret, 2),
            "relative_strength": round(rs, 2),
            "outperforming": rs > 0,
        }
    except Exception:
        return default
