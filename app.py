"""
AI Stock Analyst  --  Public Streamlit Dashboard
=================================================
Version: 3.1.0
Anyone can enter their stocks, shares, avg cost, and email.
The app generates a personalized dashboard and sends them a report.
"""
APP_VERSION = "3.1.0"

import streamlit as st
import os, datetime, smtplib, time
import pandas as pd
import pytz
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
    enrich_picks, compute_risk_dashboard,
    compute_technicals, get_financials, signal_logic,
    get_earnings_info, get_analyst_data, get_ticker_news,
    _timeline_block, _action_text, get_info, get_hist,
    MOMENTUM_PICKS, SWING_PICKS, STRATEGY_NAMES,
    fetch_sp500_tickers, analyse_stocks, get_top_movers,
    MY_PORTFOLIO, get_crypto_prices, get_fear_greed, get_ai_strategy_note,
)

# ═════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ═════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="AI Stock Analyst",
    page_icon=None,
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
    html, body, [class*="css"] {{ font-size: 16px; }}
    section[data-testid="stSidebar"] {{ background-color: {CARD}; }}
    section[data-testid="stSidebar"] * {{ font-size: 15px !important; }}
    .block-container {{ padding-top: 0.5rem; }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px; background-color: {CARD}; border-radius: 8px; padding: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 6px; color: {DIM}; font-weight: 700;
        font-size: 15px !important; padding: 10px 20px !important;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {ALT} !important; color: {WHITE} !important;
    }}
    [data-testid="stMetricLabel"] {{ font-size: 14px !important; color: {DIM}; font-weight: 600; }}
    [data-testid="stMetricValue"] {{ font-size: 1.7rem !important; font-weight: 800; color: {WHITE}; }}
    [data-testid="stMetricDelta"] {{ font-size: 1rem !important; }}
    .stock-card {{
        background: {CARD}; border: 1px solid {BORDER};
        border-radius: 12px; padding: 22px 26px; margin-bottom: 16px;
    }}
    .badge {{
        display: inline-block; padding: 5px 16px; border-radius: 6px;
        font-weight: 800; font-size: 14px; letter-spacing: 0.5px;
    }}
    .badge-buy   {{ background: {GREEN}22; color: {GREEN}; border: 1px solid {GREEN}44; }}
    .badge-sell  {{ background: {RED}22;   color: {RED};   border: 1px solid {RED}44; }}
    .badge-hold  {{ background: {DIM}33;   color: {TEXT};  border: 1px solid {DIM}55; }}
    .badge-trim  {{ background: {AMBER}22; color: {AMBER}; border: 1px solid {AMBER}44; }}
    .badge-watch {{ background: {AMBER}22; color: {AMBER}; border: 1px solid {AMBER}44; }}
    .kpi-label {{
        font-size: 11px; color: {DIM}; text-transform: uppercase;
        letter-spacing: 1px; margin-bottom: 3px; font-weight: 600;
    }}
    .kpi-value {{ font-size: 18px; font-weight: 800; line-height: 1.2; }}
    .card-info {{
        font-size: 14px !important; color: {TEXT}; line-height: 1.8;
        padding: 12px 16px; background: {ALT}; border-radius: 8px; margin-top: 10px;
    }}
    .card-timeline {{
        font-size: 14px !important; color: {TEXT}; line-height: 1.8;
        padding: 12px 16px; background: {ALT}; border-radius: 8px; margin-top: 10px;
    }}
    .timeline-label {{
        color: {CYAN}; font-weight: 700; font-size: 14px !important;
        margin-top: 6px; margin-bottom: 2px;
    }}
    .card-reason {{ font-size: 14px; color: {DIM}; font-style: italic; margin-top: 6px; }}
    .card-action {{ font-size: 15px; color: {AMBER}; font-weight: 700; margin-top: 6px; }}
    .card-ticker {{ font-size: 22px; font-weight: 900; color: {WHITE}; }}
    .card-name   {{ font-size: 14px; color: {DIM}; margin-left: 10px; }}
    .news-item {{
        padding: 10px 0; border-bottom: 1px solid {BORDER};
        font-size: 14px; color: {TEXT}; line-height: 1.6;
    }}
    .dataframe td, .dataframe th {{ font-size: 14px !important; padding: 10px 14px !important; }}
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {{ font-size: 15px !important; padding: 10px 12px !important;
        min-width: 80px; overflow: visible; }}
    .stNumberInput > div {{ overflow: visible !important; }}
    section[data-testid="stSidebar"] .stNumberInput input {{ min-width: 70px !important; }}
    section[data-testid="stSidebar"] .stNumberInput {{ margin-bottom: 1rem !important; }}
    /* Hide "Press Enter to apply" on number inputs */
    .stNumberInput [data-testid="stCaptionContainer"] {{ display: none !important; }}
    label[data-testid="stWidgetLabel"] p {{ font-size: 15px !important; font-weight: 600; }}
    .stButton > button, .stFormSubmitButton > button {{
        font-size: 16px !important; font-weight: 700 !important;
        padding: 12px 28px !important; border-radius: 8px !important;
        white-space: nowrap !important; min-width: 120px !important;
    }}
    section[data-testid="stSidebar"] .stButton > button {{
        min-width: 100% !important; width: 100% !important;
    }}
    .hero-title {{
        font-size: 38px; font-weight: 900; color: {WHITE};
        letter-spacing: -0.5px; line-height: 1.2;
    }}
    .hero-sub {{
        font-size: 17px; color: {DIM}; margin-top: 10px; line-height: 1.6;
    }}
    @keyframes live-pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:0.3}} }}
    .live-dot {{
        display:inline-block; width:9px; height:9px; border-radius:50%;
        background:{AMBER}; box-shadow:0 0 8px {AMBER};
        animation:live-pulse 1.5s ease-in-out infinite;
        margin-right:6px; vertical-align:middle;
    }}
    @keyframes ticker-scroll {{ 0%{{transform:translateX(0)}} 100%{{transform:translateX(-33.333%)}} }}
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    header {{ visibility: hidden; }}
</style>
""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════
#  HELPERS
# ═════════════════════════════════════════════════════════════════
def dlr(v): return f"${v:,.2f}"
def pct(v): return f"{v:+.2f}%"
def clr(v): return GREEN if v >= 0 else RED

def is_market_open() -> bool:
    et = pytz.timezone("America/New_York")
    now = datetime.datetime.now(et)
    if now.weekday() >= 5:
        return False
    return datetime.time(9, 30) <= now.time() <= datetime.time(16, 0)

@st.cache_data(ttl=15, show_spinner=False)
def get_live_prices(tickers: tuple) -> dict:
    """Batch yfinance download — faster than individual calls."""
    import yfinance as yf
    if not tickers:
        return {}
    tickers_list = list(tickers)
    result = {}
    try:
        df = yf.download(tickers_list, period="2d", interval="1d",
                         auto_adjust=True, progress=False, threads=True)
        if df.empty:
            raise ValueError("Empty")
        closes = df["Close"] if isinstance(df.columns, pd.MultiIndex) or "Close" in df.columns else df
        if isinstance(closes, pd.DataFrame):
            for tk in tickers_list:
                try:
                    col = closes[tk] if tk in closes.columns else closes.iloc[:, 0]
                    prices = col.dropna()
                    if len(prices) >= 2:
                        prev, curr = float(prices.iloc[-2]), float(prices.iloc[-1])
                        chg = curr - prev
                        result[tk] = {"price": curr, "change": chg, "change_pct": round(chg / prev * 100, 2) if prev else 0}
                except Exception:
                    result[tk] = {"price": 0.0, "change": 0.0, "change_pct": 0.0}
        else:
            prices = closes.dropna()
            if len(prices) >= 2 and len(tickers_list) == 1:
                prev, curr = float(prices.iloc[-2]), float(prices.iloc[-1])
                chg = curr - prev
                result[tickers_list[0]] = {"price": curr, "change": chg, "change_pct": round(chg / prev * 100, 2) if prev else 0}
    except Exception:
        pass
    for tk in tickers_list:
        if tk not in result:
            try:
                fi = yf.Ticker(tk).fast_info
                p = float(fi.last_price or 0)
                pc = float(fi.previous_close or p)
                chg = p - pc
                result[tk] = {"price": p, "change": chg, "change_pct": round(chg / pc * 100, 2) if pc else 0}
            except Exception:
                result[tk] = {"price": 0.0, "change": 0.0, "change_pct": 0.0}
    return result

def sparkline_chart(ticker: str):
    """Mini 30-day sparkline for portfolio cards."""
    import plotly.graph_objects as go
    hist = get_hist(ticker, "30d", "1d")
    if hist.empty or len(hist) < 2:
        return None
    prices = hist["Close"].tolist()
    color = GREEN if prices[-1] >= prices[0] else RED
    # Plotly needs rgba for fill with alpha; hex #RRGGBB -> rgba(r,g,b,0.08)
    hex_to_rgba = lambda h: f"rgba({int(h[1:3],16)},{int(h[3:5],16)},{int(h[5:7],16)},0.08)"
    fill_color = hex_to_rgba(color) if color.startswith("#") else "rgba(0,0,0,0.08)"
    fig = go.Figure(go.Scatter(
        y=prices,
        mode="lines",
        line=dict(color=color, width=1.5),
        fill="tozeroy",
        fillcolor=fill_color,
    ))
    fig.update_layout(
        height=60, margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


# ═════════════════════════════════════════════════════════════════
#  CHART HELPERS (full price charts, allocation, P&L)
# ═════════════════════════════════════════════════════════════════
_CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0f1318",
    font=dict(color="#d1d4dc", size=12),
    margin=dict(l=0, r=0, t=32, b=0),
    xaxis=dict(showgrid=False, color="#4b5568", zeroline=False,
               rangeslider=dict(visible=False)),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
    hovermode="x unified",
)
_CHART_YAXIS = dict(showgrid=True, gridcolor="#1e2533", color="#4b5568", zeroline=False)

@st.cache_data(ttl=300, show_spinner=False)
def _get_ohlcv(ticker: str, period: str = "60d") -> pd.DataFrame:
    """Cached OHLCV history for charts."""
    try:
        df = get_hist(ticker, period, "1d")
        if df.empty or len(df) < 2:
            import yfinance as yf
            df = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=True)
        df.index = pd.to_datetime(df.index)
        return df
    except Exception:
        return pd.DataFrame()

def build_price_chart(ticker: str, avg_cost: float, tech: dict) -> go.Figure:
    """
    3-panel chart: Candlestick + Bollinger Bands + avg cost line (top),
    RSI with overbought/oversold bands (middle), MACD histogram (bottom).
    """
    df = _get_ohlcv(ticker, "60d")
    if df.empty or len(df) < 10:
        fig = go.Figure()
        fig.update_layout(**_CHART_LAYOUT, title=f"{ticker} — no data")
        return fig

    close = df["Close"]
    dates = df.index

    def _hex_rgba(h, a=1.0):
        r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
        return f"rgba({r},{g},{b},{a})"

    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_up = bb_mid + 2 * bb_std
    bb_dn = bb_mid - 2 * bb_std

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    hist_colors = [GREEN if v >= 0 else RED for v in hist]

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.60, 0.20, 0.20],
        vertical_spacing=0.03,
    )

    fig.add_trace(go.Candlestick(
        x=dates, open=df["Open"], high=df["High"], low=df["Low"], close=close,
        name=ticker,
        increasing_line_color=GREEN, decreasing_line_color=RED,
        increasing_fillcolor=_hex_rgba(GREEN, 0.53), decreasing_fillcolor=_hex_rgba(RED, 0.53),
        line=dict(width=1),
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=dates, y=bb_up, name="BB Upper",
        line=dict(color=_hex_rgba(CYAN, 0.33), width=1, dash="dot"), showlegend=False,
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=dates, y=bb_dn, name="BB Lower",
        line=dict(color=_hex_rgba(CYAN, 0.33), width=1, dash="dot"),
        fill="tonexty", fillcolor="rgba(34,211,238,0.08)", showlegend=False,
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=dates, y=bb_mid, name="BB Mid",
        line=dict(color=_hex_rgba(CYAN, 0.5), width=1), showlegend=False,
    ), row=1, col=1)

    if avg_cost and avg_cost > 0:
        fig.add_hline(
            y=avg_cost, line_color=AMBER, line_dash="dash", line_width=1.5,
            annotation_text=f"Avg ${avg_cost:.2f}",
            annotation_font_color=AMBER, annotation_font_size=11,
            row=1, col=1,
        )

    fig.add_trace(go.Scatter(
        x=dates, y=rsi, name="RSI",
        line=dict(color=PURPLE, width=1.5), showlegend=False,
    ), row=2, col=1)
    fig.add_hline(y=70, line_color=_hex_rgba(RED, 0.4), line_dash="dot", line_width=1, row=2, col=1)
    fig.add_hline(y=30, line_color=_hex_rgba(GREEN, 0.4), line_dash="dot", line_width=1, row=2, col=1)
    fig.add_hrect(y0=70, y1=100, fillcolor=_hex_rgba(RED, 0.03), line_width=0, row=2, col=1)
    fig.add_hrect(y0=0, y1=30, fillcolor=_hex_rgba(GREEN, 0.03), line_width=0, row=2, col=1)

    fig.add_trace(go.Bar(
        x=dates, y=hist, name="MACD Hist",
        marker_color=hist_colors, showlegend=False,
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=dates, y=macd, name="MACD", line=dict(color=BLUE, width=1.5), showlegend=False,
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=dates, y=signal, name="Signal", line=dict(color=AMBER, width=1.2), showlegend=False,
    ), row=3, col=1)

    layout = dict(**_CHART_LAYOUT)
    layout.update(
        height=520,
        title=dict(text=f"<b>{ticker}</b>  60-Day Chart", font=dict(size=14, color=WHITE), x=0),
        yaxis2=dict(title="RSI", showgrid=True, gridcolor="#1e2533",
                    color="#4b5568", range=[0, 100], zeroline=False),
        yaxis3=dict(title="MACD", showgrid=True, gridcolor="#1e2533",
                    color="#4b5568", zeroline=False),
        xaxis3=dict(showgrid=False, color="#4b5568", zeroline=False,
                    rangeslider=dict(visible=False)),
    )
    fig.update_layout(**layout)
    fig.update_xaxes(showspikes=True, spikecolor=DIM, spikethickness=1)
    fig.update_yaxes(showspikes=True, spikecolor=DIM, spikethickness=1)
    return fig


def build_sector_donut(risk_d: dict) -> go.Figure | None:
    """Sector exposure donut chart."""
    sectors = risk_d.get("sectors", {})
    if not sectors:
        return None
    labels = list(sectors.keys())
    values = [round(v, 1) for v in sectors.values()]
    colors = [BLUE, CYAN, PURPLE, AMBER, GREEN, RED, "#f97316", "#84cc16",
              "#ec4899", "#14b8a6"][:len(labels)]
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.55,
        marker=dict(colors=colors, line=dict(color=BG, width=2)),
        textinfo="label+percent",
        textfont=dict(size=12, color=WHITE),
        hovertemplate="%{label}: %{value:.1f}%<extra></extra>",
    ))
    _lay = dict(**_CHART_LAYOUT)
    _lay.update(height=280, margin=dict(l=0, r=0, t=36, b=0),
                title=dict(text="Sector Exposure", font=dict(size=13, color=WHITE), x=0),
                showlegend=False)
    fig.update_layout(**_lay)
    return fig


def build_allocation_bar(holdings: list) -> go.Figure | None:
    """Horizontal bar chart of portfolio allocation by market value."""
    if not holdings:
        return None
    tickers = [h["ticker"] for h in holdings]
    values = [h["market_value"] for h in holdings]
    total = sum(values) or 1
    pcts = [v / total * 100 for v in values]
    colors = [GREEN if h["open_pnl"] >= 0 else RED for h in holdings]

    fig = go.Figure(go.Bar(
        x=pcts, y=tickers,
        orientation="h",
        marker=dict(color=colors, opacity=0.85),
        text=[f"{p:.1f}%" for p in pcts],
        textposition="outside",
        textfont=dict(color=WHITE, size=12),
        hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
    ))
    _lay = dict(**_CHART_LAYOUT)
    _lay.update(height=max(180, len(tickers) * 48), margin=dict(l=0, r=80, t=36, b=20),
                title=dict(text="Portfolio Allocation", font=dict(size=13, color=WHITE), x=0),
                xaxis=dict(showgrid=True, gridcolor="#1e2533", color="#4b5568",
                           ticksuffix="%", zeroline=False, rangeslider=dict(visible=False)),
                yaxis=dict(showgrid=False, color=WHITE, zeroline=False, autorange="reversed"))
    fig.update_layout(**_lay)
    return fig


def build_pnl_bar(holdings: list) -> go.Figure | None:
    """Open P&L per holding — bar chart."""
    if not holdings:
        return None
    tickers = [h["ticker"] for h in holdings]
    pnls = [h["open_pnl"] for h in holdings]
    pcts = [h["open_pnl_pct"] for h in holdings]
    colors = [GREEN if v >= 0 else RED for v in pnls]

    fig = go.Figure(go.Bar(
        x=tickers, y=pnls,
        marker=dict(color=colors, opacity=0.85),
        text=[f"{p:+.1f}%" for p in pcts],
        textposition="auto",
        textfont=dict(color=WHITE, size=11),
        hovertemplate="%{x}<br>P&L: $%{y:,.2f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_color=DIM, line_width=1)
    _lay = dict(**_CHART_LAYOUT)
    _lay.update(height=320, margin=dict(l=0, r=0, t=50, b=50),
                title=dict(text="Open P&L by Position", font=dict(size=13, color=WHITE), x=0),
                yaxis=dict(**_CHART_YAXIS, tickprefix="$", automargin=True))
    fig.update_layout(**_lay)
    return fig


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
        rsi_val = tech.get("rsi") or 50
        strategy_note = get_ai_strategy_note(tk, sig, rsi_val, anly.get("rec_buy", 0), anly.get("rec_sell", 0))

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
            "strategy_note": strategy_note, "strategy": "", "tech": tech, "fins": fins, "earn": earn,
            "analyst": anly, "news": news, "timeline": timeline,
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

    # ── Per-stock detail cards ──
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

        cards += f"""
        <div style="background:{C};border:1px solid {BD};border-radius:10px;padding:18px 22px;margin-bottom:14px;">
          <table width="100%" cellpadding="0" cellspacing="0"><tr>
            <td style="padding:0;"><span style="font-size:18px;font-weight:800;color:{W};">{h["ticker"]}</span>
              <span style="font-size:12px;color:{D};margin-left:8px;">{h["name"]}</span></td>
            <td style="padding:0;text-align:right;">{sig_html(h["signal"])}</td>
          </tr></table>
          <div style="font-size:11px;color:{D};margin-top:4px;font-style:italic;">{h["reason"]}</div>
          <div style="font-size:12px;color:{AM};margin-top:4px;font-weight:600;">Action: {h["action"]}</div>

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

          <div style="margin-top:10px;padding:10px 14px;background:{A};border-radius:6px;font-size:11px;line-height:1.7;">
            <div style="color:{CY};font-weight:600;">Short-term (0-30d):</div>
            <div style="color:{T};">{tl.get("short_level","N/A")}<br>{tl.get("short_trigger","")}</div>
            <div style="color:{CY};font-weight:600;margin-top:4px;">Medium-term (1-6mo):</div>
            <div style="color:{T};">{tl.get("med_catalyst","N/A")}<br>{tl.get("med_target","")}</div>
            <div style="color:{CY};font-weight:600;margin-top:4px;">Long-term (6-24mo):</div>
            <div style="color:{T};">{tl.get("long_thesis","N/A")}<br>Invalidate: {tl.get("long_invalidate","N/A")}</div>
          </div>
        </div>"""

    # ── Technicals table ──
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

    # ── Risk dashboard ──
    risk_rows = ""
    for p in risk_d.get("positions", []):
        risk_rows += f"""<tr style="background:{C};">
          <td style="padding:6px 10px;color:{W};font-weight:700;border-bottom:1px solid {BD};">{p["ticker"]}</td>
          <td style="padding:6px 10px;color:{T};border-bottom:1px solid {BD};">{p["weight"]:.1f}%</td>
          <td style="padding:6px 10px;color:{T};border-bottom:1px solid {BD};">{p["beta"]:.2f}</td>
          <td style="padding:6px 10px;color:{T};border-bottom:1px solid {BD};">${p["risk_1d"]:,.2f}</td>
        </tr>"""

    sector_html = ""
    for sec, exp in sorted(risk_d.get("sectors", {}).items(), key=lambda x: -x[1]):
        sector_html += f'<span style="display:inline-block;margin:2px 6px 2px 0;padding:3px 10px;background:{A};border-radius:4px;font-size:11px;color:{T};">{sec} {exp:.1f}%</span>'

    html = f"""<html><head><meta charset="utf-8"></head>
    <body style="margin:0;padding:0;background:{B};font-family:'Segoe UI',Arial,sans-serif;">
    <div style="max-width:700px;margin:0 auto;padding:20px;">

      <!-- HEADER -->
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

      <!-- PORTFOLIO KPIs -->
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

      <!-- STOCK DETAIL CARDS -->
      <div style="font-size:15px;font-weight:700;color:{W};margin-bottom:10px;">YOUR HOLDINGS</div>
      {cards}

      <!-- TECHNICALS -->
      <div style="font-size:15px;font-weight:700;color:{W};margin:20px 0 10px;">TECHNICAL SNAPSHOT</div>
      <div style="overflow-x:auto;">
        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
          <thead><tr style="background:{A};">
            <th style="padding:8px 10px;text-align:left;color:{D};font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">Ticker</th>
            <th style="padding:8px 10px;text-align:left;color:{D};font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">Price</th>
            <th style="padding:8px 10px;text-align:left;color:{D};font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">RSI</th>
            <th style="padding:8px 10px;text-align:left;color:{D};font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">Signal</th>
            <th style="padding:8px 10px;text-align:left;color:{D};font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">MACD</th>
            <th style="padding:8px 10px;text-align:left;color:{D};font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">Bollinger</th>
            <th style="padding:8px 10px;text-align:left;color:{D};font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">EMA</th>
            <th style="padding:8px 10px;text-align:left;color:{D};font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">Volume</th>
          </tr></thead>
          <tbody>{tech_rows}</tbody>
        </table>
      </div>

      <!-- RISK DASHBOARD -->
      <div style="font-size:15px;font-weight:700;color:{W};margin:20px 0 10px;">RISK DASHBOARD</div>
      <div style="background:{C};border-radius:10px;padding:16px 20px;margin-bottom:14px;border:1px solid {BD};">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            {kpi("Weighted Beta", f'{risk_d["weighted_beta"]:.2f}', W)}
            {kpi("Risk Rating", risk_d["risk_rating"], AM)}
            {kpi("1-Day 95% VaR", f'${risk_d["var_95"]:,.2f}', R)}
          </tr>
        </table>
        {"" if not risk_rows else f'''
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:10px;border-collapse:collapse;">
          <thead><tr style="background:{A};">
            <th style="padding:6px 10px;text-align:left;color:{D};font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">Ticker</th>
            <th style="padding:6px 10px;text-align:left;color:{D};font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">Weight</th>
            <th style="padding:6px 10px;text-align:left;color:{D};font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">Beta</th>
            <th style="padding:6px 10px;text-align:left;color:{D};font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">1-Day Risk</th>
          </tr></thead>
          <tbody>{risk_rows}</tbody>
        </table>'''}
        {"" if not sector_html else f'<div style="margin-top:10px;"><div style="font-size:10px;color:{D};margin-bottom:4px;">SECTOR EXPOSURE</div>{sector_html}</div>'}
      </div>

      <!-- FOOTER -->
      <div style="text-align:center;padding:16px 0;">
        <div style="font-size:10px;color:{D};">Generated by AI Stock Analyst | Not financial advice</div>
      </div>
    </div></body></html>"""

    # Plain-text fallback
    text = f"AI Stock Analyst Report -- {today_s}\n"
    text += f"S&P 500: ${sp['price']:,.2f} ({sp['change']:+.2f}%)\n\n"
    for h in holdings:
        t = h.get("tech", {}); tl = h.get("timeline", {})
        rsi_s = f'RSI {t["rsi"]:.0f} ({t["rsi_label"]})' if t.get("rsi") else "RSI N/A"
        text += f"{'='*50}\n"
        text += f"{h['ticker']}  {h['name']}\n"
        text += f"  Price: ${h['current_price']:,.2f}  |  Avg: ${h['avg_cost']:,.2f}  |  Shares: {int(h['shares'])}\n"
        text += f"  Open P&L: ${h['open_pnl']:+,.2f} ({h['open_pnl_pct']:+.2f}%)\n"
        text += f"  Day P&L:  ${h['day_pnl']:+,.2f} ({h['day_pnl_pct']:+.2f}%)\n"
        text += f"  Signal: {h['signal']} -- {h['reason']}\n"
        text += f"  Action: {h['action']}\n"
        text += f"  PE: {h['pe'] or 'N/A'}  |  {rsi_s}  |  MACD: {t.get('macd_label','N/A')}\n"
        text += f"  Short: {tl.get('short_level','N/A')} | {tl.get('short_trigger','')}\n"
        text += f"  Medium: {tl.get('med_catalyst','N/A')} | {tl.get('med_target','')}\n"
        text += f"  Long: {tl.get('long_thesis','N/A')} | Invalidate: {tl.get('long_invalidate','N/A')}\n\n"
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
            srv.ehlo()
            srv.starttls()
            srv.ehlo()
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
if "page_mode" not in st.session_state:
    st.session_state.page_mode = "personal"  # "personal" = My Portfolio, "custom" = Analyze Stocks
if "portfolio_submitted" not in st.session_state:
    st.session_state.portfolio_submitted = True  # Start with dashboard (My Portfolio)
if "user_portfolio" not in st.session_state:
    st.session_state.user_portfolio = MY_PORTFOLIO
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "num_stocks" not in st.session_state:
    st.session_state.num_stocks = 1
if "portfolio_version" not in st.session_state:
    st.session_state.portfolio_version = 0  # Bump when portfolio changes → re-run heavy analysis


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

    # Navigation: My Portfolio vs Analyze Stocks (stacked = full width, no wrap)
    if st.button("My Portfolio", use_container_width=True, type="primary" if st.session_state.page_mode == "personal" else "secondary"):
        st.session_state.page_mode = "personal"
        st.session_state.user_portfolio = MY_PORTFOLIO
        st.session_state.portfolio_submitted = True
        st.rerun()
    if st.button("Analyze Stocks", use_container_width=True, type="primary" if st.session_state.page_mode == "custom" else "secondary"):
        st.session_state.page_mode = "custom"
        st.session_state.portfolio_submitted = False
        st.session_state.user_portfolio = []
        st.rerun()

    st.divider()

    if st.session_state.portfolio_submitted:
        st.markdown(
            f'<div style="font-size:11px;color:{DIM};font-weight:600;'
            f'text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">'
            f'{"My Portfolio" if st.session_state.page_mode == "personal" else "Your Portfolio"}</div>',
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
        with st.expander("Add Stock", expanded=False):
            add_mode = st.radio("Action", ["Add shares", "Reduce position (sold)"], key="add_mode",
                                horizontal=True)
            add_ticker = st.text_input("Ticker", key="add_ticker", placeholder="e.g. AAPL")
            with st.form("add_stock_form", clear_on_submit=False, enter_to_submit=False):
                add_shares = st.number_input("Shares", min_value=0.0, step=1.0, key="add_shares", value=0.0)
                add_avg = st.number_input("Avg Cost ($)", min_value=0.0, step=0.01, key="add_avg", value=0.0,
                                          help="For 'Add shares': cost per share. For 'Reduce': optional (price sold at).")
                form_submitted = st.form_submit_button("Update Portfolio")
            if form_submitted:
                tk = (add_ticker or "").upper().strip()
                current = list(st.session_state.user_portfolio)
                existing = next((p for p in current if p["ticker"] == tk), None)

                if add_mode == "Add shares":
                    if tk and add_shares > 0 and add_avg > 0:
                        if existing:
                            # Average in: new_avg = (old_shares*old_avg + new_shares*new_avg) / total_shares
                            old_s, old_a = existing["shares"], existing["avg_cost"]
                            new_s = old_s + add_shares
                            new_avg = (old_s * old_a + add_shares * add_avg) / new_s
                            existing["shares"] = round(new_s, 2)
                            existing["avg_cost"] = round(new_avg, 2)
                            st.success(f"Added {add_shares:.0f} shares of {tk}. New avg cost: ${new_avg:.2f}")
                        else:
                            current.append({"ticker": tk, "shares": add_shares, "avg_cost": add_avg})
                            st.success(f"Added {tk} to portfolio.")
                        st.session_state.user_portfolio = current
                        st.session_state.portfolio_version = st.session_state.get("portfolio_version", 0) + 1
                        for k in ("holdings", "_live_holdings"):
                            st.session_state.pop(k, None)
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Enter ticker, shares, and avg cost.")
                else:
                    # Reduce position (sold)
                    if tk and add_shares > 0 and existing:
                        old_s = existing["shares"]
                        if add_shares >= old_s:
                            current = [p for p in current if p["ticker"] != tk]
                            st.success(f"Removed {tk} (sold full position).")
                        else:
                            existing["shares"] = round(old_s - add_shares, 2)
                            st.success(f"Reduced {tk} by {add_shares:.0f} shares. Remaining: {existing['shares']:.0f}")
                        st.session_state.user_portfolio = current
                        st.session_state.portfolio_version = st.session_state.get("portfolio_version", 0) + 1
                        for k in ("holdings", "_live_holdings"):
                            st.session_state.pop(k, None)
                        st.cache_data.clear()
                        st.rerun()
                    elif not existing:
                        st.error(f"{tk} is not in your portfolio.")
                    else:
                        st.error("Enter ticker and shares sold.")
        st.divider()
        if st.session_state.page_mode == "custom":
            if st.button("Start Over", use_container_width=True):
                st.session_state.portfolio_submitted = False
                st.session_state.user_portfolio = []
                st.session_state.user_email = ""
                for k in ("holdings", "_live_holdings", "risk_d", "sp", "picks_m", "picks_s", "macro", "email_sent", "email_error"):
                    st.session_state.pop(k, None)
                st.cache_data.clear()
                st.rerun()
        if st.button("Refresh Data", use_container_width=True, type="primary"):
            for k in ("holdings", "_live_holdings", "risk_d", "sp", "picks_m", "picks_s", "macro"):
                st.session_state.pop(k, None)
            st.cache_data.clear()
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
    <div style="font-size:13px;color:{DIM};text-align:center;line-height:1.6;">
      Data: Yahoo Finance | Finnhub | Google News<br>Not financial advice
    </div>""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════
#  PAGE 1: INPUT FORM  (shown when custom mode and not submitted)
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

        with st.form("portfolio_form"):
            num = st.number_input(
                "How many stocks?", min_value=1, max_value=20, value=st.session_state.num_stocks,
                key="num_input",
            )
            form_tickers = []
            for i in range(int(num)):
                st.markdown(
                    f'<div style="font-size:12px;color:{AMBER};font-weight:600;margin-top:10px;">'
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
                st.session_state.portfolio_version = st.session_state.get("portfolio_version", 0) + 1
                for k in ("holdings", "_live_holdings", "risk_d", "sp", "picks_m", "picks_s", "macro"):
                    st.session_state.pop(k, None)
                st.rerun()
            else:
                st.error("Please enter at least one stock with shares and avg cost filled in.")

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
#  PAGE 2: DASHBOARD  (shown after submission or in personal mode)
# ═════════════════════════════════════════════════════════════════
if st.session_state.portfolio_submitted:
    user_portfolio = st.session_state.user_portfolio
    user_email = st.session_state.user_email

    # ── HEAVY ANALYSIS: run once, store in session state ───────────────────
    if "holdings" not in st.session_state:
        loading = st.empty()
        loading.markdown(f"""
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                    min-height:60vh;text-align:center;">
          <style>
            @keyframes pulse-ring {{ 0% {{ transform: scale(0.8); opacity: 1; }} 50% {{ transform: scale(1.2); opacity: 0.4; }} 100% {{ transform: scale(0.8); opacity: 1; }} }}
            .load-icon {{ width: 80px; height: 80px; border-radius: 50%; background: linear-gradient(135deg, {AMBER}, {GREEN});
              display: flex; align-items: center; justify-content: center; animation: pulse-ring 1.5s ease-in-out infinite; margin-bottom: 24px; }}
          </style>
          <div class="load-icon"><svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="{CARD}" stroke-width="2.5"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg></div>
          <div style="font-size:22px;font-weight:800;color:{WHITE};">Analyzing Your Portfolio</div>
          <div style="font-size:13px;color:{DIM};margin-top:8px;">Fetching data, computing technicals...</div>
        </div>""", unsafe_allow_html=True)
        with st.spinner("Fetching market data..."):
            sp = load_market()
        with st.spinner("Running signal analysis..."):
            picks_m, picks_s = load_picks()
        with st.spinner("Loading news & risk data..."):
            macro, catalysts = load_news()
            holdings = analyse_user_portfolio(user_portfolio)
            risk_d = compute_risk_dashboard(holdings)
        _live = get_live_prices(tuple(h["ticker"] for h in holdings))
        for h in holdings:
            ld = _live.get(h["ticker"], {})
            if ld.get("price", 0) > 0:
                lp = ld["price"]
                h["current_price"] = round(lp, 2)
                h["day_pnl"] = round(ld["change"] * h["shares"], 2)
                h["day_pnl_pct"] = round(ld["change_pct"], 2)
                h["market_value"] = round(lp * h["shares"], 2)
                h["open_pnl"] = round(h["market_value"] - h["total_cost"], 2)
                h["open_pnl_pct"] = round((lp - h["avg_cost"]) / h["avg_cost"] * 100, 2)
        st.session_state.holdings = holdings
        st.session_state._live_holdings = holdings  # Initial display; KPI fragment will refresh
        st.session_state.risk_d = risk_d
        st.session_state.sp = sp
        st.session_state.picks_m = picks_m
        st.session_state.picks_s = picks_s
        st.session_state.macro = macro
        if user_email and "@" in user_email:
            es, ee = send_user_email(user_email, holdings, risk_d, sp, picks_m, picks_s)
            st.session_state.email_sent = es
            st.session_state.email_error = ee
        else:
            st.session_state.email_sent = None
            st.session_state.email_error = None
        loading.empty()

    holdings = st.session_state.holdings
    risk_d = st.session_state.risk_d
    sp = st.session_state.sp
    picks_m = st.session_state.picks_m
    picks_s = st.session_state.picks_s
    macro = st.session_state.macro
    email_sent = st.session_state.get("email_sent")
    email_error = st.session_state.get("email_error")

    # ── HEADER + TICKER TAPE ──────────────────────────────────────────────
    mood_c = GREEN if sp["spy_mood"] == "Bullish" else RED if sp["spy_mood"] == "Bearish" else AMBER
    _open = is_market_open()
    _dot = '<span class="live-dot"></span>' if _open else '<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#334155;margin-right:6px;vertical-align:middle;"></span>'
    _live_label = "15-MIN DELAY" if _open else "MARKET CLOSED"
    _live_col   = AMBER if _open else DIM
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{CARD},{ALT});border-radius:12px;
                padding:20px 26px;margin-bottom:10px;border:1px solid {BORDER};">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
        <div>
          <span style="font-size:22px;font-weight:800;color:{WHITE};">{"My Stock Analysis" if st.session_state.page_mode == "personal" else "Your Stock Analysis"}</span>
          <span style="font-size:13px;color:{DIM};margin-left:14px;">{datetime.datetime.now().strftime("%I:%M %p")}</span>
        </div>
        <div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap;">
          <div>
            <span style="color:{DIM};font-size:13px;">S&amp;P 500</span>
            <span style="font-size:20px;font-weight:800;color:{WHITE};margin-left:8px;">{dlr(sp['price'])}</span>
            <span style="color:{clr(sp['change'])};font-weight:700;font-size:15px;margin-left:8px;">{pct(sp['change'])}</span>
          </div>
          <span style="color:{mood_c};font-weight:700;font-size:15px;">SPY {sp['spy_mood']}</span>
          <span style="font-size:13px;font-weight:700;color:{_live_col};">{_dot}{_live_label}</span>
          <span style="font-size:11px;color:{DIM};margin-left:8px;">Updated {datetime.datetime.now(pytz.timezone("America/New_York")).strftime("%I:%M:%S %p ET")}</span>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    # Ticker tape (fragment refreshes every 15s — no full page re-run)
    @st.fragment(run_every=15)
    def render_ticker_tape():
        _h = st.session_state.get("_live_holdings") or st.session_state.get("holdings", [])
        if not _h:
            return
        _tape_list = (
            tuple(h["ticker"] for h in _h)
            + ("SPY", "QQQ", "NVDA", "AAPL", "TSLA")
            + ("BTC-USD", "ETH-USD", "SOL-USD")
        )
        _tape_px = get_live_prices(_tape_list)
        def _ti(tk):
            d = _tape_px.get(tk, {}); p = d.get("price", 0); c = d.get("change_pct", 0)
            col = GREEN if c >= 0 else RED; arr = "▲" if c >= 0 else "▼"
            return (f'<span style="margin:0 28px;white-space:nowrap;">'
                    f'<span style="color:{WHITE};font-weight:700;">{tk}</span>'
                    f'&nbsp;<span style="color:#94A3B8;">${p:,.2f}</span>'
                    f'&nbsp;<span style="color:{col};font-weight:700;">{arr}{abs(c):.2f}%</span>'
                    f'</span>')
        _tape = "".join(_ti(tk) for tk in _tape_list) * 3
        et = pytz.timezone("America/New_York")
        last_fetch = datetime.datetime.now(et).strftime("%I:%M:%S %p ET")
        st.markdown(f"""
        <div style="overflow:hidden;background:{BG};border-top:1px solid {BORDER};
                    border-bottom:1px solid {BORDER};padding:9px 0;margin-bottom:4px;">
          <div style="display:inline-block;animation:ticker-scroll 40s linear infinite;
                      white-space:nowrap;font-family:'Courier New',monospace;font-size:13px;">
            {_tape}
          </div>
        </div>
        <div style="font-size:11px;color:{DIM};text-align:right;padding-right:8px;margin-bottom:14px;">
          Updated {last_fetch} · 15-min delayed
        </div>""", unsafe_allow_html=True)

    render_ticker_tape()

    if email_sent is True:
        st.success(f"Report sent to {user_email}!")
    elif user_email and email_sent is False:
        detail = f" ({email_error})" if email_error else ""
        st.warning(f"Could not send email{detail} -- but your dashboard is ready below.")

    # KPI row (fragment refreshes every 20s — fetches prices, stores _live_holdings)
    @st.fragment(run_every=20)
    def render_kpi_row():
        _h = st.session_state.get("holdings", [])
        if not _h:
            return
        live = get_live_prices(tuple(h["ticker"] for h in _h))
        h_copy = [dict(h) for h in _h]
        for h in h_copy:
            d = live.get(h["ticker"], {})
            if d.get("price"):
                lp = d["price"]
                h["current_price"] = round(lp, 2)
                h["market_value"] = round(lp * h["shares"], 2)
                h["day_pnl"] = round(d.get("change", 0) * h["shares"], 2)
                h["day_pnl_pct"] = round(d.get("change_pct", 0), 2)
                h["open_pnl"] = round(h["market_value"] - h["total_cost"], 2)
                h["open_pnl_pct"] = round((lp - h["avg_cost"]) / h["avg_cost"] * 100, 2) if h["avg_cost"] else 0
        st.session_state._live_holdings = h_copy
        tv = sum(h["market_value"] for h in h_copy)
        tc = sum(h["total_cost"] for h in h_copy)
        tp = tv - tc
        tpc = tp / tc * 100 if tc else 0
        tdp = sum(h["day_pnl"] for h in h_copy)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Portfolio Value", dlr(tv))
        k2.metric("Total Cost", dlr(tc))
        k3.metric("Open P&L", dlr(tp), delta=pct(tpc))
        k4.metric("Today's P&L", dlr(tdp))

    render_kpi_row()

    # Use live-updated holdings for display (portfolio cards, technicals)
    _display_holdings = st.session_state.get("_live_holdings") or holdings

    # ── TABS ──
    tab_port, tab_picks, tab_tech, tab_risk, tab_crypto = st.tabs(
        ["Portfolio", "Trade Ideas", "Technicals", "Risk & News", "Crypto"]
    )

    # ──── PORTFOLIO TAB ────
    with tab_port:
        _pnl_fig = build_pnl_bar(_display_holdings)
        if _pnl_fig:
            st.plotly_chart(_pnl_fig, use_container_width=True,
                            config={"displayModeBar": False}, key="pnl_bar")

        for h in _display_holdings:
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
              <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                <div style="display:flex;align-items:baseline;gap:10px;">
                  <span class="card-ticker">{h["ticker"]}</span>
                  <span class="card-name">{h["name"]}</span>
                </div>
                <div style="display:flex;align-items:center;gap:12px;">
                  <span style="font-size:22px;font-weight:800;color:{WHITE};">{dlr(h["current_price"])}</span>
                  <span style="font-size:16px;font-weight:700;color:{clr(h['day_pnl_pct'])}">{pct(h['day_pnl_pct'])}</span>
                  {sig_badge(h["signal"])}
                </div>
              </div>
              <div class="card-reason">{h["reason"]}</div>
              <div class="card-action">Action: {h["action"]}</div>
              <div style="font-size:13px;color:{DIM};font-style:italic;margin-top:4px;">{h.get("strategy_note","")}</div>
              <div style="display:flex;gap:20px;margin-top:14px;flex-wrap:wrap;">
                <div><div class="kpi-label">Avg Cost</div><div class="kpi-value" style="color:{TEXT};">{dlr(h["avg_cost"])}</div></div>
                <div><div class="kpi-label">Shares</div><div class="kpi-value" style="color:{WHITE};">{int(h["shares"])}</div></div>
                <div><div class="kpi-label">PE</div><div class="kpi-value" style="color:{AMBER};">{pe_s}</div></div>
                <div><div class="kpi-label">RSI</div><div class="kpi-value" style="color:{WHITE};">{rsi_s}</div></div>
                <div><div class="kpi-label">Open P&L</div><div class="kpi-value" style="color:{oc};">{"+" if h["open_pnl"]>=0 else ""}{dlr(h["open_pnl"])} <span style="font-size:13px;">({pct(h["open_pnl_pct"])})</span></div></div>
                <div><div class="kpi-label">Day P&L</div><div class="kpi-value" style="color:{dc};">{"+" if h["day_pnl"]>=0 else ""}{dlr(h["day_pnl"])} <span style="font-size:13px;">({pct(h["day_pnl_pct"])})</span></div></div>
              </div>
              <div class="card-info">{info_html}</div>
              <div class="card-timeline">
                <div class="timeline-label">Short-term (0-30d):</div><div>{tl["short_level"]}<br>{tl["short_trigger"]}</div>
                <div class="timeline-label">Medium-term (1-6mo):</div><div>{tl["med_catalyst"]}<br>{tl["med_target"]}</div>
                <div class="timeline-label">Long-term (6-24mo):</div><div>{tl["long_thesis"]}<br>Invalidate: {tl["long_invalidate"]}</div>
              </div>
            </div>""", unsafe_allow_html=True)
            chart = sparkline_chart(h["ticker"])
            if chart:
                st.plotly_chart(chart, use_container_width=True, config={"displayModeBar": False},
                                key=f"spark_{h['ticker']}")
            _fig = build_price_chart(h["ticker"], h["avg_cost"], h["tech"])
            st.plotly_chart(_fig, use_container_width=True,
                            config={"displayModeBar": True,
                                    "modeBarButtonsToRemove": ["autoScale2d", "lasso2d", "select2d"],
                                    "displaylogo": False},
                            key=f"price_chart_{h['ticker']}")

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
        _tech_tickers = list({h["ticker"]: h for h in _display_holdings}.keys())
        if len(_tech_tickers) > 1:
            _sel = st.selectbox("Select ticker to chart", _tech_tickers,
                                key="tech_ticker_sel")
        else:
            _sel = _tech_tickers[0] if _tech_tickers else None

        if _sel:
            _sel_holding = next((h for h in _display_holdings if h["ticker"] == _sel), None)
            _avg = _sel_holding["avg_cost"] if _sel_holding else 0
            _tech_fig = build_price_chart(_sel, _avg,
                                          _sel_holding.get("tech", {}) if _sel_holding else {})
            st.plotly_chart(_tech_fig, use_container_width=True,
                            config={"displayModeBar": True,
                                    "modeBarButtonsToRemove": ["autoScale2d", "lasso2d", "select2d"],
                                    "displaylogo": False},
                            key=f"tech_chart_{_sel}")

        seen = set(); rows = []
        for h in _display_holdings:
            tk = h["ticker"]; t = h["tech"]
            if tk in seen: continue
            seen.add(tk)
            rows.append({
                "Ticker": tk, "Price": f"${h['current_price']:,.2f}",
                "RSI": f'{t["rsi"]:.0f}' if t.get("rsi") is not None else "N/A",
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

        _rc1, _rc2 = st.columns([1, 1])
        with _rc1:
            _alloc_fig = build_allocation_bar(_display_holdings)
            if _alloc_fig:
                st.plotly_chart(_alloc_fig, use_container_width=True,
                                config={"displayModeBar": False}, key="alloc_bar")
        with _rc2:
            _donut_fig = build_sector_donut(risk_d)
            if _donut_fig:
                st.plotly_chart(_donut_fig, use_container_width=True,
                                config={"displayModeBar": False}, key="sector_donut")

        if risk_d["positions"]:
            pdf = pd.DataFrame(risk_d["positions"])
            pdf = pdf.rename(columns={"ticker": "Ticker", "weight": "Weight %", "beta": "Beta", "risk_1d": "1-Day Risk $"})
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
                st.markdown(f'<div class="news-item">{title}<span style="color:{DIM};font-size:13px;">{pub}</span></div>', unsafe_allow_html=True)
        if macro["risks"]:
            rdf = pd.DataFrame(macro["risks"])
            rdf.columns = [c.title() for c in rdf.columns]
            st.dataframe(rdf, use_container_width=True, hide_index=True)

    # ──── CRYPTO TAB ────
    with tab_crypto:
        fg = get_fear_greed()
        fg_val, fg_lbl = fg.get("value", 50), fg.get("label", "Neutral")
        fg_col = GREEN if fg_val > 60 else RED if fg_val < 40 else AMBER
        st.metric("Fear & Greed Index", f"{fg_val} — {fg_lbl}", delta=None)
        st.markdown(f'<div style="font-size:12px;color:{DIM};margin-bottom:16px;">'
                    f'<span style="color:{fg_col};font-weight:700;">{fg_val}/100</span> — '
                    f'Green = Greed, Red = Fear, Amber = Neutral</div>', unsafe_allow_html=True)

        crypto_data = get_crypto_prices()
        coin_map = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL", "binancecoin": "BNB", "ripple": "XRP"}
        yf_map = {"bitcoin": "BTC-USD", "ethereum": "ETH-USD", "solana": "SOL-USD", "binancecoin": "BNB-USD", "ripple": "XRP-USD"}

        for cid, sym in coin_map.items():
            d = crypto_data.get(cid, {})
            price = d.get("usd", 0) or 0
            chg = d.get("usd_24h_change") or 0
            mcap = d.get("usd_market_cap") or 0
            mcap_s = f"${mcap/1e9:.1f}B" if mcap >= 1e9 else f"${mcap/1e6:.0f}M"
            col = GREEN if chg >= 0 else RED
            st.markdown(f"""
            <div class="stock-card">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="font-size:18px;font-weight:800;color:{WHITE};">{sym}</span>
                <span style="font-size:16px;font-weight:700;color:{WHITE};">${price:,.2f}</span>
                <span style="color:{col};font-weight:700;">{chg:+.2f}%</span>
                <span style="font-size:12px;color:{DIM};">MCap: {mcap_s}</span>
              </div>
            </div>""", unsafe_allow_html=True)

        st.markdown(f'<div style="font-size:14px;font-weight:700;color:{WHITE};margin:20px 0 10px;">Technicals (yfinance)</div>', unsafe_allow_html=True)
        crypto_tech_rows = []
        for cid, sym in coin_map.items():
            yf_tk = yf_map.get(cid, f"{sym}-USD")
            tech = compute_technicals(yf_tk)
            crypto_tech_rows.append({
                "Coin": sym,
                "RSI": f'{tech["rsi"]:.0f}' if tech.get("rsi") is not None else "N/A",
                "RSI Signal": tech.get("rsi_label", "N/A"),
                "MACD": tech.get("macd_label", "N/A"),
                "EMA": tech.get("ema_label", "N/A"),
            })
        if crypto_tech_rows:
            st.dataframe(pd.DataFrame(crypto_tech_rows), use_container_width=True, hide_index=True)

        st.markdown(f'<div style="font-size:11px;color:{DIM};margin-top:16px;font-style:italic;">'
                    f'Crypto trades 24/7. Technical indicators apply standard stock logic.</div>', unsafe_allow_html=True)
