"""HTML and plain-text builders for the daily email report.

Gmail strips <style> blocks inconsistently, so everything is inline-styled. All
third-party text (headlines, publishers, company names) is HTML-escaped before
it is interpolated, and links are restricted to http(s).
"""

from __future__ import annotations

import datetime as dt
from html import escape

from quant_research.watchlist import STRATEGY_TIMELINE

C_BG = "#0b0e11"
C_CARD = "#141821"
C_ALT = "#1a1f2b"
C_BORDER = "#1e2533"
C_TEXT = "#d1d4dc"
C_DIM = "#6b7280"
C_GREEN = "#00d26a"
C_RED = "#f6465d"
C_AMBER = "#f0b90b"
C_BLUE = "#3b82f6"
C_WHITE = "#ffffff"
C_PURPLE = "#a78bfa"
C_CYAN = "#22d3ee"


def _dlr(v):
    return f"${v:,.2f}"


def _pct_val(v):
    c = C_GREEN if v >= 0 else C_RED
    s = "+" if v >= 0 else ""
    a = "^" if v >= 0 else "v"
    return (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
        f'background:{c}1a;color:{c};font-weight:700;font-size:11px;">'
        f'{a} {s}{v:.2f}%</span>'
    )


def _clr(v):
    return C_GREEN if v >= 0 else C_RED


def _sig(s):
    if "BUY" in s.upper():
        bg, c = C_GREEN + "1a", C_GREEN
    elif "SELL" in s.upper():
        bg, c = C_RED + "1a", C_RED
    elif "TRIM" in s.upper():
        bg, c = C_AMBER + "1a", C_AMBER
    elif "WATCH" in s.upper():
        bg, c = C_AMBER + "1a", C_AMBER
    elif "ERROR" in s.upper():
        bg, c = C_RED + "1a", C_RED
    else:
        bg, c = C_TEXT + "1a", C_TEXT
    return (
        f'<span style="display:inline-block;padding:3px 12px;border-radius:4px;'
        f'background:{bg};color:{c};font-weight:700;font-size:11px;">{s}</span>'
    )


def _th(t):
    return (
        f'<th style="padding:8px 12px;text-align:left;color:{C_DIM};font-size:9px;'
        f'font-weight:600;text-transform:uppercase;letter-spacing:0.8px;'
        f'border-bottom:2px solid {C_BORDER};">{t}</th>'
    )


def _td(content, **kw):
    color = kw.get("color", C_TEXT)
    bold = "700" if kw.get("bold") else "400"
    sz = kw.get("size", "12px")
    return (
        f'<td style="padding:9px 12px;color:{color};font-weight:{bold};font-size:{sz};'
        f'border-bottom:1px solid {C_BORDER};">{content}</td>'
    )


def _sec(title, body):
    return (
        f'<div style="margin:18px 20px;"><div style="margin-bottom:12px;padding-bottom:7px;'
        f'border-bottom:1px solid {C_BORDER};"><span style="font-size:14px;font-weight:700;'
        f'color:{C_WHITE};letter-spacing:0.3px;">{title}</span></div>{body}</div>'
    )


def _card(body):
    return (
        f'<div style="background:{C_CARD};border:1px solid {C_BORDER};border-radius:8px;'
        f'padding:14px 16px;margin-bottom:10px;">{body}</div>'
    )


def _risk_badge(level):
    c = C_RED if level == "HIGH" else C_AMBER if level == "MEDIUM" else C_GREEN
    return (
        f'<span style="padding:2px 8px;border-radius:3px;background:{c}1a;'
        f'color:{c};font-weight:700;font-size:10px;">{level}</span>'
    )


def _safe_url(url: str) -> str:
    """Only http(s) links survive; anything else (javascript:, data:) is dropped."""
    url = (url or "").strip()
    return escape(url, quote=True) if url.lower().startswith(("http://", "https://")) else ""


def _headline_link(item: dict) -> str:
    title = escape(item.get("title", ""))
    href = _safe_url(item.get("link", ""))
    if not href:
        return title
    return f'<a href="{href}" style="color:{C_BLUE};text-decoration:none;">{title}</a>'


def _score_breakdown_html(h: dict) -> str:
    """Compact score breakdown table for email cards."""
    bd = h.get("score_breakdown", {})
    sc = h.get("score", 0)
    if not bd:
        return ""
    sc_c = C_GREEN if sc > 1 else C_RED if sc < -1 else C_AMBER
    rows = ""
    for comp, val in bd.items():
        if val == 0:
            continue
        vc = C_GREEN if val > 0 else C_RED
        label = comp.replace("_", " ").title()
        rows += (
            f'<tr><td style="padding:2px 6px;color:{C_TEXT};font-size:10px;'
            f'border-bottom:1px solid {C_BORDER};">{label}</td>'
            f'<td style="padding:2px 6px;color:{vc};font-size:10px;font-weight:700;'
            f'text-align:right;border-bottom:1px solid {C_BORDER};">{val:+.1f}</td></tr>'
        )
    if not rows:
        return ""
    return (
        f'<div style="margin-top:8px;padding:8px 10px;background:{C_ALT};border-radius:5px;">'
        f'<div style="font-size:9px;color:{C_DIM};text-transform:uppercase;margin-bottom:4px;">'
        f'Score: <span style="color:{sc_c};font-weight:700;">{sc:+.1f}</span></div>'
        f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
        f'{rows}</table></div>'
    )


def _relative_strength_html(h: dict) -> str:
    """Relative strength vs sector for email cards."""
    rs = h.get("relative_strength", {})
    if not rs or not isinstance(rs, dict):
        return ""
    val = rs.get("relative_strength", 0)
    out = rs.get("outperforming", False)
    c = C_GREEN if out else C_RED
    arrow = "+" if out else ""
    return (
        f'<div style="margin-top:4px;font-size:10px;color:{c};font-weight:600;">'
        f'vs Sector: {arrow}{val:.1f}% {"UP" if out else "DOWN"}</div>'
    )


def html_premarket(movers: list[dict]) -> str:
    """Pre-market movers section for email."""
    if not movers:
        return ""
    rows = ""
    for m in movers:
        c = C_GREEN if m["change_pct"] > 0 else C_RED
        rows += (
            f'<tr><td style="padding:6px 10px;color:{C_WHITE};font-weight:700;font-size:12px;'
            f'border-bottom:1px solid {C_BORDER};">{m["ticker"]}</td>'
            f'<td style="padding:6px 10px;color:{C_TEXT};font-size:12px;'
            f'border-bottom:1px solid {C_BORDER};">{_dlr(m["prev_close"])}</td>'
            f'<td style="padding:6px 10px;color:{c};font-weight:700;font-size:12px;'
            f'border-bottom:1px solid {C_BORDER};">{_dlr(m["pre_price"])}</td>'
            f'<td style="padding:6px 10px;border-bottom:1px solid {C_BORDER};">'
            f'{_pct_val(m["change_pct"])}</td></tr>'
        )
    table = (
        f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
        f'<thead><tr style="background:{C_CARD};">{_th("Ticker")}{_th("Prev Close")}'
        f'{_th("Pre-Market")}{_th("Change")}</tr></thead><tbody>{rows}</tbody></table>'
    )
    return _sec("Pre-Market Movers (>2%)", table)


def html_weekly_recap(spy_7d: float, returns: list[tuple[str, float]]) -> str:
    """Friday recap: each holding's 7-day return and its spread versus SPY."""
    if not returns:
        return ""
    rows = ""
    for tk, ret in returns:
        c = C_GREEN if ret > 0 else C_RED
        vs_spy = ret - spy_7d
        vs_c = C_GREEN if vs_spy > 0 else C_RED
        rows += (
            f'<tr><td style="padding:6px 10px;color:{C_WHITE};font-weight:700;'
            f'border-bottom:1px solid {C_BORDER};">{escape(tk)}</td>'
            f'<td style="padding:6px 10px;color:{c};font-weight:700;'
            f'border-bottom:1px solid {C_BORDER};">{ret:+.2f}%</td>'
            f'<td style="padding:6px 10px;color:{vs_c};font-weight:700;'
            f'border-bottom:1px solid {C_BORDER};">{vs_spy:+.2f}%</td></tr>'
        )
    best_tk, best_ret = max(returns, key=lambda x: x[1])
    worst_tk, worst_ret = min(returns, key=lambda x: x[1])
    summary = (
        f'<div style="margin-bottom:10px;font-size:11px;color:{C_TEXT};line-height:1.6;">'
        f'SPY 7-Day: <span style="color:{C_GREEN if spy_7d > 0 else C_RED};font-weight:700;">{spy_7d:+.2f}%</span>'
        f' | Best: <span style="color:{C_GREEN};font-weight:700;">{escape(best_tk)} ({best_ret:+.2f}%)</span>'
        f' | Worst: <span style="color:{C_RED};font-weight:700;">{escape(worst_tk)} ({worst_ret:+.2f}%)</span></div>'
    )
    table = (
        f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
        f'<thead><tr style="background:{C_CARD};">{_th("Ticker")}{_th("7-Day Return")}'
        f'{_th("vs SPY")}</tr></thead><tbody>{rows}</tbody></table>'
    )
    return _sec("Weekly Recap", summary + table)


def html_header(sp, today_str, now_str):
    mood_c = C_GREEN if sp["spy_mood"] == "Bullish" else C_RED if sp["spy_mood"] == "Bearish" else C_AMBER
    return f"""
    <div style="background:linear-gradient(135deg,#141821,#1a2332);border-radius:12px 12px 0 0;
                padding:24px 20px;border-bottom:2px solid {C_AMBER};">
      <table width="100%" cellpadding="0" cellspacing="0"><tr>
        <td><div style="font-size:19px;font-weight:800;color:{C_WHITE};">Stock Analyst</div>
            <div style="font-size:10px;color:{C_DIM};margin-top:2px;">DAILY MARKET REPORT</div></td>
        <td style="text-align:right;">
            <div style="font-size:12px;color:{C_TEXT};font-weight:600;">{today_str}</div>
            <div style="font-size:10px;color:{C_DIM};">Generated at {now_str}</div></td>
      </tr></table>
      <div style="margin-top:12px;padding-top:10px;border-top:1px solid {C_BORDER};">
        <span style="color:{C_DIM};font-size:10px;">S&amp;P 500</span>
        <span style="color:{C_WHITE};font-weight:700;font-size:15px;margin-left:6px;">{_dlr(sp['price'])}</span>
        &ensp;{_pct_val(sp['change'])}
        <span style="margin-left:16px;color:{C_DIM};font-size:10px;">SPY RSI</span>
        <span style="color:{mood_c};font-weight:700;font-size:12px;margin-left:4px;">{sp['spy_mood']}</span>
        <span style="color:{C_DIM};font-size:10px;margin-left:2px;">({sp['spy_rsi']:.0f})</span>
      </div>
    </div>"""


def html_macro(macro):
    rows = ""
    for h in macro["headlines"][:6]:
        pub = f' <span style="color:{C_DIM};">-- {escape(h["publisher"])}</span>' if h["publisher"] else ""
        rows += f'<div style="padding:4px 0;border-bottom:1px solid {C_BORDER};font-size:11px;color:{C_TEXT};">{_headline_link(h)}{pub}</div>'
    risk_rows = ""
    if macro["risks"]:
        for r in macro["risks"]:
            risk_rows += f'<tr><td style="padding:6px 10px;color:{C_WHITE};font-weight:600;font-size:12px;border-bottom:1px solid {C_BORDER};">{r["ticker"]}</td><td style="padding:6px 10px;border-bottom:1px solid {C_BORDER};">{_risk_badge(r["level"])}</td><td style="padding:6px 10px;color:{C_TEXT};font-size:11px;border-bottom:1px solid {C_BORDER};">{r["reason"]} (keyword: {r["keyword"]})</td></tr>'
        risk_rows = f'<div style="margin-top:10px;"><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px;">Portfolio Risk Flags</div><table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;"><thead><tr>{_th("Ticker")}{_th("Risk")}{_th("Reason")}</tr></thead><tbody>{risk_rows}</tbody></table></div>'
    return _sec("Macro & Political Risk", rows + risk_rows)


def html_catalysts(cats):
    if not cats:
        return _sec(
            "This Week's Catalysts",
            f'<div style="color:{C_DIM};font-size:11px;">No major earnings this week for your watchlist.</div>',
        )
    rows = ""
    for c in cats:
        d = c["date"].strftime("%b %d") if c["date"] else "TBD"
        eps = f"est EPS: ${c['eps_est']:.2f}" if c["eps_est"] else "est EPS: N/A"
        clr = C_AMBER if c["days"] <= 3 else C_TEXT
        rows += f'<div style="padding:5px 0;border-bottom:1px solid {C_BORDER};font-size:12px;"><span style="color:{C_WHITE};font-weight:700;">{c["ticker"]}</span> <span style="color:{clr};"> -- reports {d} ({eps})</span></div>'
    return _sec("This Week's Catalysts", rows)


def html_portfolio(holdings):
    if not holdings:
        return ""
    tv = sum(h["market_value"] for h in holdings)
    tc = sum(h["total_cost"] for h in holdings)
    tp = tv - tc
    tpct = tp / tc * 100 if tc else 0
    td = sum(h["day_pnl"] for h in holdings)
    summary = f'''<div style="background:{C_ALT};border-radius:8px;padding:14px 16px;margin-bottom:14px;border:1px solid {C_BORDER};">
      <table width="100%" cellpadding="0" cellspacing="0"><tr>
        <td style="text-align:center;width:25%;"><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;letter-spacing:0.8px;">Total Value</div><div style="font-size:16px;font-weight:700;color:{C_WHITE};">{_dlr(tv)}</div></td>
        <td style="text-align:center;width:25%;border-left:1px solid {C_BORDER};"><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;letter-spacing:0.8px;">Total Cost</div><div style="font-size:16px;font-weight:700;color:{C_TEXT};">{_dlr(tc)}</div></td>
        <td style="text-align:center;width:25%;border-left:1px solid {C_BORDER};"><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;letter-spacing:0.8px;">Open P&amp;L</div><div style="font-size:16px;font-weight:700;color:{_clr(tp)};"> {"+" if tp >= 0 else ""}{_dlr(tp)}</div>{_pct_val(tpct)}</td>
        <td style="text-align:center;width:25%;border-left:1px solid {C_BORDER};"><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;letter-spacing:0.8px;">Today</div><div style="font-size:16px;font-weight:700;color:{_clr(td)};">{"+" if td >= 0 else ""}{_dlr(td)}</div></td>
      </tr></table></div>'''

    cards = ""
    for h in holdings:
        t = h["tech"]
        e = h["earn"]
        a = h["analyst"]
        tl = h["timeline"]
        pe_s = f'{h["pe"]:.1f}' if h["pe"] else "N/A"
        rsi_s = f'{t["rsi"]:.0f} ({t["rsi_label"]})' if t["rsi"] else "N/A"
        earn_s = ""
        if e.get("days_to_earnings") is not None:
            ec = C_AMBER if e["days_to_earnings"] <= 7 else C_DIM
            earn_s = f'<span style="color:{ec};">Earnings in {e["days_to_earnings"]}d ({e["next_earnings"].strftime("%b %d") if e["next_earnings"] else "TBD"})</span>'
        if e.get("last_eps_actual") is not None:
            earn_s += (
                f' | Last Q: ${e["last_eps_actual"]:.2f} vs ${e["last_eps_est"]:.2f}' if e.get("last_eps_est") else ""
            )
            if e.get("last_surprise_pct") is not None:
                sc = C_GREEN if e["last_surprise_pct"] >= 0 else C_RED
                earn_s += f' (<span style="color:{sc};">{e["last_surprise_pct"]:+.1f}%</span>)'
        analyst_s = f'{a["rec_buy"]} Buy | {a["rec_hold"]} Hold | {a["rec_sell"]} Sell'
        tgt_s = ""
        if a["target_mean"]:
            tgt_s = f'Target: ${a["target_low"]:.0f} / ${a["target_mean"]:.0f} / ${a["target_high"]:.0f}'
        insider_s = f'Insider: {a["insider_buys"]} buys / {a["insider_sells"]} sells (30d)'
        news_data = h.get("news", {})
        news_items = news_data.get("headlines", []) if isinstance(news_data, dict) else news_data
        sent_score = news_data.get("sentiment_score", 0) if isinstance(news_data, dict) else 0
        sent_c = C_GREEN if sent_score > 0.3 else C_RED if sent_score < -0.3 else C_DIM
        sent_lbl = "Bullish" if sent_score > 0.3 else "Bearish" if sent_score < -0.3 else "Neutral"
        news_h = f'<div style="padding:3px 0;font-size:10px;"><span style="color:{sent_c};font-weight:700;">News Sentiment: {sent_lbl} ({sent_score:+.2f})</span></div>'
        for n in news_items[:3]:
            news_h += f'<div style="padding:3px 0;font-size:10px;color:{C_TEXT};border-bottom:1px solid {C_BORDER};">{_headline_link(n)}</div>'

        cards += f'''<div style="background:{C_CARD};border:1px solid {C_BORDER};border-radius:8px;padding:16px;margin-bottom:12px;">
          <table width="100%" cellpadding="0" cellspacing="0"><tr>
            <td><span style="font-size:16px;font-weight:800;color:{C_WHITE};">{h["ticker"]}</span>
                <span style="font-size:11px;color:{C_DIM};margin-left:6px;">{escape(h["name"])}</span></td>
            <td style="text-align:right;">{_sig(h["signal"])}</td></tr></table>
          <div style="font-size:10px;color:{C_DIM};margin-top:4px;font-style:italic;">{escape(h["reason"])}</div>
          <div style="font-size:11px;color:{C_AMBER};margin-top:3px;font-weight:600;">Action: {h["action"]}</div>
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:10px;"><tr>
            <td style="width:14%;padding:4px;"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">Price</div><div style="font-size:13px;font-weight:700;color:{C_WHITE};">{_dlr(h["current_price"])}</div></td>
            <td style="width:14%;padding:4px;"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">Avg Cost</div><div style="font-size:13px;font-weight:700;color:{C_TEXT};">{_dlr(h["avg_cost"])}</div></td>
            <td style="width:10%;padding:4px;"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">Shares</div><div style="font-size:13px;font-weight:700;color:{C_WHITE};">{h["shares"]}</div></td>
            <td style="width:10%;padding:4px;"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">PE</div><div style="font-size:13px;font-weight:700;color:{C_AMBER};">{pe_s}</div></td>
            <td style="width:14%;padding:4px;"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">RSI</div><div style="font-size:13px;font-weight:700;color:{C_WHITE};">{rsi_s}</div></td>
            <td style="width:14%;padding:4px;"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">Open P&L</div><div style="font-size:13px;font-weight:700;color:{_clr(h["open_pnl"])};">{"+" if h["open_pnl"] >= 0 else ""}{_dlr(h["open_pnl"])}</div>{_pct_val(h["open_pnl_pct"])}</td>
            <td style="width:14%;padding:4px;"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">Day P&L</div><div style="font-size:13px;font-weight:700;color:{_clr(h["day_pnl"])};">{"+" if h["day_pnl"] >= 0 else ""}{_dlr(h["day_pnl"])}</div>{_pct_val(h["day_pnl_pct"])}</td>
          </tr></table>
          <div style="margin-top:8px;padding:8px 10px;background:{C_ALT};border-radius:5px;font-size:10px;color:{C_TEXT};line-height:1.6;">
            {earn_s}<br>Analyst: {analyst_s} {tgt_s}<br>{insider_s}
          </div>
          {_score_breakdown_html(h)}
          {_relative_strength_html(h)}
          <div style="margin-top:8px;padding:8px 10px;background:{C_ALT};border-radius:5px;font-size:10px;line-height:1.6;">
            <div style="color:{C_CYAN};font-weight:600;">Short-term (0-30d):</div><div style="color:{C_TEXT};">{tl["short_level"]}<br>{tl["short_trigger"]}</div>
            <div style="color:{C_CYAN};font-weight:600;margin-top:4px;">Medium-term (1-6mo):</div><div style="color:{C_TEXT};">{tl["med_catalyst"]}<br>{tl["med_target"]}</div>
            <div style="color:{C_CYAN};font-weight:600;margin-top:4px;">Long-term (6-24mo):</div><div style="color:{C_TEXT};">{tl["long_thesis"]}<br>Invalidate: {tl["long_invalidate"]}</div>
          </div>
          {f'<div style="margin-top:6px;">{news_h}</div>' if news_h else ""}
        </div>'''
    return _sec("Your Portfolio", summary + cards)


def html_picks(picks, title):
    if not picks:
        return _sec(title, f'<div style="color:{C_DIM};font-size:11px;">No picks today.</div>')
    cards = ""
    for p in picks:
        st_clr = C_GREEN if p["status"] == "ACTIVE" else C_AMBER
        t = p.get("tech", {})
        rsi_s = f'RSI {t["rsi"]:.0f}' if t.get("rsi") else ""
        macd_s = t.get("macd_label", "")
        ema_s = t.get("ema_label", "")
        earn_s = ""
        if p.get("earn", {}).get("days_to_earnings") is not None:
            d = p["earn"]["days_to_earnings"]
            earn_s = f'Earnings in {d}d' if d >= 0 else ""
        p_news = p.get("news", {})
        p_news_items = p_news.get("headlines", []) if isinstance(p_news, dict) else p_news
        news_h = ""
        for n in p_news_items[:2]:
            news_h += f'<div style="padding:2px 0;font-size:10px;color:{C_TEXT};">{_headline_link(n)}</div>'

        cards += f'''<div style="background:{C_CARD};border:1px solid {C_BORDER};border-radius:8px;padding:14px 16px;margin-bottom:10px;">
          <table width="100%" cellpadding="0" cellspacing="0"><tr>
            <td><span style="font-size:15px;font-weight:700;color:{C_WHITE};">{p["ticker"]}</span>
                <span style="font-size:11px;color:{C_DIM};margin-left:6px;">{escape(p["name"])}</span></td>
            <td style="text-align:right;">
              <span style="font-size:13px;font-weight:700;color:{C_WHITE};">{_dlr(p["current_price"])}</span>
              &ensp;{_pct_val(p["day_chg"])}
              <span style="font-size:9px;font-weight:700;color:{st_clr};padding:2px 6px;border-radius:3px;background:{st_clr}1a;margin-left:6px;">{p["status"]}</span>
            </td></tr></table>
          <div style="margin-top:6px;padding:6px 10px;background:{C_PURPLE}15;border-radius:4px;font-size:11px;color:{C_PURPLE};font-weight:600;">
            Strategy: {p["strategy_name"]}</div>
          <div style="font-size:11px;color:{C_TEXT};margin-top:6px;line-height:1.5;">{escape(p["reason"])}</div>
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:8px;background:{C_ALT};border-radius:5px;">
            <tr>
              <td style="padding:7px 12px;text-align:center;width:20%;"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">Entry</div><div style="font-size:13px;font-weight:700;color:{C_BLUE};">{_dlr(p["entry"])}</div></td>
              <td style="padding:7px 12px;text-align:center;width:20%;border-left:1px solid {C_BORDER};"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">Target</div><div style="font-size:13px;font-weight:700;color:{C_GREEN};">{_dlr(p["target"])}</div></td>
              <td style="padding:7px 12px;text-align:center;width:20%;border-left:1px solid {C_BORDER};"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">Stop (ATR)</div><div style="font-size:13px;font-weight:700;color:{C_RED};">{_dlr(p["stop"])}</div></td>
              <td style="padding:7px 12px;text-align:center;width:20%;border-left:1px solid {C_BORDER};"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">R/R</div><div style="font-size:13px;font-weight:700;color:{C_WHITE};">1:{p["rr"]:.1f}</div></td>
              <td style="padding:7px 12px;text-align:center;width:20%;border-left:1px solid {C_BORDER};"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">Size</div><div style="font-size:13px;font-weight:700;color:{C_WHITE};">{p["pos_size"]} shares</div></td>
            </tr></table>
          <div style="margin-top:6px;font-size:10px;color:{C_DIM};">
            Risk: {p["risk_pct"]:.1f}% | Reward: {p["reward_pct"]:.1f}%
            &ensp;|&ensp;{rsi_s} {macd_s} {ema_s}
            {f"&ensp;|&ensp;{earn_s}" if earn_s else ""}
          </div>
          <div style="font-size:10px;color:{C_DIM};margin-top:2px;">Fill: {p["fill_window"]}</div>
          {f'<div style="margin-top:4px;">{news_h}</div>' if news_h else ""}
        </div>'''
    return _sec(title, cards)


def html_tech_snapshot(holdings, picks_m, picks_s):
    """One-row-per-ticker technical snapshot table."""
    tickers_done = set()
    rows = ""
    all_items = [(h["ticker"], h["current_price"], h["tech"]) for h in holdings]
    for p in picks_m + picks_s:
        if p["ticker"] not in [x[0] for x in all_items]:
            all_items.append((p["ticker"], p["current_price"], p.get("tech", {})))
    for tk, price, t in all_items:
        if tk in tickers_done:
            continue
        tickers_done.add(tk)
        bg = C_CARD if len(tickers_done) % 2 == 0 else C_ALT
        rsi_c = C_RED if t.get("rsi_label") == "OVERBOUGHT" else C_GREEN if t.get("rsi_label") == "OVERSOLD" else C_TEXT
        macd_c = (
            C_GREEN
            if "BULLISH" in t.get("macd_label", "")
            else C_RED
            if "BEARISH" in t.get("macd_label", "")
            else C_TEXT
        )
        ema_c = C_GREEN if t.get("ema_label") == "GOLDEN CROSS" else C_RED
        vol_c = C_AMBER if t.get("vol_label") == "HIGH VOLUME" else C_DIM
        rows += f'''<tr style="background:{bg};">
          {_td(tk, color=C_WHITE, bold=True)}
          {_td(_dlr(price), color=C_WHITE)}
          <td style="padding:9px 12px;color:{rsi_c};font-size:11px;border-bottom:1px solid {C_BORDER};">{t.get("rsi", "N/A")}</td>
          <td style="padding:9px 12px;color:{macd_c};font-size:11px;border-bottom:1px solid {C_BORDER};">{t.get("macd_label", "N/A")}</td>
          {_td(t.get("bb_label", "N/A"), size="11px")}
          <td style="padding:9px 12px;color:{ema_c};font-size:11px;border-bottom:1px solid {C_BORDER};">{t.get("ema_label", "N/A")}</td>
          <td style="padding:9px 12px;color:{vol_c};font-size:11px;border-bottom:1px solid {C_BORDER};">{t.get("vol_label", "N/A")}</td>
          {_td(_dlr(t.get("atr_stop") or 0), color=C_RED, size="11px")}
          {_td(_dlr(t.get("atr_target") or 0), color=C_GREEN, size="11px")}
        </tr>'''
    table = f'''<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
      <thead><tr style="background:{C_CARD};">{_th("Ticker")}{_th("Price")}{_th("RSI")}{_th("MACD")}{_th("BB")}{_th("EMA")}{_th("Volume")}{_th("ATR Stop")}{_th("ATR Target")}</tr></thead>
      <tbody>{rows}</tbody></table>'''
    return _sec("Technical Snapshot", table)


def html_movers(df, title):
    rows = ""
    for i, (_, r) in enumerate(df.iterrows()):
        bg = C_CARD if i % 2 == 0 else C_ALT
        rows += f'<tr style="background:{bg};">{_td(r["Ticker"], color=C_WHITE, bold=True)}{_td(_dlr(r["Previous Close"]), color=C_DIM)}<td style="padding:9px 12px;color:{_clr(r["Change %"])};font-weight:600;font-size:12px;border-bottom:1px solid {C_BORDER};">{_dlr(r["Current Price"])}</td><td style="padding:9px 12px;text-align:right;border-bottom:1px solid {C_BORDER};">{_pct_val(r["Change %"])}</td></tr>'
    table = f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;"><thead><tr style="background:{C_CARD};">{_th("Symbol")}{_th("Prev Close")}{_th("Price")}{_th("Change")}</tr></thead><tbody>{rows}</tbody></table>'
    return _sec(title, table)


def html_timeline(timeline: list[dict] = STRATEGY_TIMELINE):
    colors = [C_RED, C_AMBER, C_AMBER, C_BLUE, C_PURPLE]
    rows = ""
    for i, item in enumerate(timeline):
        bg = C_CARD if i % 2 == 0 else C_ALT
        dc = colors[i % len(colors)]
        rows += f'<tr style="background:{bg};"><td style="padding:10px 12px;border-bottom:1px solid {C_BORDER};"><span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:{dc};margin-right:6px;vertical-align:middle;"></span><span style="font-size:11px;font-weight:700;color:{dc};">{item["period"]}</span></td><td style="padding:10px 12px;font-weight:600;color:{C_WHITE};font-size:12px;border-bottom:1px solid {C_BORDER};">{item["action"]}</td><td style="padding:10px 12px;color:{C_TEXT};font-size:11px;border-bottom:1px solid {C_BORDER};">{item["detail"]}</td></tr>'
    return _sec(
        "Strategy Timeline",
        f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;"><thead><tr style="background:{C_CARD};">{_th("Period")}{_th("Action")}{_th("Detail")}</tr></thead><tbody>{rows}</tbody></table>',
    )


def html_risk(rd):
    rc = C_GREEN if rd["risk_rating"] == "LOW" else C_RED if rd["risk_rating"] == "HIGH" else C_AMBER
    summary = f'''<div style="background:{C_ALT};border-radius:8px;padding:14px 16px;margin-bottom:12px;border:1px solid {C_BORDER};">
      <table width="100%" cellpadding="0" cellspacing="0"><tr>
        <td style="text-align:center;width:33%;"><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;">Weighted Beta</div><div style="font-size:16px;font-weight:700;color:{C_WHITE};">{rd["weighted_beta"]:.2f}</div></td>
        <td style="text-align:center;width:34%;border-left:1px solid {C_BORDER};"><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;">Risk Rating</div><div style="font-size:16px;font-weight:700;color:{rc};">{rd["risk_rating"]}</div></td>
        <td style="text-align:center;width:33%;border-left:1px solid {C_BORDER};"><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;">1-Day 95% VaR</div><div style="font-size:16px;font-weight:700;color:{C_RED};">{_dlr(rd["var_95"])}</div></td>
      </tr></table></div>'''
    # Positions
    prows = ""
    for p in rd["positions"]:
        prows += f'<tr><td style="padding:7px 10px;color:{C_WHITE};font-weight:600;font-size:11px;border-bottom:1px solid {C_BORDER};">{p["ticker"]}</td><td style="padding:7px 10px;color:{C_TEXT};font-size:11px;border-bottom:1px solid {C_BORDER};">{p["weight"]:.1f}%</td><td style="padding:7px 10px;color:{C_TEXT};font-size:11px;border-bottom:1px solid {C_BORDER};">{p["beta"]:.2f}</td><td style="padding:7px 10px;color:{C_RED};font-size:11px;border-bottom:1px solid {C_BORDER};">{_dlr(p["risk_1d"])}</td></tr>'
    ptable = f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;"><thead><tr style="background:{C_CARD};">{_th("Ticker")}{_th("Weight")}{_th("Beta")}{_th("1-Day Risk")}</tr></thead><tbody>{prows}</tbody></table>'
    # Sectors
    srows = ""
    for sec, pct in sorted(rd["sectors"].items(), key=lambda x: -x[1]):
        srows += f'<tr><td style="padding:5px 10px;color:{C_TEXT};font-size:11px;border-bottom:1px solid {C_BORDER};">{sec}</td><td style="padding:5px 10px;color:{C_WHITE};font-weight:600;font-size:11px;border-bottom:1px solid {C_BORDER};">{pct:.1f}%</td></tr>'
    stable = (
        f'<div style="margin-top:10px;"><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px;">Sector Exposure</div><table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;"><tbody>{srows}</tbody></table></div>'
        if srows
        else ""
    )
    return _sec("Portfolio Risk Dashboard", summary + ptable + stable)


# =====================================================================
#  15. EMAIL ASSEMBLY & SEND
# =====================================================================
def build_html(
    sp,
    macro,
    catalysts,
    portfolio,
    picks_m,
    picks_s,
    gainers,
    losers,
    risk_d,
    premarket_movers=None,
    weekly_recap: tuple[float, list[tuple[str, float]]] | None = None,
    now: dt.datetime | None = None,
):
    """Assemble the full dark-theme report. ``weekly_recap`` is ``(spy_7d, [(ticker, ret), ...])`` on Fridays."""
    now = now or dt.datetime.now()
    today_s = now.strftime("%A, %B %d, %Y")
    now_s = now.strftime("%I:%M %p")
    pre_html = html_premarket(premarket_movers or [])
    friday_html = html_weekly_recap(*weekly_recap) if weekly_recap else ""
    return f"""<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<style>
  /* Force dark mode so Gmail/Outlook do not override it */
  :root {{ color-scheme: dark; }}
  body, div, td, th, p, span, a {{ color-scheme: dark !important; }}
  [data-ogsc] body {{ background-color: #0b0e11 !important; }}
  [data-ogsb] body {{ background-color: #0b0e11 !important; }}
  u + .body {{ background-color: #0b0e11 !important; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background-color: #0b0e11 !important; color: #d1d4dc !important; }}
    .email-wrap {{ background-color: #0b0e11 !important; }}
  }}
</style>
</head>
<body class="body" style="margin:0;padding:0;background-color:{C_BG};font-family:'SF Pro Display','Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;-webkit-font-smoothing:antialiased;">
<div style="max-width:720px;margin:0 auto;padding:20px 10px;">
  {html_header(sp, today_s, now_s)}
  <div style="background:{C_CARD};border-radius:0 0 12px 12px;padding-bottom:8px;overflow:hidden;">
    {pre_html}
    {html_macro(macro)}
    {html_catalysts(catalysts)}
    {html_portfolio(portfolio)}
    {html_picks(picks_m, "Momentum Longs (1-3 Day Horizon)")}
    {html_picks(picks_s, "Swing Trades (2-4 Week Horizon)")}
    {html_tech_snapshot(portfolio, picks_m, picks_s)}
    {html_timeline()}
    {html_risk(risk_d)}
    {html_movers(gainers, "Top 10 Gainers")}
    {html_movers(losers, "Top 10 Losers")}
    {friday_html}
    <div style="margin:20px 20px 14px;padding:12px 16px;background:{C_ALT};border-radius:8px;border:1px solid {C_BORDER};text-align:center;">
      <div style="font-size:9px;color:{C_DIM};line-height:1.6;">
        Data: Yahoo Finance | Finnhub | Finviz | Google News<br>
        Generated by <span style="color:{C_AMBER};font-weight:600;">Stock Analyst v3</span>
        &ensp;|&ensp;{now_s} &ensp;|&ensp; For educational purposes only -- Not financial advice.
      </div>
    </div>
  </div>
</div></body></html>"""


def build_plain(sp, portfolio, picks_m, picks_s, today: dt.date | None = None):
    lines = [
        f"Stock Analyst -- {today or dt.date.today()}",
        "=" * 50,
        f"S&P 500: ${sp['price']:,.2f} ({sp['change']:+.2f}%)",
        "",
    ]
    lines.append("PORTFOLIO:")
    for h in portfolio:
        lines.append(
            f"  {h['ticker']:6s} ${h['current_price']:>8.2f}  P&L {h['open_pnl_pct']:+.2f}%  -> {h['signal']}  {h['action']}"
        )
    lines += ["", "MOMENTUM PICKS:"]
    for p in picks_m:
        lines.append(
            f"  {p['ticker']:6s} ${p['current_price']:>8.2f}  Entry ${p['entry']:.2f}  Target ${p['target']:.2f}  Stop ${p['stop']:.2f}  [{p['status']}]"
        )
    lines += ["", "SWING PICKS:"]
    for p in picks_s:
        lines.append(
            f"  {p['ticker']:6s} ${p['current_price']:>8.2f}  Entry ${p['entry']:.2f}  Target ${p['target']:.2f}  Stop ${p['stop']:.2f}  [{p['status']}]"
        )
    lines += ["", "Not financial advice."]
    return "\n".join(lines)
