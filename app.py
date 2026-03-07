"""
AI Stock Analyst  --  Public Streamlit Dashboard v4
====================================================
Anyone can enter their stocks, shares, avg cost, and email.
The app generates a personalized dashboard and sends them a report.
"""

import streamlit as st
import os, datetime, smtplib
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

for _key in ("EMAIL_PASSWORD", "SENDER_EMAIL", "RECIPIENT_EMAIL", "FINNHUB_API_KEY", "ANTHROPIC_API_KEY"):
    if _key not in os.environ:
        try:
            os.environ[_key] = st.secrets[_key]
        except Exception:
            pass

from main import (
    fetch_market_summary, get_macro_news, get_weekly_catalysts,
    analyse_portfolio, enrich_picks, compute_risk_dashboard,
    compute_technicals, get_financials, compute_signal_score,
    get_earnings_info, get_analyst_data, get_ticker_news,
    _timeline_block, _action_text, get_info, get_hist,
    get_relative_strength,
    MOMENTUM_PICKS, SWING_PICKS, STRATEGY_NAMES,
    fetch_sp500_tickers, analyse_stocks, get_top_movers,
    _info_cache, _hist_cache,
)

# ═════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ═════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="AI Stock Analyst",
    page_icon="chart_with_upwards_trend",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═════════════════════════════════════════════════════════════════
#  PALETTE
# ═════════════════════════════════════════════════════════════════
BG     = "#0A0E1A"
CARD   = "#111827"
ALT    = "#1a2332"
BORDER = "#1e3a5f"
TEXT   = "#E2E8F0"
DIM    = "#6b7280"
GREEN  = "#00FF88"
RED    = "#FF4444"
AMBER  = "#FFB800"
BLUE   = "#3b82f6"
WHITE  = "#ffffff"
PURPLE = "#a78bfa"
CYAN   = "#22d3ee"

# ═════════════════════════════════════════════════════════════════
#  CSS — Finance Terminal Aesthetic
# ═════════════════════════════════════════════════════════════════
st.markdown(f"""
<style>
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}

    .stApp {{ background-color: {BG}; }}
    section[data-testid="stSidebar"] {{ background-color: {CARD}; }}
    .block-container {{ padding-top: 1rem; }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px; background-color: {CARD}; border-radius: 8px; padding: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{ border-radius: 6px; color: {DIM}; font-weight: 600; }}
    .stTabs [aria-selected="true"] {{
        background-color: {ALT} !important; color: {WHITE} !important;
    }}
    [data-testid="stMetricValue"] {{ font-size: 1.3rem; font-weight: 800; font-family: monospace; }}
    [data-testid="stMetricDelta"] {{ font-size: 0.85rem; }}

    .stock-card {{
        background: linear-gradient(135deg, {CARD} 0%, {ALT} 100%);
        border: 1px solid {BORDER};
        border-radius: 12px; padding: 20px; margin-bottom: 16px;
        box-shadow: 0 4px 24px rgba(0, 255, 136, 0.05);
    }}
    .badge {{
        display: inline-block; padding: 3px 12px; border-radius: 4px;
        font-weight: 700; font-size: 12px;
    }}
    .badge-buy   {{ background: {GREEN}1a; color: {GREEN}; }}
    .badge-sell  {{ background: {RED}1a;   color: {RED}; }}
    .badge-hold  {{ background: {AMBER}1a; color: {AMBER}; }}
    .badge-trim  {{ background: {AMBER}1a; color: {AMBER}; }}
    .badge-watch {{ background: {DIM}22;   color: {TEXT}; }}

    .signal-buy  {{ color: {GREEN}; font-weight: bold; font-size: 1.1em; }}
    .signal-sell {{ color: {RED}; font-weight: bold; font-size: 1.1em; }}
    .signal-hold {{ color: {AMBER}; font-weight: bold; font-size: 1.1em; }}
    .signal-watch {{ color: {DIM}; font-weight: bold; font-size: 1.1em; }}

    .score-bar-container {{ background: {ALT}; border-radius: 8px; height: 8px; margin: 8px 0; position: relative; }}
    .score-bar {{ height: 8px; border-radius: 8px; position: absolute; }}

    .metric-tile {{
        background: {CARD}; border: 1px solid {BORDER};
        border-radius: 8px; padding: 12px 16px; text-align: center;
    }}

    .kpi-label {{ font-size: 9px; color: {DIM}; text-transform: uppercase; letter-spacing: 0.5px; font-family: monospace; }}
    .kpi-value {{ font-size: 15px; font-weight: 700; font-family: monospace; }}
    .hero-title {{
        font-size: 36px; font-weight: 900; color: {GREEN};
        letter-spacing: -0.5px; line-height: 1.2; font-family: monospace;
    }}
    .hero-sub {{
        font-size: 16px; color: {DIM}; margin-top: 8px; line-height: 1.5;
    }}

    /* Terminal prompt effect for input page */
    .terminal-prompt {{
        font-family: 'Courier New', monospace;
        color: {GREEN};
        background: {BG};
        padding: 16px;
        border-radius: 8px;
        border: 1px solid {BORDER};
    }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
    .cursor-blink {{
        display: inline-block;
        width: 8px; height: 18px;
        background: {GREEN};
        margin-left: 4px;
        animation: blink 1s step-start infinite;
        vertical-align: text-bottom;
    }}
</style>
""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════
#  HELPERS
# ═════════════════════════════════════════════════════════════════
def dlr(v): return f"${v:,.2f}"
def pct(v): return f"{v:+.2f}%"
def clr(v): return GREEN if v >= 0 else RED

def sig_badge(sig):
    s = sig.upper()
    if "BUY" in s:   c = "buy"
    elif "SELL" in s: c = "sell"
    elif "TRIM" in s: c = "trim"
    elif "WATCH" in s: c = "watch"
    else:             c = "hold"
    return f'<span class="badge badge-{c}">{sig}</span>'

def score_bar_html(score):
    """Visual bar showing -10 to +10 composite score."""
    pct_pos = (score + 10) / 20 * 100
    c = GREEN if score > 1 else RED if score < -1 else AMBER
    return f"""
    <div class="score-bar-container">
      <div class="score-bar" style="left:0;width:{pct_pos:.0f}%;background:{c};"></div>
      <div style="position:absolute;left:50%;top:-1px;width:1px;height:10px;background:{DIM};"></div>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:9px;color:{DIM};font-family:monospace;">
      <span>-10</span>
      <span style="color:{c};font-weight:700;">{score:+.1f}</span>
      <span>+10</span>
    </div>"""

def pick_card(p):
    sc = GREEN if p["status"] == "ACTIVE" else AMBER
    t = p.get("tech", {})
    rsi_s = f'RSI {t["rsi"]:.0f}' if t.get("rsi") else ""
    macd_s = t.get("macd_label", "")
    ema_s  = t.get("ema_label", "")
    extras = " | ".join(x for x in [rsi_s, macd_s, ema_s] if x and x != "N/A")
    return f"""
    <div class="stock-card">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">
        <div>
          <span style="font-size:17px;font-weight:800;color:{GREEN};font-family:monospace;">{p["ticker"]}</span>
          <span style="font-size:12px;color:{DIM};margin-left:8px;">{p["name"]}</span>
        </div>
        <div>
          <span style="font-size:14px;font-weight:700;color:{WHITE};font-family:monospace;">{dlr(p["current_price"])}</span>
          <span style="margin-left:8px;color:{clr(p['day_chg'])};font-weight:700;">{pct(p["day_chg"])}</span>
          <span class="badge" style="margin-left:8px;background:{sc}1a;color:{sc};">{p["status"]}</span>
        </div>
      </div>
      <div style="margin-top:6px;padding:6px 10px;background:{PURPLE}15;border-radius:4px;
                  font-size:11px;color:{PURPLE};font-weight:600;">Strategy: {p["strategy_name"]}</div>
      <div style="font-size:12px;color:{TEXT};margin-top:8px;line-height:1.5;">{p["reason"]}</div>
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


def build_plotly_chart(ticker: str, tech: dict) -> go.Figure:
    """Build an interactive Plotly candlestick + RSI chart for a ticker."""
    from ta.trend import EMAIndicator
    from ta.volatility import BollingerBands
    from ta.momentum import RSIIndicator, StochRSIIndicator

    df = get_hist(ticker, "90d", "1d")
    if df.empty or len(df) < 10:
        fig = go.Figure()
        fig.add_annotation(text="Insufficient data", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(template="plotly_dark", height=400)
        return fig

    df = df.tail(60).copy()
    close = df["Close"]

    ema20 = EMAIndicator(close=close, window=min(20, len(close))).ema_indicator()
    ema50 = EMAIndicator(close=close, window=min(50, len(close))).ema_indicator()
    bb = BollingerBands(close=close, window=min(20, len(close)), window_dev=2)
    bb_upper = bb.bollinger_hband()
    bb_lower = bb.bollinger_lband()

    # VWAP
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    cum_tp_vol = (tp * df["Volume"]).cumsum()
    cum_vol = df["Volume"].cumsum()
    vwap = cum_tp_vol / cum_vol

    # RSI
    rsi = RSIIndicator(close=close, window=14).rsi()

    # Stochastic RSI
    stoch_rsi = None
    try:
        stoch_rsi = StochRSIIndicator(close=close, window=14, smooth1=3, smooth2=3).stochrsi()
    except Exception:
        pass

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=[0.7, 0.3])

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="OHLC", increasing_line_color=GREEN, decreasing_line_color=RED), row=1, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=ema20, name="EMA 20",
                             line=dict(color=BLUE, width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=ema50, name="EMA 50",
                             line=dict(color="#FF8800", width=1)), row=1, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=bb_upper, name="BB Upper",
                             line=dict(color="rgba(150,150,150,0.3)", width=1), showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=bb_lower, name="BB Band",
                             line=dict(color="rgba(150,150,150,0.3)", width=1),
                             fill="tonexty", fillcolor="rgba(150,150,150,0.08)"), row=1, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=vwap, name="VWAP",
                             line=dict(color=AMBER, width=1, dash="dash")), row=1, col=1)

    # Support / Resistance lines
    if tech.get("support"):
        fig.add_hline(y=tech["support"], line_dash="dot", line_color=GREEN, opacity=0.5,
                      annotation_text=f"Support ${tech['support']}", row=1, col=1)
    if tech.get("resistance"):
        fig.add_hline(y=tech["resistance"], line_dash="dot", line_color=RED, opacity=0.5,
                      annotation_text=f"Resistance ${tech['resistance']}", row=1, col=1)

    # RSI subplot
    fig.add_trace(go.Scatter(x=df.index, y=rsi, name="RSI",
                             line=dict(color=CYAN, width=1.5)), row=2, col=1)
    if stoch_rsi is not None:
        fig.add_trace(go.Scatter(x=df.index, y=stoch_rsi * 100, name="StochRSI",
                                 line=dict(color=PURPLE, width=1)), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color=RED, opacity=0.4, row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color=GREEN, opacity=0.4, row=2, col=1)
    fig.add_hrect(y0=70, y1=100, fillcolor=RED, opacity=0.05, row=2, col=1)
    fig.add_hrect(y0=0, y1=30, fillcolor=GREEN, opacity=0.05, row=2, col=1)

    fig.update_layout(
        template="plotly_dark",
        title=f"{ticker} — Last 60 Days",
        height=500,
        margin=dict(l=50, r=20, t=40, b=20),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        paper_bgcolor=BG,
        plot_bgcolor=CARD,
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="RSI", row=2, col=1, range=[0, 100])

    return fig


# ═════════════════════════════════════════════════════════════════
#  CUSTOM PORTFOLIO ANALYSIS (for user-entered stocks)
# ═════════════════════════════════════════════════════════════════
def analyse_user_portfolio(portfolio: list[dict]) -> list[dict]:
    """Same pipeline as main.py but works for any user's stocks with composite scoring."""
    results = []
    for pos in portfolio:
        tk, shares, avg = pos["ticker"].upper().strip(), pos["shares"], pos["avg_cost"]
        info = get_info(tk)
        cur = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        prev = info.get("previousClose") or info.get("regularMarketPreviousClose") or 0
        pe = info.get("trailingPE") or info.get("forwardPE")
        name = info.get("shortName") or info.get("longName") or tk
        hi52 = info.get("fiftyTwoWeekHigh")
        lo52 = info.get("fiftyTwoWeekLow")
        mcap_r = info.get("marketCap")

        tc = shares * avg; mv = shares * cur
        opnl = mv - tc; opnl_p = (cur - avg) / avg * 100 if avg else 0
        dpnl = (cur - prev) * shares if prev else 0
        dpnl_p = (cur - prev) / prev * 100 if prev else 0
        rng = (cur - lo52) / (hi52 - lo52) * 100 if hi52 and lo52 and hi52 != lo52 else None

        if mcap_r and mcap_r >= 1e12: mcap = f"${mcap_r/1e12:.2f}T"
        elif mcap_r and mcap_r >= 1e9: mcap = f"${mcap_r/1e9:.2f}B"
        elif mcap_r and mcap_r >= 1e6: mcap = f"${mcap_r/1e6:.1f}M"
        else: mcap = "N/A"

        tech = compute_technicals(tk)
        fins = get_financials(tk)
        earn = get_earnings_info(tk)
        anly = get_analyst_data(tk)
        news = get_ticker_news(tk)
        rel_str = get_relative_strength(tk)

        scoring = compute_signal_score(
            tk, tech, fins, anly, news,
            price=cur, pnl=opnl_p, day_chg=dpnl_p, hi52=hi52)
        sig = scoring["signal"]
        reason = scoring["reasoning"]

        timeline = _timeline_block(tk, cur, tech, earn)
        action = _action_text(sig, {"shares": shares, "current_price": cur})

        results.append({
            "ticker": tk, "name": name, "shares": shares, "avg_cost": avg,
            "current_price": round(cur, 2), "prev_close": round(prev, 2),
            "total_cost": round(tc, 2), "market_value": round(mv, 2),
            "open_pnl": round(opnl, 2), "open_pnl_pct": round(opnl_p, 2),
            "day_pnl": round(dpnl, 2), "day_pnl_pct": round(dpnl_p, 2),
            "pe": round(pe, 2) if pe else None, "market_cap": mcap,
            "hi52": round(hi52, 2) if hi52 else None,
            "lo52": round(lo52, 2) if lo52 else None,
            "range_pct": round(rng, 1) if rng is not None else None,
            "signal": sig, "reason": reason, "action": action,
            "score": scoring["score"], "score_breakdown": scoring["breakdown"],
            "strategy": "", "tech": tech, "fins": fins, "earn": earn,
            "analyst": anly, "news": news, "timeline": timeline,
            "relative_strength": rel_str,
        })
    return results


def send_user_email(recipient: str, holdings: list[dict], risk_d: dict,
                    sp: dict, picks_m: list, picks_s: list):
    """Build and send a full report email matching the dashboard."""
    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("EMAIL_PASSWORD")
    if not sender or not password:
        return False, "EMAIL_PASSWORD or SENDER_EMAIL not configured in Streamlit secrets"

    today_s = datetime.date.today().strftime("%A, %B %d, %Y")
    now_s = datetime.datetime.now().strftime("%I:%M %p")

    B = "#0b0e11"; C = "#141821"; A = "#1a1f2b"; BD = "#1e2533"
    T = "#d1d4dc"; D = "#6b7280"; G = "#00d26a"; R = "#f6465d"
    AM = "#f0b90b"; W = "#ffffff"; CY = "#22d3ee"; PU = "#a78bfa"; BL = "#3b82f6"

    def ec(v): return G if v >= 0 else R
    def ep(v): return f'<span style="color:{ec(v)};font-weight:700;">{"+" if v>=0 else ""}{v:.2f}%</span>'
    def kpi(label, val, color=W):
        return (f'<td style="padding:8px 12px;text-align:center;"><div style="font-size:9px;color:{D};'
                f'text-transform:uppercase;letter-spacing:.5px;">{label}</div>'
                f'<div style="font-size:14px;font-weight:700;color:{color};">{val}</div></td>')
    def sig_html(sig):
        if "BUY" in sig.upper(): sc = G
        elif "SELL" in sig.upper(): sc = R
        elif "TRIM" in sig.upper() or "WATCH" in sig.upper(): sc = AM
        else: sc = D
        return (f'<span style="padding:3px 12px;border-radius:4px;background:{sc}1a;'
                f'color:{sc};font-weight:700;font-size:11px;">{sig}</span>')

    tv = sum(h["market_value"] for h in holdings)
    tc = sum(h["total_cost"] for h in holdings)
    tp = tv - tc; tpct = tp / tc * 100 if tc else 0
    tdp = sum(h["day_pnl"] for h in holdings)

    mood_c = G if sp.get("spy_mood") == "Bullish" else R if sp.get("spy_mood") == "Bearish" else AM

    cards = ""
    for h in holdings:
        t = h.get("tech", {}); e = h.get("earn", {}); a = h.get("analyst", {})
        tl = h.get("timeline", {})
        pe_s = f'{h["pe"]:.1f}' if h.get("pe") else "N/A"
        rsi_s = f'{t["rsi"]:.0f} ({t["rsi_label"]})' if t.get("rsi") else "N/A"

        info_parts = []
        if e.get("days_to_earnings") is not None:
            info_parts.append(f'Earnings in {e["days_to_earnings"]}d'
                + (f' ({e["next_earnings"].strftime("%b %d")})' if e.get("next_earnings") else ""))
        info_parts.append(f'Analyst: {a.get("rec_buy",0)} Buy / {a.get("rec_hold",0)} Hold / {a.get("rec_sell",0)} Sell')
        if a.get("target_mean"):
            info_parts.append(f'Target: ${a["target_low"]:.0f} / ${a["target_mean"]:.0f} / ${a["target_high"]:.0f}')
        info_parts.append(f'Insider (30d): {a.get("insider_buys",0)} buys / {a.get("insider_sells",0)} sells')

        # Sentiment
        news_data = h.get("news", {})
        sent = news_data.get("sentiment_score", 0) if isinstance(news_data, dict) else 0
        sent_c = G if sent > 0.3 else R if sent < -0.3 else D
        sent_lbl = "Bullish" if sent > 0.3 else "Bearish" if sent < -0.3 else "Neutral"

        # Score breakdown
        bd = h.get("score_breakdown", {})
        sc = h.get("score", 0)
        sc_c = G if sc > 1 else R if sc < -1 else AM
        bd_rows = ""
        for comp, val in bd.items():
            if val == 0: continue
            vc = G if val > 0 else R
            bd_rows += f'<tr><td style="padding:2px 6px;color:{T};font-size:10px;">{comp.replace("_"," ").title()}</td><td style="padding:2px 6px;color:{vc};font-size:10px;font-weight:700;text-align:right;">{val:+.1f}</td></tr>'

        # Relative strength
        rs = h.get("relative_strength", {})
        rs_val = rs.get("relative_strength", 0) if rs else 0
        rs_out = rs.get("outperforming", False) if rs else False
        rs_c = G if rs_out else R

        cards += f"""
        <div style="background:{C};border:1px solid {BD};border-radius:10px;padding:18px 22px;margin-bottom:14px;">
          <table width="100%" cellpadding="0" cellspacing="0"><tr>
            <td style="padding:0;"><span style="font-size:18px;font-weight:800;color:{W};">{h["ticker"]}</span>
              <span style="font-size:12px;color:{D};margin-left:8px;">{h["name"]}</span></td>
            <td style="padding:0;text-align:right;">{sig_html(h["signal"])}
              <span style="margin-left:8px;font-size:11px;color:{sc_c};font-weight:700;">Score: {sc:+.1f}</span></td>
          </tr></table>
          <div style="font-size:11px;color:{D};margin-top:4px;font-style:italic;">{h["reason"]}</div>
          <div style="font-size:12px;color:{AM};margin-top:4px;font-weight:600;">Action: {h["action"]}</div>
          <div style="margin-top:4px;font-size:10px;color:{sent_c};font-weight:600;">News Sentiment: {sent_lbl} ({sent:+.2f})</div>
          <div style="margin-top:4px;font-size:10px;color:{rs_c};font-weight:600;">vs Sector: {"+" if rs_out else ""}{rs_val:.1f}%</div>

          <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px;background:{A};border-radius:6px;">
            <tr>
              {kpi("Price", f'${h["current_price"]:,.2f}', W)}
              {kpi("Avg Cost", f'${h["avg_cost"]:,.2f}', T)}
              {kpi("Shares", int(h["shares"]), W)}
              {kpi("PE", pe_s, AM)}
              {kpi("RSI", rsi_s, W)}
            </tr>
          </table>

          <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:6px;background:{A};border-radius:6px;">
            <tr>
              {kpi("Open P&L", f'{"+" if h["open_pnl"]>=0 else ""}${h["open_pnl"]:,.2f}', ec(h["open_pnl"]))}
              {kpi("Open P&L %", f'{"+" if h["open_pnl_pct"]>=0 else ""}{h["open_pnl_pct"]:.2f}%', ec(h["open_pnl_pct"]))}
              {kpi("Day P&L", f'{"+" if h["day_pnl"]>=0 else ""}${h["day_pnl"]:,.2f}', ec(h["day_pnl"]))}
              {kpi("Day P&L %", f'{"+" if h["day_pnl_pct"]>=0 else ""}{h["day_pnl_pct"]:.2f}%', ec(h["day_pnl_pct"]))}
            </tr>
          </table>

          <div style="margin-top:10px;padding:10px 14px;background:{A};border-radius:6px;
                      font-size:11px;color:{T};line-height:1.7;">
            {"<br>".join(info_parts)}
          </div>

          {"" if not bd_rows else f'<div style="margin-top:8px;padding:8px 10px;background:{A};border-radius:5px;"><div style="font-size:9px;color:{D};margin-bottom:4px;">SCORE BREAKDOWN</div><table width="100%" cellpadding="0" cellspacing="0">{bd_rows}</table></div>'}

          <div style="margin-top:10px;padding:10px 14px;background:{A};border-radius:6px;font-size:11px;line-height:1.7;">
            <div style="color:{CY};font-weight:600;">Short-term (0-30d):</div>
            <div style="color:{T};">{tl.get("short_level","N/A")}<br>{tl.get("short_trigger","")}</div>
            <div style="color:{CY};font-weight:600;margin-top:4px;">Medium-term (1-6mo):</div>
            <div style="color:{T};">{tl.get("med_catalyst","N/A")}<br>{tl.get("med_target","")}</div>
            <div style="color:{CY};font-weight:600;margin-top:4px;">Long-term (6-24mo):</div>
            <div style="color:{T};">{tl.get("long_thesis","N/A")}<br>Invalidate: {tl.get("long_invalidate","N/A")}</div>
          </div>
        </div>"""

    tech_rows = ""
    for h in holdings:
        t = h.get("tech", {})
        tech_rows += f"""<tr style="background:{C};">
          <td style="padding:8px 10px;color:{W};font-weight:700;border-bottom:1px solid {BD};">{h["ticker"]}</td>
          <td style="padding:8px 10px;color:{W};border-bottom:1px solid {BD};">${h["current_price"]:,.2f}</td>
          <td style="padding:8px 10px;color:{T};border-bottom:1px solid {BD};">{f'{t["rsi"]:.0f}' if t.get("rsi") else "N/A"}</td>
          <td style="padding:8px 10px;color:{T};border-bottom:1px solid {BD};">{t.get("rsi_label","N/A")}</td>
          <td style="padding:8px 10px;color:{T};border-bottom:1px solid {BD};">{t.get("macd_label","N/A")}</td>
          <td style="padding:8px 10px;color:{T};border-bottom:1px solid {BD};">{t.get("bb_label","N/A")}</td>
          <td style="padding:8px 10px;color:{T};border-bottom:1px solid {BD};">{t.get("ema_label","N/A")}</td>
          <td style="padding:8px 10px;color:{T};border-bottom:1px solid {BD};">{t.get("vol_label","N/A")}</td>
        </tr>"""

    risk_rows = ""
    for p in risk_d.get("positions", []):
        risk_rows += f"""<tr style="background:{C};">
          <td style="padding:6px 10px;color:{W};font-weight:700;border-bottom:1px solid {BD};">{p["ticker"]}</td>
          <td style="padding:6px 10px;color:{T};border-bottom:1px solid {BD};">{p["weight"]:.1f}%</td>
          <td style="padding:6px 10px;color:{T};border-bottom:1px solid {BD};">{p["beta"]:.2f}</td>
          <td style="padding:6px 10px;color:{R};border-bottom:1px solid {BD};">${p["risk_1d"]:,.2f}</td>
        </tr>"""

    sector_html = ""
    for sec, exp in sorted(risk_d.get("sectors", {}).items(), key=lambda x: -x[1]):
        sector_html += f'<span style="display:inline-block;margin:2px 6px 2px 0;padding:3px 10px;background:{A};border-radius:4px;font-size:11px;color:{T};">{sec} {exp:.1f}%</span>'

    html = f"""<html><head><meta charset="utf-8"></head>
    <body style="margin:0;padding:0;background:{B};font-family:'Segoe UI',Arial,sans-serif;">
    <div style="max-width:700px;margin:0 auto;padding:20px;">
      <div style="background:linear-gradient(135deg,{C},{A});border-radius:12px;padding:20px 24px;
                  margin-bottom:16px;border:1px solid {BD};">
        <table width="100%" cellpadding="0" cellspacing="0"><tr>
          <td style="padding:0;">
            <div style="font-size:22px;font-weight:800;color:{W};">AI Stock Analyst</div>
            <div style="font-size:11px;color:{D};margin-top:2px;">{today_s} | {now_s}</div>
          </td>
          <td style="padding:0;text-align:right;">
            <div style="color:{D};font-size:11px;">S&amp;P 500</div>
            <div><span style="font-size:18px;font-weight:800;color:{W};">${sp["price"]:,.2f}</span>
              {ep(sp["change"])}</div>
            <div style="font-size:11px;margin-top:2px;">
              <span style="color:{D};">SPY</span>
              <span style="color:{mood_c};font-weight:700;margin-left:4px;">{sp.get("spy_mood","")}</span>
            </div>
          </td>
        </tr></table>
      </div>
      <div style="background:{C};border-radius:10px;padding:16px 20px;margin-bottom:16px;border:1px solid {BD};">
        <div style="font-size:13px;color:{AM};font-weight:700;margin-bottom:10px;">PORTFOLIO SUMMARY</div>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            {kpi("Value", f"${tv:,.2f}", W)}
            {kpi("Cost", f"${tc:,.2f}", T)}
            {kpi("Open P&L", f'{"+" if tp>=0 else ""}${tp:,.2f} ({tpct:+.1f}%)', ec(tp))}
            {kpi("Today P&L", f'{"+" if tdp>=0 else ""}${tdp:,.2f}', ec(tdp))}
          </tr>
        </table>
      </div>
      <div style="font-size:15px;font-weight:700;color:{W};margin-bottom:10px;">YOUR HOLDINGS</div>
      {cards}
      <div style="text-align:center;padding:16px 0;">
        <div style="font-size:10px;color:{D};">Generated by AI Stock Analyst | Not financial advice</div>
      </div>
    </div></body></html>"""

    text = f"AI Stock Analyst Report -- {today_s}\n"
    text += f"S&P 500: ${sp['price']:,.2f} ({sp['change']:+.2f}%)\n\n"
    for h in holdings:
        t = h.get("tech", {}); tl = h.get("timeline", {})
        rsi_s = f'RSI {t["rsi"]:.0f} ({t["rsi_label"]})' if t.get("rsi") else "RSI N/A"
        text += f"{'='*50}\n"
        text += f"{h['ticker']}  {h['name']}  Score: {h.get('score',0):+.1f}\n"
        text += f"  Price: ${h['current_price']:,.2f}  |  Avg: ${h['avg_cost']:,.2f}  |  Shares: {int(h['shares'])}\n"
        text += f"  Open P&L: ${h['open_pnl']:+,.2f} ({h['open_pnl_pct']:+.2f}%)\n"
        text += f"  Day P&L:  ${h['day_pnl']:+,.2f} ({h['day_pnl_pct']:+.2f}%)\n"
        text += f"  Signal: {h['signal']} -- {h['reason']}\n"
        text += f"  Action: {h['action']}\n"
        text += f"  PE: {h['pe'] or 'N/A'}  |  {rsi_s}  |  MACD: {t.get('macd_label','N/A')}\n\n"
    text += f"Risk: Beta {risk_d['weighted_beta']:.2f} | VaR ${risk_d['var_95']:,.2f} | {risk_d['risk_rating']}\n"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"AI Stock Report -- {datetime.date.today()}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    raw = msg.as_string()
    recipients = [recipient]

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as srv:
            srv.ehlo(); srv.starttls(); srv.ehlo()
            srv.login(sender, password)
            srv.sendmail(sender, recipients, raw)
        return True, None
    except Exception as exc1:
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as srv:
                srv.login(sender, password)
                srv.sendmail(sender, recipients, raw)
            return True, None
        except Exception as exc2:
            return False, f"STARTTLS: {exc1} | SSL: {exc2}"


# ═════════════════════════════════════════════════════════════════
#  CACHED DATA (shared across all users)
# ═════════════════════════════════════════════════════════════════
@st.cache_data(ttl=1800, show_spinner="Fetching market data...")
def load_market():
    return fetch_market_summary()

@st.cache_data(ttl=1800, show_spinner="Loading trade ideas...")
def load_picks():
    return enrich_picks(MOMENTUM_PICKS), enrich_picks(SWING_PICKS)

@st.cache_data(ttl=1800, show_spinner="Loading news...")
def load_news():
    return get_macro_news(), get_weekly_catalysts()

@st.cache_data(ttl=3600, show_spinner="Scanning S&P 500 (may take a few minutes)...")
def load_sp500():
    tickers = fetch_sp500_tickers()
    df = analyse_stocks(tickers)
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    return get_top_movers(df)


# ═════════════════════════════════════════════════════════════════
#  SESSION STATE
# ═════════════════════════════════════════════════════════════════
if "portfolio_submitted" not in st.session_state:
    st.session_state.portfolio_submitted = False
if "user_portfolio" not in st.session_state:
    st.session_state.user_portfolio = []
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "num_stocks" not in st.session_state:
    st.session_state.num_stocks = 1


# ═════════════════════════════════════════════════════════════════
#  SIDEBAR — always visible
# ═════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center;padding:10px 0 4px;">
      <div style="font-size:22px;font-weight:800;color:{GREEN};font-family:monospace;">AI Stock Analyst</div>
      <div style="font-size:11px;color:{DIM};margin-top:2px;font-family:monospace;">FREE PORTFOLIO ANALYZER</div>
    </div>""", unsafe_allow_html=True)
    st.markdown(
        f'<div style="text-align:center;color:{DIM};font-size:12px;font-family:monospace;">'
        f'{datetime.date.today().strftime("%A, %B %d, %Y")}</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    if st.session_state.portfolio_submitted:
        st.markdown(
            f'<div style="font-size:11px;color:{DIM};font-weight:600;'
            f'text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;font-family:monospace;">'
            f'Your Portfolio</div>',
            unsafe_allow_html=True,
        )
        for p in st.session_state.user_portfolio:
            st.markdown(
                f'<div style="padding:4px 0;font-size:13px;font-family:monospace;">'
                f'<span style="color:{GREEN};font-weight:700;">{p["ticker"]}</span>'
                f' <span style="color:{DIM};">-- {p["shares"]} @ {dlr(p["avg_cost"])}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.divider()
        if st.button("Start Over", use_container_width=True):
            st.session_state.portfolio_submitted = False
            st.session_state.user_portfolio = []
            st.session_state.user_email = ""
            _info_cache.clear()
            _hist_cache.clear()
            st.rerun()
        if st.button("Refresh Data", use_container_width=True, type="primary"):
            st.cache_data.clear()
            _info_cache.clear()
            _hist_cache.clear()
            st.rerun()
    else:
        st.markdown(
            f'<div style="font-size:12px;color:{TEXT};line-height:1.6;">'
            f'Enter your stocks on the right to get a free personalized analysis '
            f'with signals, technicals, and a full report sent to your email.'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown(f"""
    <div style="font-size:10px;color:{DIM};text-align:center;line-height:1.6;font-family:monospace;">
      Data: Yahoo Finance | Finnhub | Google News<br>Not financial advice
    </div>""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════
#  PAGE 1: INPUT FORM  (shown before submission)
# ═════════════════════════════════════════════════════════════════
if not st.session_state.portfolio_submitted:
    st.markdown(f"""
    <div style="text-align:center;margin:40px 0 20px;">
      <div class="hero-title">&gt; Get Your Free Stock Analysis<span class="cursor-blink"></span></div>
      <div class="hero-sub">
        Enter your positions below. We'll analyze every stock with<br>
        technical indicators, PE ratios, analyst ratings, news, and<br>
        send a professional report straight to your inbox.
      </div>
    </div>""", unsafe_allow_html=True)

    st.markdown("---")

    col_form, col_preview = st.columns([3, 2])

    with col_form:
        st.markdown(
            f'<div style="font-size:16px;font-weight:700;color:{GREEN};margin-bottom:12px;font-family:monospace;">'
            f'$ enter_positions</div>',
            unsafe_allow_html=True,
        )

        with st.form("portfolio_form"):
            num = st.number_input(
                "How many stocks?", min_value=1, max_value=20, value=st.session_state.num_stocks,
                key="num_input",
            )
            form_tickers = []
            for i in range(int(num)):
                st.markdown(
                    f'<div style="font-size:12px;color:{AMBER};font-weight:600;margin-top:10px;font-family:monospace;">'
                    f'Stock #{i+1}</div>',
                    unsafe_allow_html=True,
                )
                c1, c2, c3 = st.columns(3)
                ticker = c1.text_input("Ticker", key=f"ticker_{i}", placeholder="e.g. AAPL")
                shares = c2.number_input("Shares", min_value=0.0, step=1.0, key=f"shares_{i}", value=0.0)
                avg_cost = c3.number_input("Avg Cost ($)", min_value=0.0, step=0.01, key=f"avg_{i}", value=0.0)
                form_tickers.append((ticker, shares, avg_cost))

            st.markdown("---")
            user_email = st.text_input("Your Email (for the report)", placeholder="you@example.com")

            submitted = st.form_submit_button(
                "Analyze My Portfolio",
                use_container_width=True, type="primary",
            )

        if submitted:
            st.session_state.num_stocks = int(num)
            stocks_input = []
            for ticker, shares, avg_cost in form_tickers:
                tk = ticker.upper().strip()
                if tk and shares > 0 and avg_cost > 0:
                    stocks_input.append({"ticker": tk, "shares": shares, "avg_cost": avg_cost})
            if stocks_input:
                st.session_state.user_portfolio = stocks_input
                st.session_state.user_email = user_email
                st.session_state.portfolio_submitted = True
                st.rerun()
            else:
                st.error("Please enter at least one stock with shares and avg cost filled in.")

    with col_preview:
        st.markdown(
            f'<div style="font-size:16px;font-weight:700;color:{GREEN};margin-bottom:12px;font-family:monospace;">'
            f'$ what_you_get</div>',
            unsafe_allow_html=True,
        )
        features = [
            ("BUY / SELL / HOLD signals + Score", "Composite score -10 to +10 with full breakdown"),
            ("Technical Indicators", "RSI, StochRSI, MACD, Bollinger, EMA, VWAP, OBV, Support/Resistance"),
            ("Interactive Charts", "Candlestick charts with overlays and RSI subplot"),
            ("Analyst Ratings", "Buy/Hold/Sell counts + price targets from Wall Street"),
            ("Earnings Alerts", "Upcoming earnings dates with EPS estimates"),
            ("Risk Dashboard", "Portfolio beta, sector exposure, 1-day VaR"),
            ("Sector Relative Strength", "Your stock vs its sector ETF performance"),
            ("News Sentiment", "AI-powered headline sentiment scoring"),
            ("Trade Ideas", "Curated momentum and swing picks with entry/stop/target"),
            ("Email Report", "Full analysis delivered to your inbox"),
        ]
        for title, desc in features:
            st.markdown(f"""
            <div style="padding:8px 0;border-bottom:1px solid {BORDER};">
              <div style="font-size:13px;font-weight:700;color:{GREEN};">{title}</div>
              <div style="font-size:11px;color:{DIM};">{desc}</div>
            </div>""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════
#  PAGE 2: DASHBOARD  (shown after submission)
# ═════════════════════════════════════════════════════════════════
if st.session_state.portfolio_submitted:
    user_portfolio = st.session_state.user_portfolio
    user_email = st.session_state.user_email

    # ── Loading screen ──
    loading = st.empty()
    loading.markdown(f"""
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                min-height:60vh;text-align:center;">
      <style>
        @keyframes pulse-ring {{
          0% {{ transform: scale(0.8); opacity: 1; }}
          50% {{ transform: scale(1.2); opacity: 0.4; }}
          100% {{ transform: scale(0.8); opacity: 1; }}
        }}
        @keyframes bar-fill {{
          0% {{ width: 0%; }}
          20% {{ width: 25%; }}
          50% {{ width: 55%; }}
          80% {{ width: 80%; }}
          100% {{ width: 95%; }}
        }}
        .load-icon {{
          width: 80px; height: 80px; border-radius: 50%;
          background: linear-gradient(135deg, {AMBER}, {GREEN});
          display: flex; align-items: center; justify-content: center;
          animation: pulse-ring 1.5s ease-in-out infinite;
          margin-bottom: 24px;
        }}
        .load-bar-bg {{
          width: 280px; height: 6px; background: {CARD}; border-radius: 3px;
          overflow: hidden; margin-top: 20px;
        }}
        .load-bar-fill {{
          height: 100%; background: linear-gradient(90deg, {AMBER}, {GREEN});
          border-radius: 3px; animation: bar-fill 8s ease-out forwards;
        }}
      </style>
      <div class="load-icon">
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="{CARD}" stroke-width="2.5"
             stroke-linecap="round" stroke-linejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
      </div>
      <div style="font-size:22px;font-weight:800;color:{GREEN};font-family:monospace;">Analyzing Your Portfolio</div>
      <div id="load-status" style="font-size:13px;color:{DIM};margin-top:8px;">
        Fetching live market data...</div>
      <div class="load-bar-bg"><div class="load-bar-fill"></div></div>
      <div style="margin-top:24px;font-size:11px;color:{DIM};max-width:320px;line-height:1.6;">
        Computing technical indicators, fetching analyst ratings,<br>
        scanning news, and building your risk dashboard.
      </div>
    </div>""", unsafe_allow_html=True)

    sp = load_market()
    picks_m, picks_s = load_picks()
    macro, catalysts = load_news()
    holdings = analyse_user_portfolio(user_portfolio)
    risk_d = compute_risk_dashboard(holdings)

    email_sent = False
    email_error = None
    if user_email and "@" in user_email:
        email_sent, email_error = send_user_email(user_email, holdings, risk_d, sp, picks_m, picks_s)

    loading.empty()

    # ── HEADER BAR ──
    mood_c = GREEN if sp["spy_mood"] == "Bullish" else RED if sp["spy_mood"] == "Bearish" else AMBER
    mood_icon = "🟢" if sp["spy_mood"] == "Bullish" else "🔴" if sp["spy_mood"] == "Bearish" else "🟡"
    buy_count = sum(1 for h in holdings if h["signal"] == "BUY")
    tv = sum(h["market_value"] for h in holdings)
    tc = sum(h["total_cost"] for h in holdings)
    tp = tv - tc
    tpc = tp / tc * 100 if tc else 0
    tdp = sum(h["day_pnl"] for h in holdings)
    now_str = datetime.datetime.now().strftime("%I:%M %p")

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{CARD},{ALT});border-radius:12px;
                padding:16px 24px;margin-bottom:16px;border:1px solid {BORDER};
                display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
      <div>
        <span style="font-size:20px;font-weight:800;color:{GREEN};font-family:monospace;">AI Stock Analyst</span>
        <span style="font-size:11px;color:{DIM};margin-left:12px;font-family:monospace;">{now_str}</span>
      </div>
      <div style="display:flex;gap:24px;align-items:center;flex-wrap:wrap;">
        <div style="text-align:center;">
          <div style="font-size:9px;color:{DIM};text-transform:uppercase;font-family:monospace;">SPY Mood</div>
          <div style="font-size:14px;font-weight:700;color:{mood_c};">{mood_icon} {sp['spy_mood']}</div>
        </div>
        <div style="text-align:center;">
          <div style="font-size:9px;color:{DIM};text-transform:uppercase;font-family:monospace;">S&amp;P 500</div>
          <div style="font-size:14px;font-weight:700;color:{WHITE};font-family:monospace;">{dlr(sp['price'])}
            <span style="color:{clr(sp['change'])};">{pct(sp['change'])}</span></div>
        </div>
        <div style="text-align:center;">
          <div style="font-size:9px;color:{DIM};text-transform:uppercase;font-family:monospace;">BUY Signals</div>
          <div style="font-size:14px;font-weight:700;color:{GREEN};">{buy_count}</div>
        </div>
        <div style="text-align:center;">
          <div style="font-size:9px;color:{DIM};text-transform:uppercase;font-family:monospace;">Total P&amp;L</div>
          <div style="font-size:14px;font-weight:700;color:{clr(tp)};font-family:monospace;">{"+" if tp>=0 else ""}{dlr(tp)}</div>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    if email_sent:
        st.success(f"Report sent to {user_email}!")
    elif user_email:
        detail = f" ({email_error})" if email_error else ""
        st.warning(f"Could not send email{detail} -- but your dashboard is ready below.")

    # ── KPI ROW ──
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Portfolio Value", dlr(tv))
    k2.metric("Total Cost", dlr(tc))
    k3.metric("Open P&L", dlr(tp), delta=pct(tpc))
    k4.metric("Today's P&L", dlr(tdp))

    # ── TABS ──
    tab_port, tab_picks, tab_tech, tab_risk = st.tabs(
        ["Portfolio", "Trade Ideas", "Technicals", "Risk & News"]
    )

    # ──── PORTFOLIO TAB ────
    with tab_port:
        for h in holdings:
            oc = clr(h["open_pnl"]); dc = clr(h["day_pnl"])
            pe_s = f'{h["pe"]:.1f}' if h["pe"] else "N/A"
            t = h["tech"]
            rsi_s = f'{t["rsi"]:.0f} ({t["rsi_label"]})' if t.get("rsi") else "N/A"
            stoch_s = f'{t["stoch_rsi"]:.3f} ({t["stoch_rsi_label"]})' if t.get("stoch_rsi") is not None else "N/A"
            vwap_s = f'{dlr(t["vwap"])} ({t["vwap_label"]})' if t.get("vwap") else "N/A"
            tl = h["timeline"]
            e = h["earn"]; a = h["analyst"]
            fins = h.get("fins", {})
            news_data = h.get("news", {})
            sent = news_data.get("sentiment_score", 0) if isinstance(news_data, dict) else 0
            sent_c = GREEN if sent > 0.3 else RED if sent < -0.3 else DIM
            sent_lbl = "Bullish" if sent > 0.3 else "Bearish" if sent < -0.3 else "Neutral"

            rs = h.get("relative_strength", {})
            rs_val = rs.get("relative_strength", 0) if rs else 0
            rs_out = rs.get("outperforming", False) if rs else False
            rs_c = GREEN if rs_out else RED

            info_parts = []
            if e.get("days_to_earnings") is not None:
                info_parts.append(f'Earnings in {e["days_to_earnings"]}d'
                    + (f' ({e["next_earnings"].strftime("%b %d")})' if e.get("next_earnings") else ""))
            info_parts.append(f'Analyst: {a["rec_buy"]} Buy / {a["rec_hold"]} Hold / {a["rec_sell"]} Sell')
            if a.get("target_mean"):
                info_parts.append(f'Target: ${a["target_low"]:.0f} / ${a["target_mean"]:.0f} / ${a["target_high"]:.0f}')
            info_parts.append(f'Insider (30d): {a["insider_buys"]} buys / {a["insider_sells"]} sells')
            if fins.get("peg") is not None:
                info_parts.append(f'PEG: {fins["peg"]:.2f} ({fins["peg_label"]})')
            if fins.get("z_score") is not None:
                info_parts.append(f'Altman Z: {fins["z_score"]:.2f} ({fins["z_label"]})')
            if fins.get("est_revision") and fins["est_revision"] != "N/A":
                info_parts.append(f'EPS Estimates: {fins["est_revision"]}')
            info_html = "<br>".join(info_parts)

            # Stock card with two-column layout
            st.markdown(f"""
            <div class="stock-card">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;">
                <div style="flex:1;min-width:280px;">
                  <div>
                    <span style="font-size:22px;font-weight:800;color:{GREEN};font-family:monospace;">{h["ticker"]}</span>
                    <span style="font-size:12px;color:{DIM};margin-left:8px;">{h["name"]}</span>
                    <span style="margin-left:12px;">{sig_badge(h["signal"])}</span>
                  </div>
                  <div style="font-size:18px;font-weight:700;color:{WHITE};margin-top:6px;font-family:monospace;">
                    {dlr(h["current_price"])}
                    <span style="font-size:13px;color:{dc};margin-left:8px;">Day {pct(h["day_pnl_pct"])}</span>
                  </div>
                  <div style="margin-top:4px;">
                    <span style="color:{oc};font-weight:700;font-family:monospace;">P&L {"+" if h["open_pnl"]>=0 else ""}{dlr(h["open_pnl"])} ({pct(h["open_pnl_pct"])})</span>
                  </div>
                  <div style="font-size:11px;color:{DIM};margin-top:4px;font-style:italic;">{h["reason"]}</div>
                  <div style="font-size:12px;color:{AMBER};margin-top:4px;font-weight:600;">Action: {h["action"]}</div>
                  <div style="margin-top:4px;font-size:10px;color:{sent_c};font-weight:600;">News Sentiment: {sent_lbl} ({sent:+.2f})</div>
                  <div style="margin-top:2px;font-size:10px;color:{rs_c};font-weight:600;">vs Sector: {"+" if rs_out else ""}{rs_val:.1f}%</div>
                  {score_bar_html(h.get("score", 0))}
                </div>
                <div style="flex:0 0 260px;">
                  <div style="padding:10px 14px;background:{ALT};border-radius:6px;font-size:11px;line-height:1.8;font-family:monospace;">
                    <div><span style="color:{DIM};">RSI:</span> <span style="color:{WHITE};">{rsi_s}</span></div>
                    <div><span style="color:{DIM};">StochRSI:</span> <span style="color:{WHITE};">{stoch_s}</span></div>
                    <div><span style="color:{DIM};">MACD:</span> <span style="color:{WHITE};">{t.get('macd_label','N/A')}</span></div>
                    <div><span style="color:{DIM};">VWAP:</span> <span style="color:{WHITE};">{vwap_s}</span></div>
                    <div><span style="color:{DIM};">OBV:</span> <span style="color:{WHITE};">{t.get('obv_trend','N/A')}</span></div>
                    <div><span style="color:{DIM};">S/R:</span> <span style="color:{WHITE};">{t.get('sr_label','N/A')}</span></div>
                    <div><span style="color:{DIM};">Support:</span> <span style="color:{GREEN};">{dlr(t['support']) if t.get('support') else 'N/A'}</span></div>
                    <div><span style="color:{DIM};">Resist:</span> <span style="color:{RED};">{dlr(t['resistance']) if t.get('resistance') else 'N/A'}</span></div>
                    <div><span style="color:{DIM};">PE:</span> <span style="color:{AMBER};">{pe_s}</span></div>
                  </div>
                </div>
              </div>
              <div style="margin-top:10px;padding:10px 14px;background:{ALT};border-radius:6px;font-size:11px;color:{TEXT};line-height:1.7;">{info_html}</div>
              <div style="margin-top:10px;padding:10px 14px;background:{ALT};border-radius:6px;font-size:11px;line-height:1.7;">
                <div style="color:{CYAN};font-weight:600;">Short-term (0-30d):</div><div style="color:{TEXT};">{tl["short_level"]}<br>{tl["short_trigger"]}</div>
                <div style="color:{CYAN};font-weight:600;margin-top:4px;">Medium-term (1-6mo):</div><div style="color:{TEXT};">{tl["med_catalyst"]}<br>{tl["med_target"]}</div>
                <div style="color:{CYAN};font-weight:600;margin-top:4px;">Long-term (6-24mo):</div><div style="color:{TEXT};">{tl["long_thesis"]}<br>Invalidate: {tl["long_invalidate"]}</div>
              </div>
            </div>""", unsafe_allow_html=True)

            with st.expander(f"View Chart - {h['ticker']}"):
                fig = build_plotly_chart(h["ticker"], t)
                st.plotly_chart(fig, use_container_width=True, key=f"chart_port_{h['ticker']}")

    # ──── TRADE IDEAS TAB ────
    with tab_picks:
        st.markdown(f'<div style="font-size:16px;font-weight:700;color:{GREEN};margin-bottom:10px;font-family:monospace;">Momentum Longs (1-3 Day)</div>', unsafe_allow_html=True)
        for p in picks_m:
            st.markdown(pick_card(p), unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:16px;font-weight:700;color:{GREEN};margin:24px 0 10px;font-family:monospace;">Swing Trades (2-4 Week)</div>', unsafe_allow_html=True)
        for p in picks_s:
            st.markdown(pick_card(p), unsafe_allow_html=True)

    # ──── TECHNICALS TAB (interactive charts) ────
    with tab_tech:
        ticker_options = [h["ticker"] for h in holdings]
        if ticker_options:
            selected_tk = st.selectbox("Select ticker to chart", ticker_options, key="tech_chart_select")
            selected_h = next((h for h in holdings if h["ticker"] == selected_tk), None)
            if selected_h:
                fig = build_plotly_chart(selected_tk, selected_h["tech"])
                st.plotly_chart(fig, use_container_width=True, key=f"chart_tech_{selected_tk}")

                # Technical data table below chart
                t = selected_h["tech"]
                fins = selected_h.get("fins", {})
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(f"**RSI:** {t.get('rsi', 'N/A')} ({t.get('rsi_label', 'N/A')})")
                    st.markdown(f"**StochRSI:** {t.get('stoch_rsi', 'N/A')} ({t.get('stoch_rsi_label', 'N/A')})")
                    st.markdown(f"**MACD:** {t.get('macd_label', 'N/A')}")
                with col2:
                    st.markdown(f"**Bollinger:** {t.get('bb_label', 'N/A')}")
                    st.markdown(f"**EMA Cross:** {t.get('ema_label', 'N/A')}")
                    st.markdown(f"**Volume:** {t.get('vol_label', 'N/A')}")
                with col3:
                    st.markdown(f"**VWAP:** {dlr(t['vwap']) if t.get('vwap') else 'N/A'} ({t.get('vwap_label', 'N/A')})")
                    st.markdown(f"**OBV Trend:** {t.get('obv_trend', 'N/A')}")
                    st.markdown(f"**S/R:** {t.get('sr_label', 'N/A')} | Sup: {dlr(t['support']) if t.get('support') else 'N/A'} | Res: {dlr(t['resistance']) if t.get('resistance') else 'N/A'}")

                if fins.get("peg") is not None:
                    st.markdown(f"**PEG Ratio:** {fins['peg']:.2f} ({fins['peg_label']})")
                if fins.get("z_score") is not None:
                    st.markdown(f"**Altman Z-Score:** {fins['z_score']:.2f} ({fins['z_label']})")
                if fins.get("est_revision") and fins["est_revision"] != "N/A":
                    st.markdown(f"**EPS Estimate Revisions:** {fins['est_revision']}")

    # ──── RISK & NEWS TAB ────
    with tab_risk:
        r1, r2, r3 = st.columns(3)
        r1.metric("Weighted Beta", f'{risk_d["weighted_beta"]:.2f}')
        r2.metric("Risk Rating", risk_d["risk_rating"])
        r3.metric("1-Day 95% VaR", dlr(risk_d["var_95"]))
        if risk_d["positions"]:
            pdf = pd.DataFrame(risk_d["positions"])
            pdf.columns = ["Ticker", "Weight %", "Beta", "1-Day Risk $"]
            pdf["1-Day Risk $"] = pdf["1-Day Risk $"].map(lambda x: f"${x:,.2f}")
            st.dataframe(pdf, use_container_width=True, hide_index=True)
        if risk_d["sectors"]:
            sdf = pd.DataFrame([{"Sector": k, "Exposure %": round(v, 1)}
                for k, v in sorted(risk_d["sectors"].items(), key=lambda x: -x[1])])
            st.dataframe(sdf, use_container_width=True, hide_index=True)
        st.divider()
        st.markdown(f'<div style="font-size:16px;font-weight:700;color:{GREEN};margin-bottom:10px;font-family:monospace;">Macro & Political Risk</div>', unsafe_allow_html=True)
        if macro["headlines"]:
            for h in macro["headlines"][:6]:
                pub = f' -- {h["publisher"]}' if h["publisher"] else ""
                title = h["title"]
                if h["link"]:
                    title = f'<a href="{h["link"]}" style="color:{BLUE};text-decoration:none;">{title}</a>'
                st.markdown(f'<div style="padding:6px 0;border-bottom:1px solid {BORDER};font-size:12px;color:{TEXT};">{title}<span style="color:{DIM};">{pub}</span></div>', unsafe_allow_html=True)
        if macro["risks"]:
            rdf = pd.DataFrame(macro["risks"])
            rdf.columns = [c.title() for c in rdf.columns]
            st.dataframe(rdf, use_container_width=True, hide_index=True)
