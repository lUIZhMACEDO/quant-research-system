"""
AI Stock Analyst  --  Public Streamlit Dashboard
=================================================
Anyone can enter their stocks, shares, avg cost, and email.
The app generates a personalized dashboard and sends them a report.
"""

import streamlit as st
import os, datetime, smtplib
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

for _key in ("EMAIL_PASSWORD", "SENDER_EMAIL", "RECIPIENT_EMAIL", "FINNHUB_API_KEY"):
    if _key not in os.environ:
        try:
            os.environ[_key] = st.secrets[_key]
        except Exception:
            pass

from main import (
    fetch_market_summary, get_macro_news, get_weekly_catalysts,
    analyse_portfolio, enrich_picks, compute_risk_dashboard,
    compute_technicals, get_financials, signal_logic,
    get_earnings_info, get_analyst_data, get_ticker_news,
    _timeline_block, _action_text, get_info,
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
#  CSS
# ═════════════════════════════════════════════════════════════════
st.markdown(f"""
<style>
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
    .kpi-label {{ font-size: 9px; color: {DIM}; text-transform: uppercase; letter-spacing: 0.5px; }}
    .kpi-value {{ font-size: 15px; font-weight: 700; }}
    .hero-title {{
        font-size: 36px; font-weight: 900; color: {WHITE};
        letter-spacing: -0.5px; line-height: 1.2;
    }}
    .hero-sub {{
        font-size: 16px; color: {DIM}; margin-top: 8px; line-height: 1.5;
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


# ═════════════════════════════════════════════════════════════════
#  CUSTOM PORTFOLIO ANALYSIS (for user-entered stocks)
# ═════════════════════════════════════════════════════════════════
def analyse_user_portfolio(portfolio: list[dict]) -> list[dict]:
    """Same as main.py's analyse_portfolio but works for any user's stocks."""
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

        sig, reason = signal_logic(tk, cur, opnl_p, pe, dpnl_p, hi52)
        tech = compute_technicals(tk)
        fins = get_financials(tk)
        earn = get_earnings_info(tk)
        anly = get_analyst_data(tk)
        news = get_ticker_news(tk)
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
            "strategy": "", "tech": tech, "fins": fins, "earn": earn,
            "analyst": anly, "news": news, "timeline": timeline,
        })
    return results


def send_user_email(recipient: str, holdings: list[dict], risk_d: dict,
                    sp: dict, picks_m: list, picks_s: list):
    """Build and send a personalized report email to the user."""
    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("EMAIL_PASSWORD")
    if not sender or not password:
        return False, "EMAIL_PASSWORD or SENDER_EMAIL not configured in Streamlit secrets"

    today_s = datetime.date.today().strftime("%A, %B %d, %Y")
    now_s = datetime.datetime.now().strftime("%I:%M %p")

    # Build a simple but clean HTML email for the user
    C_BG = "#0b0e11"; C_CARD = "#141821"; C_ALT = "#1a1f2b"; C_BORDER = "#1e2533"
    C_TEXT = "#d1d4dc"; C_DIM = "#6b7280"; C_GREEN = "#00d26a"; C_RED = "#f6465d"
    C_AMBER = "#f0b90b"; C_WHITE = "#ffffff"

    def _ec(v): return C_GREEN if v >= 0 else C_RED
    def _ep(v):
        c = _ec(v); s = "+" if v >= 0 else ""
        return f'<span style="color:{c};font-weight:700;">{s}{v:.2f}%</span>'

    tv = sum(h["market_value"] for h in holdings)
    tc = sum(h["total_cost"] for h in holdings)
    tp = tv - tc
    tpct = tp / tc * 100 if tc else 0

    rows = ""
    for h in holdings:
        rows += f"""<tr style="background:{C_CARD};">
            <td style="padding:10px 14px;color:{C_WHITE};font-weight:700;border-bottom:1px solid {C_BORDER};">{h["ticker"]}</td>
            <td style="padding:10px 14px;color:{C_WHITE};border-bottom:1px solid {C_BORDER};">${h["current_price"]:,.2f}</td>
            <td style="padding:10px 14px;color:{C_TEXT};border-bottom:1px solid {C_BORDER};">{h["shares"]}</td>
            <td style="padding:10px 14px;border-bottom:1px solid {C_BORDER};">{_ep(h["open_pnl_pct"])}</td>
            <td style="padding:10px 14px;border-bottom:1px solid {C_BORDER};">
                <span style="padding:3px 10px;border-radius:4px;background:{_ec(0 if 'HOLD' in h['signal'] else 1)}1a;color:{_ec(0 if 'HOLD' in h['signal'] else 1)};font-weight:700;font-size:11px;">{h["signal"]}</span></td>
            <td style="padding:10px 14px;color:{C_DIM};font-size:11px;border-bottom:1px solid {C_BORDER};">{h["reason"]}</td>
        </tr>"""

    html = f"""<html><head><meta charset="utf-8"></head>
    <body style="margin:0;padding:0;background:{C_BG};font-family:'Segoe UI',Arial,sans-serif;">
    <div style="max-width:680px;margin:0 auto;padding:20px;">
      <div style="background:{C_CARD};border-radius:12px;overflow:hidden;">
        <div style="padding:24px;border-bottom:2px solid {C_AMBER};">
          <div style="font-size:20px;font-weight:800;color:{C_WHITE};">AI Stock Analyst -- Your Report</div>
          <div style="font-size:11px;color:{C_DIM};margin-top:4px;">{today_s} | {now_s}</div>
          <div style="margin-top:10px;">
            <span style="color:{C_DIM};font-size:11px;">S&amp;P 500</span>
            <span style="color:{C_WHITE};font-weight:700;font-size:15px;margin-left:6px;">${sp["price"]:,.2f}</span>
            {_ep(sp["change"])}
          </div>
        </div>
        <div style="padding:20px;">
          <div style="font-size:13px;color:{C_AMBER};font-weight:700;margin-bottom:6px;">PORTFOLIO SUMMARY</div>
          <div style="display:flex;gap:30px;margin-bottom:16px;">
            <div><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;">Value</div><div style="font-size:16px;font-weight:700;color:{C_WHITE};">${tv:,.2f}</div></div>
            <div><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;">Cost</div><div style="font-size:16px;font-weight:700;color:{C_TEXT};">${tc:,.2f}</div></div>
            <div><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;">P&amp;L</div><div style="font-size:16px;font-weight:700;color:{_ec(tp)};">{"+" if tp>=0 else ""}${tp:,.2f} ({_ep(tpct)})</div></div>
          </div>
          <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            <thead><tr style="background:{C_ALT};">
              <th style="padding:8px 14px;text-align:left;color:{C_DIM};font-size:9px;text-transform:uppercase;border-bottom:2px solid {C_BORDER};">Ticker</th>
              <th style="padding:8px 14px;text-align:left;color:{C_DIM};font-size:9px;text-transform:uppercase;border-bottom:2px solid {C_BORDER};">Price</th>
              <th style="padding:8px 14px;text-align:left;color:{C_DIM};font-size:9px;text-transform:uppercase;border-bottom:2px solid {C_BORDER};">Shares</th>
              <th style="padding:8px 14px;text-align:left;color:{C_DIM};font-size:9px;text-transform:uppercase;border-bottom:2px solid {C_BORDER};">P&amp;L</th>
              <th style="padding:8px 14px;text-align:left;color:{C_DIM};font-size:9px;text-transform:uppercase;border-bottom:2px solid {C_BORDER};">Signal</th>
              <th style="padding:8px 14px;text-align:left;color:{C_DIM};font-size:9px;text-transform:uppercase;border-bottom:2px solid {C_BORDER};">Reason</th>
            </tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
        <div style="padding:16px 20px;text-align:center;border-top:1px solid {C_BORDER};">
          <div style="font-size:10px;color:{C_DIM};">Generated by AI Stock Analyst | Not financial advice</div>
        </div>
      </div>
    </div></body></html>"""

    text = f"AI Stock Analyst Report -- {today_s}\n"
    text += f"S&P 500: ${sp['price']:,.2f} ({sp['change']:+.2f}%)\n\n"
    for h in holdings:
        text += f"{h['ticker']:6s}  ${h['current_price']:>8.2f}  P&L {h['open_pnl_pct']:+.2f}%  -> {h['signal']}  {h['reason']}\n"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"AI Stock Report -- {datetime.date.today()}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as srv:
            srv.login(sender, password)
            srv.sendmail(sender, recipient, msg.as_string())
        return True, None
    except Exception as exc:
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as srv:
                srv.starttls()
                srv.login(sender, password)
                srv.sendmail(sender, recipient, msg.as_string())
            return True, None
        except Exception as exc2:
            return False, str(exc2)


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
      <div style="font-size:22px;font-weight:800;color:{WHITE};">AI Stock Analyst</div>
      <div style="font-size:11px;color:{DIM};margin-top:2px;">FREE PORTFOLIO ANALYZER</div>
    </div>""", unsafe_allow_html=True)
    st.markdown(
        f'<div style="text-align:center;color:{DIM};font-size:12px;">'
        f'{datetime.date.today().strftime("%A, %B %d, %Y")}</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    if st.session_state.portfolio_submitted:
        st.markdown(
            f'<div style="font-size:11px;color:{DIM};font-weight:600;'
            f'text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">'
            f'Your Portfolio</div>',
            unsafe_allow_html=True,
        )
        for p in st.session_state.user_portfolio:
            st.markdown(
                f'<div style="padding:4px 0;font-size:13px;">'
                f'<span style="color:{WHITE};font-weight:700;">{p["ticker"]}</span>'
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
    <div style="font-size:10px;color:{DIM};text-align:center;line-height:1.6;">
      Data: Yahoo Finance | Finnhub | Google News<br>Not financial advice
    </div>""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════
#  PAGE 1: INPUT FORM  (shown before submission)
# ═════════════════════════════════════════════════════════════════
if not st.session_state.portfolio_submitted:
    st.markdown(f"""
    <div style="text-align:center;margin:40px 0 20px;">
      <div class="hero-title">Get Your Free Stock Analysis</div>
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
            f'<div style="font-size:16px;font-weight:700;color:{WHITE};margin-bottom:12px;">'
            f'Your Positions</div>',
            unsafe_allow_html=True,
        )

        num = st.number_input(
            "How many stocks?", min_value=1, max_value=20, value=st.session_state.num_stocks,
            key="num_input",
        )
        st.session_state.num_stocks = num

        stocks_input = []
        for i in range(int(num)):
            st.markdown(
                f'<div style="font-size:12px;color:{AMBER};font-weight:600;margin-top:10px;">'
                f'Stock #{i+1}</div>',
                unsafe_allow_html=True,
            )
            c1, c2, c3 = st.columns(3)
            ticker = c1.text_input("Ticker", key=f"ticker_{i}", placeholder="e.g. AAPL").upper().strip()
            shares = c2.number_input("Shares", min_value=0.0, step=1.0, key=f"shares_{i}", value=0.0)
            avg_cost = c3.number_input("Avg Cost ($)", min_value=0.0, step=0.01, key=f"avg_{i}", value=0.0)
            if ticker and shares > 0 and avg_cost > 0:
                stocks_input.append({"ticker": ticker, "shares": shares, "avg_cost": avg_cost})

        st.markdown("---")
        user_email = st.text_input("Your Email (for the report)", placeholder="you@example.com")

        c_submit, c_spacer = st.columns([1, 2])
        with c_submit:
            submitted = st.button(
                f"Analyze {len(stocks_input)} Stock{'s' if len(stocks_input) != 1 else ''}",
                use_container_width=True, type="primary",
                disabled=len(stocks_input) == 0,
            )

        if submitted and stocks_input:
            st.session_state.user_portfolio = stocks_input
            st.session_state.user_email = user_email
            st.session_state.portfolio_submitted = True
            st.rerun()

    with col_preview:
        st.markdown(
            f'<div style="font-size:16px;font-weight:700;color:{WHITE};margin-bottom:12px;">'
            f'What You Get</div>',
            unsafe_allow_html=True,
        )
        features = [
            ("BUY / SELL / HOLD signals", "Per-ticker based on PE, RSI, and price action"),
            ("Technical Indicators", "RSI, MACD, Bollinger Bands, EMA, ATR levels"),
            ("Analyst Ratings", "Buy/Hold/Sell counts + price targets from Wall Street"),
            ("Earnings Alerts", "Upcoming earnings dates with EPS estimates"),
            ("Risk Dashboard", "Portfolio beta, sector exposure, 1-day VaR"),
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

    # Load shared market data
    sp = load_market()
    picks_m, picks_s = load_picks()
    macro, catalysts = load_news()

    # Analyse user's specific portfolio
    with st.spinner("Analyzing your portfolio..."):
        holdings = analyse_user_portfolio(user_portfolio)
        risk_d = compute_risk_dashboard(holdings)

    # Send email if provided
    email_sent = False
    email_error = None
    if user_email and "@" in user_email:
        with st.spinner("Sending report to your email..."):
            email_sent, email_error = send_user_email(user_email, holdings, risk_d, sp, picks_m, picks_s)

    # ── HEADER ──
    mood_c = GREEN if sp["spy_mood"] == "Bullish" else RED if sp["spy_mood"] == "Bearish" else AMBER
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{CARD},{ALT});border-radius:12px;
                padding:20px 24px;margin-bottom:16px;border:1px solid {BORDER};">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
        <div>
          <span style="font-size:20px;font-weight:800;color:{WHITE};">Your Stock Analysis</span>
          <span style="font-size:11px;color:{DIM};margin-left:12px;">
            {datetime.datetime.now().strftime("%I:%M %p")}</span>
        </div>
        <div style="text-align:right;">
          <span style="color:{DIM};font-size:11px;">S&amp;P 500</span>
          <span style="font-size:18px;font-weight:800;color:{WHITE};margin-left:8px;">{dlr(sp['price'])}</span>
          <span style="color:{clr(sp['change'])};font-weight:700;margin-left:8px;">{pct(sp['change'])}</span>
          <span style="margin-left:16px;color:{DIM};font-size:11px;">SPY</span>
          <span style="color:{mood_c};font-weight:700;margin-left:4px;">{sp['spy_mood']}</span>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    if email_sent:
        st.success(f"Report sent to {user_email}!")
    elif user_email:
        detail = f" ({email_error})" if email_error else ""
        st.warning(f"Could not send email{detail} -- but your dashboard is ready below.")

    # ── KPI ROW ──
    tv = sum(h["market_value"] for h in holdings)
    tc = sum(h["total_cost"] for h in holdings)
    tp = tv - tc
    tpc = tp / tc * 100 if tc else 0
    tdp = sum(h["day_pnl"] for h in holdings)
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
            tl = h["timeline"]
            e = h["earn"]; a = h["analyst"]
            info_parts = []
            if e.get("days_to_earnings") is not None:
                info_parts.append(f'Earnings in {e["days_to_earnings"]}d'
                    + (f' ({e["next_earnings"].strftime("%b %d")})' if e.get("next_earnings") else ""))
            info_parts.append(f'Analyst: {a["rec_buy"]} Buy / {a["rec_hold"]} Hold / {a["rec_sell"]} Sell')
            if a.get("target_mean"):
                info_parts.append(f'Target: ${a["target_low"]:.0f} / ${a["target_mean"]:.0f} / ${a["target_high"]:.0f}')
            info_parts.append(f'Insider (30d): {a["insider_buys"]} buys / {a["insider_sells"]} sells')
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
              <div style="font-size:12px;color:{AMBER};margin-top:4px;font-weight:600;">Action: {h["action"]}</div>
              <div style="display:flex;gap:24px;margin-top:12px;flex-wrap:wrap;">
                <div><div class="kpi-label">Price</div><div class="kpi-value" style="color:{WHITE};">{dlr(h["current_price"])}</div></div>
                <div><div class="kpi-label">Avg Cost</div><div class="kpi-value" style="color:{TEXT};">{dlr(h["avg_cost"])}</div></div>
                <div><div class="kpi-label">Shares</div><div class="kpi-value" style="color:{WHITE};">{int(h["shares"])}</div></div>
                <div><div class="kpi-label">PE</div><div class="kpi-value" style="color:{AMBER};">{pe_s}</div></div>
                <div><div class="kpi-label">RSI</div><div class="kpi-value" style="color:{WHITE};">{rsi_s}</div></div>
                <div><div class="kpi-label">Open P&L</div><div class="kpi-value" style="color:{oc};">{"+" if h["open_pnl"]>=0 else ""}{dlr(h["open_pnl"])}</div><div style="font-size:10px;color:{oc};">{pct(h["open_pnl_pct"])}</div></div>
                <div><div class="kpi-label">Day P&L</div><div class="kpi-value" style="color:{dc};">{"+" if h["day_pnl"]>=0 else ""}{dlr(h["day_pnl"])}</div><div style="font-size:10px;color:{dc};">{pct(h["day_pnl_pct"])}</div></div>
              </div>
              <div style="margin-top:10px;padding:10px 14px;background:{ALT};border-radius:6px;font-size:11px;color:{TEXT};line-height:1.7;">{info_html}</div>
              <div style="margin-top:10px;padding:10px 14px;background:{ALT};border-radius:6px;font-size:11px;line-height:1.7;">
                <div style="color:{CYAN};font-weight:600;">Short-term (0-30d):</div><div style="color:{TEXT};">{tl["short_level"]}<br>{tl["short_trigger"]}</div>
                <div style="color:{CYAN};font-weight:600;margin-top:4px;">Medium-term (1-6mo):</div><div style="color:{TEXT};">{tl["med_catalyst"]}<br>{tl["med_target"]}</div>
                <div style="color:{CYAN};font-weight:600;margin-top:4px;">Long-term (6-24mo):</div><div style="color:{TEXT};">{tl["long_thesis"]}<br>Invalidate: {tl["long_invalidate"]}</div>
              </div>
            </div>""", unsafe_allow_html=True)

    # ──── TRADE IDEAS TAB ────
    with tab_picks:
        st.markdown(f'<div style="font-size:16px;font-weight:700;color:{WHITE};margin-bottom:10px;">Momentum Longs (1-3 Day)</div>', unsafe_allow_html=True)
        for p in picks_m:
            st.markdown(pick_card(p), unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:16px;font-weight:700;color:{WHITE};margin:24px 0 10px;">Swing Trades (2-4 Week)</div>', unsafe_allow_html=True)
        for p in picks_s:
            st.markdown(pick_card(p), unsafe_allow_html=True)

    # ──── TECHNICALS TAB ────
    with tab_tech:
        seen = set(); rows = []
        for h in holdings:
            tk = h["ticker"]; t = h["tech"]
            if tk in seen: continue
            seen.add(tk)
            rows.append({
                "Ticker": tk, "Price": f"${h['current_price']:,.2f}",
                "RSI": f'{t.get("rsi","")}' if t.get("rsi") else "N/A",
                "RSI Signal": t.get("rsi_label","N/A"), "MACD": t.get("macd_label","N/A"),
                "Bollinger": t.get("bb_label","N/A"), "EMA": t.get("ema_label","N/A"),
                "Volume": t.get("vol_label","N/A"),
                "ATR Stop": f'${t["atr_stop"]:,.2f}' if t.get("atr_stop") else "N/A",
                "ATR Target": f'${t["atr_target"]:,.2f}' if t.get("atr_target") else "N/A",
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

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
        st.markdown(f'<div style="font-size:16px;font-weight:700;color:{WHITE};margin-bottom:10px;">Macro & Political Risk</div>', unsafe_allow_html=True)
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
