"""
AI Stock Analyst  --  Streamlit Dashboard
==========================================
Live web dashboard version of the daily stock report.
Reuses all analysis logic from main.py.
"""

import streamlit as st
import os, datetime
import pandas as pd

# ── Inject Streamlit Cloud secrets into env BEFORE importing main ──
for _key in ("EMAIL_PASSWORD", "SENDER_EMAIL", "RECIPIENT_EMAIL", "FINNHUB_API_KEY"):
    if _key not in os.environ:
        try:
            os.environ[_key] = st.secrets[_key]
        except Exception:
            pass

# Now safe to import (main reads env vars at module level)
from main import (
    fetch_market_summary, get_macro_news, get_weekly_catalysts,
    analyse_portfolio, enrich_picks, compute_risk_dashboard,
    fetch_sp500_tickers, analyse_stocks, get_top_movers,
    MY_PORTFOLIO, MOMENTUM_PICKS, SWING_PICKS,
    STRATEGY_TIMELINE, STRATEGY_NAMES,
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
#  COLORS (same palette as email report)
# ═════════════════════════════════════════════════════════════════
BG     = "#0b0e11"
CARD   = "#141821"
ALT    = "#1a1f2b"
BORDER = "#1e2533"
TEXT   = "#d1d4dc"
DIM    = "#6b7280"
GREEN  = "#00d26a"
RED    = "#f6465d"
AMBER  = "#f0b90b"
BLUE   = "#3b82f6"
WHITE  = "#ffffff"
PURPLE = "#a78bfa"
CYAN   = "#22d3ee"

# ═════════════════════════════════════════════════════════════════
#  CUSTOM CSS
# ═════════════════════════════════════════════════════════════════
st.markdown(f"""
<style>
    .stApp {{ background-color: {BG}; }}
    section[data-testid="stSidebar"] {{ background-color: {CARD}; }}
    .block-container {{ padding-top: 1rem; }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px; background-color: {CARD};
        border-radius: 8px; padding: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 6px; color: {DIM}; font-weight: 600;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {ALT} !important; color: {WHITE} !important;
    }}
    [data-testid="stMetricValue"] {{ font-size: 1.3rem; font-weight: 800; }}
    [data-testid="stMetricDelta"] {{ font-size: 0.85rem; }}
    .stock-card {{
        background: {CARD}; border: 1px solid {BORDER};
        border-radius: 10px; padding: 18px 22px; margin-bottom: 14px;
    }}
    .badge {{
        display: inline-block; padding: 3px 12px; border-radius: 4px;
        font-weight: 700; font-size: 12px;
    }}
    .badge-buy   {{ background: {GREEN}1a; color: {GREEN}; }}
    .badge-sell  {{ background: {RED}1a;   color: {RED}; }}
    .badge-hold  {{ background: {DIM}22;   color: {TEXT}; }}
    .badge-trim  {{ background: {AMBER}1a; color: {AMBER}; }}
    .badge-watch {{ background: {AMBER}1a; color: {AMBER}; }}
    .kpi-label {{ font-size: 9px; color: {DIM}; text-transform: uppercase;
                  letter-spacing: 0.5px; }}
    .kpi-value {{ font-size: 15px; font-weight: 700; }}
</style>
""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════
#  HELPERS
# ═════════════════════════════════════════════════════════════════
def dlr(v):
    """Format as dollar."""
    return f"${v:,.2f}"

def pct(v):
    """Format as signed percent."""
    return f"{v:+.2f}%"

def clr(v):
    """Green if positive, red if negative."""
    return GREEN if v >= 0 else RED

def sig_badge(sig):
    """HTML badge for a signal (BUY/SELL/HOLD/TRIM/WATCH)."""
    s = sig.upper()
    if "BUY" in s:   c = "buy"
    elif "SELL" in s: c = "sell"
    elif "TRIM" in s: c = "trim"
    elif "WATCH" in s: c = "watch"
    else:             c = "hold"
    return f'<span class="badge badge-{c}">{sig}</span>'


def pick_card(p):
    """Render a single Smart Pick card (momentum or swing)."""
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
          <span style="font-size:17px;font-weight:800;color:{WHITE};">{p["ticker"]}</span>
          <span style="font-size:12px;color:{DIM};margin-left:8px;">{p["name"]}</span>
        </div>
        <div>
          <span style="font-size:14px;font-weight:700;color:{WHITE};">{dlr(p["current_price"])}</span>
          <span style="margin-left:8px;color:{clr(p['day_chg'])};font-weight:700;">{pct(p["day_chg"])}</span>
          <span class="badge" style="margin-left:8px;background:{sc}1a;color:{sc};">{p["status"]}</span>
        </div>
      </div>
      <div style="margin-top:6px;padding:6px 10px;background:{PURPLE}15;border-radius:4px;
                  font-size:11px;color:{PURPLE};font-weight:600;">
        Strategy: {p["strategy_name"]}</div>
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
        Risk: {p["risk_pct"]:.1f}%&ensp;|&ensp;Reward: {p["reward_pct"]:.1f}%
        {f"&ensp;|&ensp;{extras}" if extras else ""}
      </div>
      <div style="font-size:10px;color:{DIM};margin-top:2px;">Fill: {p["fill_window"]}</div>
    </div>"""


# ═════════════════════════════════════════════════════════════════
#  CACHED DATA LOADERS (refresh every 30 min)
# ═════════════════════════════════════════════════════════════════
@st.cache_data(ttl=1800, show_spinner="Fetching market summary...")
def load_market():
    return fetch_market_summary()

@st.cache_data(ttl=1800, show_spinner="Analyzing portfolio...")
def load_portfolio():
    h = analyse_portfolio(MY_PORTFOLIO)
    r = compute_risk_dashboard(h)
    return h, r

@st.cache_data(ttl=1800, show_spinner="Loading smart picks...")
def load_picks():
    return enrich_picks(MOMENTUM_PICKS), enrich_picks(SWING_PICKS)

@st.cache_data(ttl=1800, show_spinner="Scanning S&P 500 (may take a few minutes on first load)...")
def load_sp500():
    tickers = fetch_sp500_tickers()
    df = analyse_stocks(tickers)
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    return get_top_movers(df)

@st.cache_data(ttl=1800, show_spinner="Loading news & catalysts...")
def load_news():
    return get_macro_news(), get_weekly_catalysts()


# ═════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center;padding:10px 0 4px;">
      <div style="font-size:22px;font-weight:800;color:{WHITE};">AI Stock Analyst</div>
      <div style="font-size:11px;color:{DIM};margin-top:2px;">LIVE DASHBOARD</div>
    </div>""", unsafe_allow_html=True)

    st.markdown(
        f'<div style="text-align:center;color:{DIM};font-size:12px;">'
        f'{datetime.date.today().strftime("%A, %B %d, %Y")}</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    if st.button("Refresh All Data", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.markdown(
        f'<div style="font-size:11px;color:{DIM};font-weight:600;'
        f'text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">'
        f'Your Portfolio</div>',
        unsafe_allow_html=True,
    )
    for p in MY_PORTFOLIO:
        st.markdown(
            f'<div style="padding:4px 0;font-size:13px;">'
            f'<span style="color:{WHITE};font-weight:700;">{p["ticker"]}</span>'
            f' <span style="color:{DIM};">-- {p["shares"]} @ {dlr(p["avg_cost"])}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown(f"""
    <div style="font-size:10px;color:{DIM};text-align:center;line-height:1.6;">
      Data: Yahoo Finance | Finnhub | Google News<br>
      Auto-refreshes every 30 min<br>Not financial advice
    </div>""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════
#  LOAD DATA
# ═════════════════════════════════════════════════════════════════
sp                = load_market()
holdings, risk_d  = load_portfolio()
picks_m, picks_s  = load_picks()
macro, catalysts  = load_news()
gainers, losers   = load_sp500()


# ═════════════════════════════════════════════════════════════════
#  HEADER BAR
# ═════════════════════════════════════════════════════════════════
mood_c = GREEN if sp["spy_mood"] == "Bullish" else RED if sp["spy_mood"] == "Bearish" else AMBER
st.markdown(f"""
<div style="background:linear-gradient(135deg,{CARD},{ALT});border-radius:12px;
            padding:20px 24px;margin-bottom:16px;border:1px solid {BORDER};">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
    <div>
      <span style="font-size:20px;font-weight:800;color:{WHITE};">Daily Market Report</span>
      <span style="font-size:11px;color:{DIM};margin-left:12px;">
        {datetime.datetime.now().strftime("%I:%M %p")}</span>
    </div>
    <div style="text-align:right;">
      <span style="color:{DIM};font-size:11px;">S&amp;P 500</span>
      <span style="font-size:18px;font-weight:800;color:{WHITE};margin-left:8px;">
        {dlr(sp['price'])}</span>
      <span style="color:{clr(sp['change'])};font-weight:700;margin-left:8px;">
        {pct(sp['change'])}</span>
      <span style="margin-left:16px;color:{DIM};font-size:11px;">SPY</span>
      <span style="color:{mood_c};font-weight:700;margin-left:4px;">{sp['spy_mood']}</span>
      <span style="color:{DIM};font-size:11px;margin-left:2px;">
        ({sp['spy_rsi']:.0f})</span>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════
#  PORTFOLIO KPI ROW
# ═════════════════════════════════════════════════════════════════
tv  = sum(h["market_value"]  for h in holdings)
tc  = sum(h["total_cost"]    for h in holdings)
tp  = tv - tc
tpc = tp / tc * 100 if tc else 0
tdp = sum(h["day_pnl"]       for h in holdings)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Portfolio Value", dlr(tv))
k2.metric("Total Cost",      dlr(tc))
k3.metric("Open P&L",        dlr(tp), delta=pct(tpc))
k4.metric("Today's P&L",     dlr(tdp))


# ═════════════════════════════════════════════════════════════════
#  TABS
# ═════════════════════════════════════════════════════════════════
tab_port, tab_picks, tab_market, tab_tech, tab_risk = st.tabs(
    ["Portfolio", "Smart Picks", "Market", "Technicals", "Risk & News"]
)

# ──────────────── PORTFOLIO TAB ────────────────
with tab_port:
    for h in holdings:
        oc = clr(h["open_pnl"])
        dc = clr(h["day_pnl"])
        pe_s = f'{h["pe"]:.1f}' if h["pe"] else "N/A"
        t  = h["tech"]
        rsi_s = f'{t["rsi"]:.0f} ({t["rsi_label"]})' if t.get("rsi") else "N/A"
        tl = h["timeline"]

        # Earnings / analyst summary
        e = h["earn"]; a = h["analyst"]
        info_parts = []
        if e.get("days_to_earnings") is not None:
            info_parts.append(
                f'Earnings in {e["days_to_earnings"]}d'
                + (f' ({e["next_earnings"].strftime("%b %d")})'
                   if e.get("next_earnings") else ""))
        info_parts.append(
            f'Analyst: {a["rec_buy"]} Buy / {a["rec_hold"]} Hold / {a["rec_sell"]} Sell')
        if a.get("target_mean"):
            info_parts.append(
                f'Target: ${a["target_low"]:.0f} / ${a["target_mean"]:.0f} / ${a["target_high"]:.0f}')
        info_parts.append(
            f'Insider (30d): {a["insider_buys"]} buys / {a["insider_sells"]} sells')
        info_html = "<br>".join(info_parts)

        st.markdown(f"""
        <div class="stock-card">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">
            <div>
              <span style="font-size:18px;font-weight:800;color:{WHITE};">{h["ticker"]}</span>
              <span style="font-size:12px;color:{DIM};margin-left:8px;">{h["name"]}</span>
            </div>
            <div>{sig_badge(h["signal"])}</div>
          </div>
          <div style="font-size:11px;color:{DIM};margin-top:4px;font-style:italic;">{h["reason"]}</div>
          <div style="font-size:12px;color:{AMBER};margin-top:4px;font-weight:600;">
            Action: {h["action"]}</div>

          <!-- KPI row -->
          <div style="display:flex;gap:24px;margin-top:12px;flex-wrap:wrap;">
            <div><div class="kpi-label">Price</div>
                 <div class="kpi-value" style="color:{WHITE};">{dlr(h["current_price"])}</div></div>
            <div><div class="kpi-label">Avg Cost</div>
                 <div class="kpi-value" style="color:{TEXT};">{dlr(h["avg_cost"])}</div></div>
            <div><div class="kpi-label">Shares</div>
                 <div class="kpi-value" style="color:{WHITE};">{h["shares"]}</div></div>
            <div><div class="kpi-label">PE</div>
                 <div class="kpi-value" style="color:{AMBER};">{pe_s}</div></div>
            <div><div class="kpi-label">RSI</div>
                 <div class="kpi-value" style="color:{WHITE};">{rsi_s}</div></div>
            <div><div class="kpi-label">Open P&L</div>
                 <div class="kpi-value" style="color:{oc};">
                   {"+" if h["open_pnl"]>=0 else ""}{dlr(h["open_pnl"])}</div>
                 <div style="font-size:10px;color:{oc};">{pct(h["open_pnl_pct"])}</div></div>
            <div><div class="kpi-label">Day P&L</div>
                 <div class="kpi-value" style="color:{dc};">
                   {"+" if h["day_pnl"]>=0 else ""}{dlr(h["day_pnl"])}</div>
                 <div style="font-size:10px;color:{dc};">{pct(h["day_pnl_pct"])}</div></div>
          </div>

          <!-- Analyst & earnings info -->
          <div style="margin-top:10px;padding:10px 14px;background:{ALT};border-radius:6px;
                      font-size:11px;color:{TEXT};line-height:1.7;">
            {info_html}
          </div>

          <!-- Timeline -->
          <div style="margin-top:10px;padding:10px 14px;background:{ALT};border-radius:6px;
                      font-size:11px;line-height:1.7;">
            <div style="color:{CYAN};font-weight:600;">Short-term (0-30d):</div>
            <div style="color:{TEXT};">{tl["short_level"]}<br>{tl["short_trigger"]}</div>
            <div style="color:{CYAN};font-weight:600;margin-top:4px;">Medium-term (1-6mo):</div>
            <div style="color:{TEXT};">{tl["med_catalyst"]}<br>{tl["med_target"]}</div>
            <div style="color:{CYAN};font-weight:600;margin-top:4px;">Long-term (6-24mo):</div>
            <div style="color:{TEXT};">{tl["long_thesis"]}<br>Invalidate: {tl["long_invalidate"]}</div>
          </div>
        </div>""", unsafe_allow_html=True)

    # Strategy Timeline table
    st.markdown(
        f'<div style="font-size:16px;font-weight:700;color:{WHITE};margin:24px 0 8px;">'
        f'Strategy Timeline</div>',
        unsafe_allow_html=True,
    )
    st.dataframe(
        pd.DataFrame(STRATEGY_TIMELINE)[["period", "action", "detail"]].rename(
            columns={"period": "Period", "action": "Action", "detail": "Detail"}
        ),
        use_container_width=True, hide_index=True,
    )


# ──────────────── SMART PICKS TAB ────────────────
with tab_picks:
    st.markdown(
        f'<div style="font-size:16px;font-weight:700;color:{WHITE};margin-bottom:10px;">'
        f'Momentum Longs (1-3 Day Horizon)</div>',
        unsafe_allow_html=True,
    )
    if picks_m:
        for p in picks_m:
            st.markdown(pick_card(p), unsafe_allow_html=True)
    else:
        st.info("No momentum picks today.")

    st.markdown(
        f'<div style="font-size:16px;font-weight:700;color:{WHITE};margin:24px 0 10px;">'
        f'Swing Trades (2-4 Week Horizon)</div>',
        unsafe_allow_html=True,
    )
    if picks_s:
        for p in picks_s:
            st.markdown(pick_card(p), unsafe_allow_html=True)
    else:
        st.info("No swing picks today.")


# ──────────────── MARKET TAB ────────────────
with tab_market:
    if gainers.empty:
        st.warning("S&P 500 data is loading -- please wait or hit Refresh.")
    else:
        cg, cl = st.columns(2)
        with cg:
            st.markdown(
                f'<div style="font-size:16px;font-weight:700;color:{GREEN};margin-bottom:6px;">'
                f'Top 10 Gainers</div>',
                unsafe_allow_html=True,
            )
            gd = gainers[["Ticker", "Previous Close", "Current Price", "Change %"]].copy()
            gd["Previous Close"] = gd["Previous Close"].map(lambda x: f"${x:,.2f}")
            gd["Current Price"]  = gd["Current Price"].map(lambda x: f"${x:,.2f}")
            gd["Change %"]       = gd["Change %"].map(lambda x: f"+{x:.2f}%")
            st.dataframe(gd, use_container_width=True, hide_index=True)

        with cl:
            st.markdown(
                f'<div style="font-size:16px;font-weight:700;color:{RED};margin-bottom:6px;">'
                f'Top 10 Losers</div>',
                unsafe_allow_html=True,
            )
            ld = losers[["Ticker", "Previous Close", "Current Price", "Change %"]].copy()
            ld["Previous Close"] = ld["Previous Close"].map(lambda x: f"${x:,.2f}")
            ld["Current Price"]  = ld["Current Price"].map(lambda x: f"${x:,.2f}")
            ld["Change %"]       = ld["Change %"].map(lambda x: f"{x:.2f}%")
            st.dataframe(ld, use_container_width=True, hide_index=True)


# ──────────────── TECHNICALS TAB ────────────────
with tab_tech:
    st.markdown(
        f'<div style="font-size:16px;font-weight:700;color:{WHITE};margin-bottom:10px;">'
        f'Technical Snapshot</div>',
        unsafe_allow_html=True,
    )
    seen = set()
    all_items = [(h["ticker"], h["current_price"], h["tech"]) for h in holdings]
    for p in picks_m + picks_s:
        if p["ticker"] not in {x[0] for x in all_items}:
            all_items.append((p["ticker"], p["current_price"], p.get("tech", {})))

    rows = []
    for tk, price, t in all_items:
        if tk in seen:
            continue
        seen.add(tk)
        rows.append({
            "Ticker":      tk,
            "Price":       f"${price:,.2f}",
            "RSI":         f'{t.get("rsi", "")}' if t.get("rsi") else "N/A",
            "RSI Signal":  t.get("rsi_label", "N/A"),
            "MACD":        t.get("macd_label", "N/A"),
            "Bollinger":   t.get("bb_label", "N/A"),
            "EMA":         t.get("ema_label", "N/A"),
            "Volume":      t.get("vol_label", "N/A"),
            "ATR Stop":    f'${t["atr_stop"]:,.2f}' if t.get("atr_stop") else "N/A",
            "ATR Target":  f'${t["atr_target"]:,.2f}' if t.get("atr_target") else "N/A",
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No technical data available.")


# ──────────────── RISK & NEWS TAB ────────────────
with tab_risk:
    # ── Risk Dashboard ──
    st.markdown(
        f'<div style="font-size:16px;font-weight:700;color:{WHITE};margin-bottom:10px;">'
        f'Portfolio Risk Dashboard</div>',
        unsafe_allow_html=True,
    )
    r1, r2, r3 = st.columns(3)
    r1.metric("Weighted Beta", f'{risk_d["weighted_beta"]:.2f}')
    r2.metric("Risk Rating",   risk_d["risk_rating"])
    r3.metric("1-Day 95% VaR", dlr(risk_d["var_95"]))

    if risk_d["positions"]:
        pdf = pd.DataFrame(risk_d["positions"])
        pdf.columns = ["Ticker", "Weight %", "Beta", "1-Day Risk $"]
        pdf["1-Day Risk $"] = pdf["1-Day Risk $"].map(lambda x: f"${x:,.2f}")
        st.dataframe(pdf, use_container_width=True, hide_index=True)

    if risk_d["sectors"]:
        sdf = pd.DataFrame([
            {"Sector": k, "Exposure %": round(v, 1)}
            for k, v in sorted(risk_d["sectors"].items(), key=lambda x: -x[1])
        ])
        st.dataframe(sdf, use_container_width=True, hide_index=True)

    st.divider()

    # ── Macro Headlines ──
    st.markdown(
        f'<div style="font-size:16px;font-weight:700;color:{WHITE};margin-bottom:10px;">'
        f'Macro & Political Risk</div>',
        unsafe_allow_html=True,
    )
    if macro["headlines"]:
        for h in macro["headlines"][:6]:
            pub = f' -- {h["publisher"]}' if h["publisher"] else ""
            title = h["title"]
            if h["link"]:
                title = (f'<a href="{h["link"]}" style="color:{BLUE};'
                         f'text-decoration:none;">{title}</a>')
            st.markdown(
                f'<div style="padding:6px 0;border-bottom:1px solid {BORDER};'
                f'font-size:12px;color:{TEXT};">{title}'
                f'<span style="color:{DIM};">{pub}</span></div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(f'<div style="color:{DIM};font-size:12px;">No headlines available.</div>',
                    unsafe_allow_html=True)

    if macro["risks"]:
        st.markdown(
            f'<div style="font-size:13px;font-weight:600;color:{AMBER};margin:14px 0 6px;">'
            f'Portfolio Risk Flags</div>',
            unsafe_allow_html=True,
        )
        rdf = pd.DataFrame(macro["risks"])
        rdf.columns = [c.title() for c in rdf.columns]
        st.dataframe(rdf, use_container_width=True, hide_index=True)

    st.divider()

    # ── Catalysts ──
    st.markdown(
        f'<div style="font-size:16px;font-weight:700;color:{WHITE};margin-bottom:10px;">'
        f"This Week's Catalysts</div>",
        unsafe_allow_html=True,
    )
    if catalysts:
        for c in catalysts:
            d = c["date"].strftime("%b %d") if c["date"] else "TBD"
            eps = f"est EPS: ${c['eps_est']:.2f}" if c["eps_est"] else "est EPS: N/A"
            st.markdown(
                f'<div style="padding:6px 0;border-bottom:1px solid {BORDER};font-size:12px;">'
                f'<span style="color:{WHITE};font-weight:700;">{c["ticker"]}</span>'
                f' <span style="color:{AMBER};">-- reports {d} ({eps})</span></div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            f'<div style="color:{DIM};font-size:12px;">'
            f'No major earnings this week for your watchlist.</div>',
            unsafe_allow_html=True,
        )
