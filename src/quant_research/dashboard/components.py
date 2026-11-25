"""Small rendering helpers and live-price lookups for the dashboard."""

from __future__ import annotations

import datetime as dt
import re
from html import escape

import pandas as pd
import pytz
import streamlit as st

from quant_research.dashboard.theme import ALT, AMBER, BLUE, DIM, GREEN, PURPLE, RED, TEXT, WHITE

NY = pytz.timezone("America/New_York")
_EMAIL_RE = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[A-Za-z]{2,}$")


def dlr(v: float) -> str:
    return f"${v:,.2f}"


def pct(v: float) -> str:
    return f"{v:+.2f}%"


def clr(v: float) -> str:
    return GREEN if v >= 0 else RED


def is_valid_email(address: str) -> bool:
    """Single plain address only: blocks header injection via newlines, commas or angle brackets."""
    return bool(address) and bool(_EMAIL_RE.match(address.strip()))


def safe_link(title: str, url: str, color: str = BLUE) -> str:
    """Escaped headline, linked only if the URL is http(s)."""
    t = escape(title or "")
    url = (url or "").strip()
    if url.lower().startswith(("http://", "https://")):
        return f'<a href="{escape(url, quote=True)}" style="color:{color};text-decoration:none;">{t}</a>'
    return t


def is_market_open(now: dt.datetime | None = None) -> bool:
    """Regular NYSE session, Mon-Fri 9:30-16:00 ET (holidays not modelled)."""
    now = now.astimezone(NY) if now else dt.datetime.now(NY)
    if now.weekday() >= 5:
        return False
    return dt.time(9, 30) <= now.time() <= dt.time(16, 0)


def _quote(prev: float, curr: float) -> dict:
    chg = curr - prev
    return {"price": curr, "change": chg, "change_pct": round(chg / prev * 100, 2) if prev else 0}


@st.cache_data(ttl=15, show_spinner=False)
def get_live_prices(tickers: tuple) -> dict:
    """Last close vs the one before, batched through ``yf.download``; per-ticker fallback."""
    import yfinance as yf

    if not tickers:
        return {}
    tickers_list = list(tickers)
    result: dict[str, dict] = {}
    try:
        df = yf.download(tickers_list, period="2d", interval="1d", auto_adjust=True, progress=False, threads=True)
        if df.empty:
            raise ValueError("Empty")
        closes = df["Close"] if isinstance(df.columns, pd.MultiIndex) or "Close" in df.columns else df
        if isinstance(closes, pd.DataFrame):
            for tk in tickers_list:
                try:
                    col = closes[tk] if tk in closes.columns else closes.iloc[:, 0]
                    prices = col.dropna()
                    if len(prices) >= 2:
                        result[tk] = _quote(float(prices.iloc[-2]), float(prices.iloc[-1]))
                except Exception:
                    result[tk] = {"price": 0.0, "change": 0.0, "change_pct": 0.0}
        else:
            prices = closes.dropna()
            if len(prices) >= 2 and len(tickers_list) == 1:
                result[tickers_list[0]] = _quote(float(prices.iloc[-2]), float(prices.iloc[-1]))
    except Exception:
        pass
    for tk in tickers_list:
        if tk not in result:
            try:
                fi = yf.Ticker(tk).fast_info
                p = float(fi.last_price or 0)
                pc = float(fi.previous_close or p)
                result[tk] = _quote(pc, p)
            except Exception:
                result[tk] = {"price": 0.0, "change": 0.0, "change_pct": 0.0}
    return result


def apply_live_prices(holdings: list[dict], live: dict) -> list[dict]:
    """Copies of ``holdings`` with price, value and P&L refreshed from ``live`` quotes."""
    out = [dict(h) for h in holdings]
    for h in out:
        d = live.get(h["ticker"], {})
        if d.get("price", 0) > 0:
            lp = d["price"]
            h["current_price"] = round(lp, 2)
            h["market_value"] = round(lp * h["shares"], 2)
            h["day_pnl"] = round(d.get("change", 0) * h["shares"], 2)
            h["day_pnl_pct"] = round(d.get("change_pct", 0), 2)
            h["open_pnl"] = round(h["market_value"] - h["total_cost"], 2)
            h["open_pnl_pct"] = round((lp - h["avg_cost"]) / h["avg_cost"] * 100, 2) if h["avg_cost"] else 0
    return out


def sig_badge(sig: str) -> str:
    s = sig.upper()
    if "BUY" in s:
        c = "buy"
    elif "SELL" in s:
        c = "sell"
    elif "TRIM" in s:
        c = "trim"
    elif "WATCH" in s:
        c = "watch"
    else:
        c = "hold"
    return f'<span class="badge badge-{c}">{escape(sig)}</span>'


def pick_card(p: dict) -> str:
    sc = GREEN if p["status"] == "ACTIVE" else AMBER
    t = p.get("tech", {})
    rsi_s = f'RSI {t["rsi"]:.0f}' if t.get("rsi") else ""
    extras = " | ".join(x for x in [rsi_s, t.get("macd_label", ""), t.get("ema_label", "")] if x and x != "N/A")
    return f"""
    <div class="stock-card">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">
        <div>
          <span style="font-size:17px;font-weight:800;color:{WHITE};">{escape(p["ticker"])}</span>
          <span style="font-size:12px;color:{DIM};margin-left:8px;">{escape(p["name"])}</span>
        </div>
        <div>
          <span style="font-size:14px;font-weight:700;color:{WHITE};">{dlr(p["current_price"])}</span>
          <span style="margin-left:8px;color:{clr(p['day_chg'])};font-weight:700;">{pct(p["day_chg"])}</span>
          <span class="badge" style="margin-left:8px;background:{sc}1a;color:{sc};">{p["status"]}</span>
        </div>
      </div>
      <div style="margin-top:6px;padding:6px 10px;background:{PURPLE}15;border-radius:4px;
                  font-size:11px;color:{PURPLE};font-weight:600;">Strategy: {escape(p["strategy_name"])}</div>
      <div style="font-size:12px;color:{TEXT};margin-top:8px;line-height:1.5;">{escape(p["reason"])}</div>
      <div style="display:flex;gap:20px;margin-top:12px;padding:12px 14px;
                  background:{ALT};border-radius:6px;flex-wrap:wrap;">
        <div style="text-align:center;"><div class="kpi-label">Entry</div>
            <div class="kpi-value" style="color:{BLUE};">{dlr(p["entry"])}</div></div>
        <div style="text-align:center;"><div class="kpi-label">Target</div>
            <div class="kpi-value" style="color:{GREEN};">{dlr(p["target"])}</div></div>
        <div style="text-align:center;"><div class="kpi-label">Stop</div>
            <div class="kpi-value" style="color:{RED};">{dlr(p["stop"])}</div></div>
        <div style="text-align:center;"><div class="kpi-label">R / R</div>
            <div class="kpi-value" style="color:{WHITE};">1:{p["rr"]:.1f}</div></div>
        <div style="text-align:center;"><div class="kpi-label">Position</div>
            <div class="kpi-value" style="color:{WHITE};">{p["pos_size"]} shares</div></div>
      </div>
      <div style="margin-top:8px;font-size:10px;color:{DIM};">
        Risk: {p["risk_pct"]:.1f}% | Reward: {p["reward_pct"]:.1f}%
        {f" | {extras}" if extras else ""}
      </div>
      <div style="font-size:10px;color:{DIM};margin-top:2px;">Fill: {p["fill_window"]}</div>
    </div>"""
