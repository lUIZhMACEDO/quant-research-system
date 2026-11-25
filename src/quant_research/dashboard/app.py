"""Streamlit dashboard.

Run with ``streamlit run app.py`` (the root ``app.py`` calls :func:`main`). Streamlit
re-executes the script on every interaction, so all page rendering lives inside
``main()`` while cached loaders live at module level.

Access is gated by ``APP_PASSWORD`` (Streamlit secrets or env). If it is not
configured the dashboard refuses to render rather than running unprotected.
"""

from __future__ import annotations

import datetime as dt
import hmac
import os
from html import escape

import pandas as pd
import streamlit as st

from quant_research.config import Settings, get_settings, reset_settings
from quant_research.dashboard.charts import (
    build_allocation_bar,
    build_pnl_bar,
    build_price_chart,
    build_sector_donut,
    sparkline_chart,
)
from quant_research.dashboard.components import (
    NY,
    apply_live_prices,
    clr,
    dlr,
    get_live_prices,
    is_market_open,
    is_valid_email,
    pct,
    pick_card,
    safe_link,
    sig_badge,
)
from quant_research.dashboard.theme import (
    ALT,
    AMBER,
    BG,
    BORDER,
    CARD,
    DIM,
    GREEN,
    RED,
    STARFIELD_CSS,
    TEXT,
    WHITE,
    layout_css,
)
from quant_research.reporting.emailer import send_email
from quant_research.reporting.user_report import build_user_report
from quant_research.research.market import (
    analyse_stocks,
    fetch_market_summary,
    fetch_sp500_tickers,
    get_crypto_prices,
    get_fear_greed,
    get_top_movers,
)
from quant_research.research.news import get_macro_news
from quant_research.research.portfolio import (
    analyse_user_portfolio,
    catalyst_universe,
    compute_risk_dashboard,
    enrich_picks,
)
from quant_research.research.ticker_data import compute_technicals, get_weekly_catalysts
from quant_research.watchlist import MACRO_KEYWORDS, MOMENTUM_PICKS, SWING_PICKS, load_portfolio

APP_VERSION = "4.0.0"

# Keys copied from Streamlit secrets into the environment (only when present there).
SECRET_KEYS = (
    "APP_PASSWORD",
    "EMAIL_PASSWORD",
    "SENDER_EMAIL",
    "RECIPIENT_EMAIL",
    "SMTP_HOST",
    "SMTP_PORT",
    "FINNHUB_API_KEY",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "PUBLIC_MODE",
)

# Session keys holding analysis results; cleared whenever the portfolio changes.
RESULT_KEYS = ("holdings", "_live_holdings", "risk_d", "sp", "picks_m", "picks_s", "macro")


# ─────────────────────────────────────────────────────────────────
#  Cached data (shared across sessions)
# ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner="Fetching market data...")
def load_market():
    return fetch_market_summary()


@st.cache_data(ttl=1800, show_spinner="Loading trade ideas...")
def load_picks():
    return enrich_picks(MOMENTUM_PICKS), enrich_picks(SWING_PICKS)


@st.cache_data(ttl=1800, show_spinner="Loading news...")
def load_news(owner_tickers: tuple[str, ...]):
    owner = [{"ticker": t} for t in owner_tickers]
    return get_macro_news(list(owner_tickers), MACRO_KEYWORDS), get_weekly_catalysts(catalyst_universe(owner))


@st.cache_data(ttl=3600, show_spinner="Scanning S&P 500 (may take a few minutes)...")
def load_sp500():
    df = analyse_stocks(fetch_sp500_tickers())
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    return get_top_movers(df)


# ─────────────────────────────────────────────────────────────────
#  Setup helpers
# ─────────────────────────────────────────────────────────────────
def _bridge_streamlit_secrets() -> Settings:
    """Copy configured Streamlit secrets into the env, then (re)load settings."""
    for key in SECRET_KEYS:
        if key in os.environ:
            continue
        try:
            if key in st.secrets:
                os.environ[key] = str(st.secrets[key])
        except Exception:  # no secrets.toml locally: rely on env / .env
            break
    reset_settings()
    return get_settings()


def _password_gate(settings: Settings) -> None:
    """Block the page until the correct APP_PASSWORD is entered (constant-time compare)."""
    if st.session_state.get("authenticated"):
        return
    if not settings.app_password:
        st.error(
            "This dashboard is locked: APP_PASSWORD is not configured. "
            "Add it to Streamlit secrets or your local .env file."
        )
        st.stop()

    st.markdown(
        """
    <div style="display:flex;flex-direction:column;align-items:center;
                justify-content:center;min-height:60vh;text-align:center;">
        <div style="font-size:32px;font-weight:900;color:#ffffff;margin-bottom:8px;">
            \U0001f512 Access Restricted</div>
        <div style="font-size:15px;color:#6b7280;margin-bottom:32px;">
            Enter the password to continue.</div>
    </div>""",
        unsafe_allow_html=True,
    )
    pwd_input = st.text_input(
        "Password", type="password", key="pwd_gate", label_visibility="collapsed", placeholder="Enter password..."
    )
    if st.button("Unlock", type="primary"):
        if hmac.compare_digest(pwd_input.encode("utf-8"), settings.app_password.encode("utf-8")):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()


def _clear_results(*extra: str) -> None:
    for k in RESULT_KEYS + extra:
        st.session_state.pop(k, None)


def _init_session(settings: Settings, owner_portfolio: list[dict]) -> None:
    defaults = {
        "page_mode": "custom" if settings.public_mode else "personal",
        "portfolio_submitted": not settings.public_mode,
        "user_portfolio": [] if settings.public_mode else owner_portfolio,
        "user_email": "",
        "num_stocks": 1,
        "portfolio_version": 0,  # bumped when the portfolio changes -> re-run analysis
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _send_user_report(
    recipient: str, holdings: list[dict], risk_d: dict, sp: dict, settings: Settings
) -> tuple[bool, str | None]:
    if not settings.email_configured:
        return False, "EMAIL_PASSWORD or SENDER_EMAIL not configured in Streamlit secrets"
    html, text = build_user_report(holdings, risk_d, sp)
    try:
        send_email(settings, f"Stock Report -- {dt.date.today()}", text, html, recipient=recipient, ssl_fallback=True)
        return True, None
    except Exception as exc:
        return False, str(exc)


# ─────────────────────────────────────────────────────────────────
#  Sidebar
# ─────────────────────────────────────────────────────────────────
def _render_sidebar(settings: Settings, owner_portfolio: list[dict]) -> None:
    ss = st.session_state
    with st.sidebar:
        st.markdown(
            f"""
        <div style="text-align:center;padding:10px 0 4px;">
          <div style="font-size:22px;font-weight:800;color:{WHITE};">Stock Analyst</div>
          <div style="font-size:11px;color:{DIM};margin-top:2px;">FREE PORTFOLIO ANALYZER</div>
        </div>""",
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="text-align:center;color:{DIM};font-size:12px;">'
            f'{dt.date.today().strftime("%A, %B %d, %Y")}</div>',
            unsafe_allow_html=True,
        )
        st.divider()

        # In public mode only "Analyze Stocks" is offered.
        if not settings.public_mode:
            if st.button(
                "My Portfolio", use_container_width=True, type="primary" if ss.page_mode == "personal" else "secondary"
            ):
                ss.page_mode = "personal"
                ss.user_portfolio = owner_portfolio
                ss.portfolio_submitted = True
                st.rerun()
        if st.button(
            "Analyze Stocks", use_container_width=True, type="primary" if ss.page_mode == "custom" else "secondary"
        ):
            ss.page_mode = "custom"
            ss.portfolio_submitted = False
            ss.user_portfolio = []
            st.rerun()
        st.divider()

        if ss.portfolio_submitted:
            st.markdown(
                f'<div style="font-size:11px;color:{DIM};font-weight:600;text-transform:uppercase;'
                f'letter-spacing:1px;margin-bottom:6px;">'
                f'{"My Portfolio" if ss.page_mode == "personal" else "Your Portfolio"}</div>',
                unsafe_allow_html=True,
            )
            for p in ss.user_portfolio:
                st.markdown(
                    f'<div style="padding:4px 0;font-size:13px;">'
                    f'<span style="color:{WHITE};font-weight:700;">{escape(p["ticker"])}</span>'
                    f' <span style="color:{DIM};">-- {p["shares"]} @ {dlr(p["avg_cost"])}</span></div>',
                    unsafe_allow_html=True,
                )
            st.divider()
            _render_position_editor()
            st.divider()
            if ss.page_mode == "custom" and st.button("Start Over", use_container_width=True):
                ss.portfolio_submitted = False
                ss.user_portfolio = []
                ss.user_email = ""
                _clear_results("email_sent", "email_error")
                st.cache_data.clear()
                st.rerun()
            if st.button("Refresh Data", use_container_width=True, type="primary"):
                _clear_results()
                st.cache_data.clear()
                st.rerun()
        else:
            st.markdown(
                f'<div style="font-size:12px;color:{TEXT};line-height:1.6;">'
                f'Enter your stocks on the right to get a free personalized analysis '
                f'with signals, technicals, and a full report sent to your email.</div>',
                unsafe_allow_html=True,
            )

        st.divider()
        st.markdown(
            f"""
        <div style="font-size:13px;color:{DIM};text-align:center;line-height:1.6;">
          Data: Yahoo Finance | Finnhub | Google News<br>Not financial advice
        </div>""",
            unsafe_allow_html=True,
        )


def _render_position_editor() -> None:
    ss = st.session_state
    with st.expander("Add Stock", expanded=False):
        add_mode = st.radio("Action", ["Add shares", "Reduce position (sold)"], key="add_mode", horizontal=True)
        add_ticker = st.text_input("Ticker", key="add_ticker", placeholder="e.g. AAPL")
        with st.form("add_stock_form", clear_on_submit=False, enter_to_submit=False):
            add_shares = st.number_input("Shares", min_value=0.0, step=1.0, key="add_shares", value=0.0)
            add_avg = st.number_input(
                "Avg Cost ($)",
                min_value=0.0,
                step=0.01,
                key="add_avg",
                value=0.0,
                help="For 'Add shares': cost per share. For 'Reduce': optional (price sold at).",
            )
            form_submitted = st.form_submit_button("Update Portfolio")
        if not form_submitted:
            return
        tk = (add_ticker or "").upper().strip()
        current = [dict(p) for p in ss.user_portfolio]
        existing = next((p for p in current if p["ticker"] == tk), None)

        if add_mode == "Add shares":
            if not (tk and add_shares > 0 and add_avg > 0):
                st.error("Enter ticker, shares, and avg cost.")
                return
            if existing:
                old_s, old_a = existing["shares"], existing["avg_cost"]
                new_s = old_s + add_shares
                new_avg = (old_s * old_a + add_shares * add_avg) / new_s
                existing["shares"] = round(new_s, 2)
                existing["avg_cost"] = round(new_avg, 2)
                st.success(f"Added {add_shares:.0f} shares of {tk}. New avg cost: ${new_avg:.2f}")
            else:
                current.append({"ticker": tk, "shares": add_shares, "avg_cost": add_avg})
                st.success(f"Added {tk} to portfolio.")
        else:
            if not existing:
                st.error(f"{tk} is not in your portfolio.")
                return
            if not (tk and add_shares > 0):
                st.error("Enter ticker and shares sold.")
                return
            if add_shares >= existing["shares"]:
                current = [p for p in current if p["ticker"] != tk]
                st.success(f"Removed {tk} (sold full position).")
            else:
                existing["shares"] = round(existing["shares"] - add_shares, 2)
                st.success(f"Reduced {tk} by {add_shares:.0f} shares. Remaining: {existing['shares']:.0f}")

        ss.user_portfolio = current
        ss.portfolio_version = ss.get("portfolio_version", 0) + 1
        for k in ("holdings", "_live_holdings"):
            ss.pop(k, None)
        st.cache_data.clear()
        st.rerun()


# ─────────────────────────────────────────────────────────────────
#  Page 1: input form
# ─────────────────────────────────────────────────────────────────
def _render_input_form() -> None:
    ss = st.session_state
    st.markdown(
        """
    <div style="text-align:center;margin:40px 0 20px;">
      <div class="hero-title">Get Your Free Stock Analysis</div>
      <div class="hero-sub">
        Enter your positions below. We'll analyze every stock with<br>
        technical indicators, PE ratios, analyst ratings, news, and<br>
        send a professional report straight to your inbox.
      </div>
    </div>""",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    col_form, col_preview = st.columns([3, 2])
    with col_form:
        st.markdown(
            f'<div style="font-size:16px;font-weight:700;color:{WHITE};margin-bottom:12px;">Your Positions</div>',
            unsafe_allow_html=True,
        )
        with st.form("portfolio_form"):
            num = st.number_input("How many stocks?", min_value=1, max_value=20, value=ss.num_stocks, key="num_input")
            form_rows = []
            for i in range(int(num)):
                st.markdown(
                    f'<div style="font-size:12px;color:{AMBER};font-weight:600;margin-top:10px;">Stock #{i + 1}</div>',
                    unsafe_allow_html=True,
                )
                c1, c2, c3 = st.columns(3)
                ticker = c1.text_input("Ticker", key=f"ticker_{i}", placeholder="e.g. AAPL")
                shares = c2.number_input("Shares", min_value=0.0, step=1.0, key=f"shares_{i}", value=0.0)
                avg_cost = c3.number_input("Avg Cost ($)", min_value=0.0, step=0.01, key=f"avg_{i}", value=0.0)
                form_rows.append((ticker, shares, avg_cost))
            st.markdown("---")
            user_email = st.text_input("Your Email (for the report)", placeholder="you@example.com")
            submitted = st.form_submit_button("Analyze My Portfolio", use_container_width=True, type="primary")

        if submitted:
            ss.num_stocks = int(num)
            stocks = [
                {"ticker": t.upper().strip(), "shares": s, "avg_cost": a}
                for t, s, a in form_rows
                if t.strip() and s > 0 and a > 0
            ]
            if not stocks:
                st.error("Please enter at least one stock with shares and avg cost filled in.")
            elif user_email.strip() and not is_valid_email(user_email):
                st.error("Please enter a single valid email address, or leave it blank.")
            else:
                ss.user_portfolio = stocks
                ss.user_email = user_email.strip()
                ss.portfolio_submitted = True
                ss.portfolio_version = ss.get("portfolio_version", 0) + 1
                _clear_results()
                st.rerun()

    with col_preview:
        st.markdown(
            f'<div style="font-size:16px;font-weight:700;color:{WHITE};margin-bottom:12px;">What You Get</div>',
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
            st.markdown(
                f"""
            <div style="padding:8px 0;border-bottom:1px solid {BORDER};">
              <div style="font-size:13px;font-weight:700;color:{GREEN};">{title}</div>
              <div style="font-size:11px;color:{DIM};">{desc}</div>
            </div>""",
                unsafe_allow_html=True,
            )


# ─────────────────────────────────────────────────────────────────
#  Page 2: dashboard
# ─────────────────────────────────────────────────────────────────
def _run_analysis(settings: Settings, owner_portfolio: list[dict]) -> None:
    ss = st.session_state
    loading = st.empty()
    loading.markdown(
        f"""
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
    </div>""",
        unsafe_allow_html=True,
    )
    with st.spinner("Fetching market data..."):
        sp = load_market()
    with st.spinner("Running signal analysis..."):
        picks_m, picks_s = load_picks()
    with st.spinner("Loading news & risk data..."):
        macro, _catalysts = load_news(tuple(p["ticker"] for p in owner_portfolio))
        holdings = analyse_user_portfolio(ss.user_portfolio)
        risk_d = compute_risk_dashboard(holdings)
    holdings = apply_live_prices(holdings, get_live_prices(tuple(h["ticker"] for h in holdings)))

    ss.holdings = holdings
    ss._live_holdings = holdings  # initial display; the KPI fragment keeps it fresh
    ss.risk_d, ss.sp, ss.picks_m, ss.picks_s, ss.macro = risk_d, sp, picks_m, picks_s, macro
    if ss.user_email and is_valid_email(ss.user_email):
        ss.email_sent, ss.email_error = _send_user_report(ss.user_email, holdings, risk_d, sp, settings)
    else:
        ss.email_sent, ss.email_error = None, None
    loading.empty()


def _render_header(sp: dict) -> None:
    mood_c = GREEN if sp["spy_mood"] == "Bullish" else RED if sp["spy_mood"] == "Bearish" else AMBER
    is_open = is_market_open()
    dot = (
        '<span class="live-dot"></span>'
        if is_open
        else '<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:#334155;'
        'margin-right:6px;vertical-align:middle;"></span>'
    )
    live_label = "15-MIN DELAY" if is_open else "MARKET CLOSED"
    live_col = AMBER if is_open else DIM
    title = "My Stock Analysis" if st.session_state.page_mode == "personal" else "Your Stock Analysis"
    st.markdown(
        f"""
    <div style="background:linear-gradient(135deg,{CARD},{ALT});border-radius:12px;
                padding:20px 26px;margin-bottom:10px;border:1px solid {BORDER};">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
        <div>
          <span style="font-size:22px;font-weight:800;color:{WHITE};">{title}</span>
          <span style="font-size:13px;color:{DIM};margin-left:14px;">{dt.datetime.now().strftime("%I:%M %p")}</span>
        </div>
        <div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap;">
          <div>
            <span style="color:{DIM};font-size:13px;">S&amp;P 500</span>
            <span style="font-size:20px;font-weight:800;color:{WHITE};margin-left:8px;">{dlr(sp['price'])}</span>
            <span style="color:{clr(sp['change'])};font-weight:700;font-size:15px;margin-left:8px;">{pct(sp['change'])}</span>
          </div>
          <span style="color:{mood_c};font-weight:700;font-size:15px;">SPY {sp['spy_mood']}</span>
          <span style="font-size:13px;font-weight:700;color:{live_col};">{dot}{live_label}</span>
          <span style="font-size:11px;color:{DIM};margin-left:8px;">Updated {dt.datetime.now(NY).strftime("%I:%M:%S %p ET")}</span>
        </div>
      </div>
    </div>""",
        unsafe_allow_html=True,
    )


@st.fragment(run_every=15)
def _render_ticker_tape() -> None:
    """Scrolling quotes; refreshes every 15s without re-running the page."""
    holdings = st.session_state.get("_live_holdings") or st.session_state.get("holdings", [])
    if not holdings:
        return
    tape_list = (
        tuple(h["ticker"] for h in holdings)
        + ("SPY", "QQQ", "NVDA", "AAPL", "TSLA")
        + ("BTC-USD", "ETH-USD", "SOL-USD")
    )
    px = get_live_prices(tape_list)

    def item(tk: str) -> str:
        d = px.get(tk, {})
        p, c = d.get("price", 0), d.get("change_pct", 0)
        col = GREEN if c >= 0 else RED
        arr = "▲" if c >= 0 else "▼"
        return (
            f'<span style="margin:0 28px;white-space:nowrap;">'
            f'<span style="color:{WHITE};font-weight:700;">{escape(tk)}</span>'
            f'&nbsp;<span style="color:#94A3B8;">${p:,.2f}</span>'
            f'&nbsp;<span style="color:{col};font-weight:700;">{arr}{abs(c):.2f}%</span></span>'
        )

    tape = "".join(item(tk) for tk in tape_list) * 3
    st.markdown(
        f"""
    <div style="overflow:hidden;background:{BG};border-top:1px solid {BORDER};
                border-bottom:1px solid {BORDER};padding:9px 0;margin-bottom:4px;">
      <div style="display:inline-block;animation:ticker-scroll 40s linear infinite;
                  white-space:nowrap;font-family:'Courier New',monospace;font-size:13px;">
        {tape}
      </div>
    </div>
    <div style="font-size:11px;color:{DIM};text-align:right;padding-right:8px;margin-bottom:14px;">
      Updated {dt.datetime.now(NY).strftime("%I:%M:%S %p ET")} · 15-min delayed
    </div>""",
        unsafe_allow_html=True,
    )


@st.fragment(run_every=20)
def _render_kpi_row() -> None:
    """Portfolio KPIs; refreshes prices every 20s and stores them for the other tabs."""
    holdings = st.session_state.get("holdings", [])
    if not holdings:
        return
    live = apply_live_prices(holdings, get_live_prices(tuple(h["ticker"] for h in holdings)))
    st.session_state._live_holdings = live
    tv = sum(h["market_value"] for h in live)
    tc = sum(h["total_cost"] for h in live)
    tp = tv - tc
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Portfolio Value", dlr(tv))
    k2.metric("Total Cost", dlr(tc))
    k3.metric("Open P&L", dlr(tp), delta=pct(tp / tc * 100 if tc else 0))
    k4.metric("Today's P&L", dlr(sum(h["day_pnl"] for h in live)))


_CHART_CONFIG = {
    "displayModeBar": True,
    "modeBarButtonsToRemove": ["autoScale2d", "lasso2d", "select2d"],
    "displaylogo": False,
}


def _holding_card(h: dict) -> str:
    oc, dc = clr(h["open_pnl"]), clr(h["day_pnl"])
    pe_s = f'{h["pe"]:.1f}' if h["pe"] else "N/A"
    t, tl, e, a = h["tech"], h["timeline"], h["earn"], h["analyst"]
    rsi_s = f'{t["rsi"]:.0f} ({t["rsi_label"]})' if t.get("rsi") else "N/A"
    info_parts = []
    if e.get("days_to_earnings") is not None:
        info_parts.append(
            f'Earnings in {e["days_to_earnings"]}d'
            + (f' ({e["next_earnings"].strftime("%b %d")})' if e.get("next_earnings") else "")
        )
    info_parts.append(f'Analyst: {a["rec_buy"]} Buy / {a["rec_hold"]} Hold / {a["rec_sell"]} Sell')
    if a.get("target_mean"):
        info_parts.append(f'Target: ${a["target_low"]:.0f} / ${a["target_mean"]:.0f} / ${a["target_high"]:.0f}')
    info_parts.append(f'Insider (30d): {a["insider_buys"]} buys / {a["insider_sells"]} sells')
    return f"""
    <div class="stock-card">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <div style="display:flex;align-items:baseline;gap:10px;">
          <span class="card-ticker">{escape(h["ticker"])}</span>
          <span class="card-name">{escape(h["name"])}</span>
        </div>
        <div style="display:flex;align-items:center;gap:12px;">
          <span style="font-size:22px;font-weight:800;color:{WHITE};">{dlr(h["current_price"])}</span>
          <span style="font-size:16px;font-weight:700;color:{clr(h['day_pnl_pct'])}">{pct(h['day_pnl_pct'])}</span>
          {sig_badge(h["signal"])}
        </div>
      </div>
      <div class="card-reason">{escape(h["reason"])}</div>
      <div class="card-action">Action: {escape(h["action"])}</div>
      <div style="font-size:13px;color:{DIM};font-style:italic;margin-top:4px;">{escape(h.get("strategy_note", ""))}</div>
      <div style="display:flex;gap:20px;margin-top:14px;flex-wrap:wrap;">
        <div><div class="kpi-label">Avg Cost</div><div class="kpi-value" style="color:{TEXT};">{dlr(h["avg_cost"])}</div></div>
        <div><div class="kpi-label">Shares</div><div class="kpi-value" style="color:{WHITE};">{int(h["shares"])}</div></div>
        <div><div class="kpi-label">PE</div><div class="kpi-value" style="color:{AMBER};">{pe_s}</div></div>
        <div><div class="kpi-label">RSI</div><div class="kpi-value" style="color:{WHITE};">{rsi_s}</div></div>
        <div><div class="kpi-label">Open P&L</div><div class="kpi-value" style="color:{oc};">{"+" if h["open_pnl"] >= 0 else ""}{dlr(h["open_pnl"])} <span style="font-size:13px;">({pct(h["open_pnl_pct"])})</span></div></div>
        <div><div class="kpi-label">Day P&L</div><div class="kpi-value" style="color:{dc};">{"+" if h["day_pnl"] >= 0 else ""}{dlr(h["day_pnl"])} <span style="font-size:13px;">({pct(h["day_pnl_pct"])})</span></div></div>
      </div>
      <div class="card-info">{"<br>".join(info_parts)}</div>
      <div class="card-timeline">
        <div class="timeline-label">Short-term (0-30d):</div><div>{tl["short_level"]}<br>{tl["short_trigger"]}</div>
        <div class="timeline-label">Medium-term (1-6mo):</div><div>{tl["med_catalyst"]}<br>{tl["med_target"]}</div>
        <div class="timeline-label">Long-term (6-24mo):</div><div>{tl["long_thesis"]}<br>Invalidate: {tl["long_invalidate"]}</div>
      </div>
    </div>"""


def _render_portfolio_tab(holdings: list[dict]) -> None:
    pnl_fig = build_pnl_bar(holdings)
    if pnl_fig:
        st.plotly_chart(pnl_fig, use_container_width=True, config={"displayModeBar": False}, key="pnl_bar")
    for h in holdings:
        st.markdown(_holding_card(h), unsafe_allow_html=True)
        chart = sparkline_chart(h["ticker"])
        if chart:
            st.plotly_chart(
                chart, use_container_width=True, config={"displayModeBar": False}, key=f"spark_{h['ticker']}"
            )
        st.plotly_chart(
            build_price_chart(h["ticker"], h["avg_cost"]),
            use_container_width=True,
            config=_CHART_CONFIG,
            key=f"price_chart_{h['ticker']}",
        )


def _render_picks_tab(picks_m: list[dict], picks_s: list[dict]) -> None:
    st.markdown(
        f'<div style="font-size:16px;font-weight:700;color:{WHITE};margin-bottom:10px;">Momentum Longs (1-3 Day)</div>',
        unsafe_allow_html=True,
    )
    for p in picks_m:
        st.markdown(pick_card(p), unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-size:16px;font-weight:700;color:{WHITE};margin:24px 0 10px;">Swing Trades (2-4 Week)</div>',
        unsafe_allow_html=True,
    )
    for p in picks_s:
        st.markdown(pick_card(p), unsafe_allow_html=True)


def _render_technicals_tab(holdings: list[dict]) -> None:
    tickers = list({h["ticker"]: h for h in holdings})
    if len(tickers) > 1:
        sel = st.selectbox("Select ticker to chart", tickers, key="tech_ticker_sel")
    else:
        sel = tickers[0] if tickers else None
    if sel:
        held = next((h for h in holdings if h["ticker"] == sel), None)
        st.plotly_chart(
            build_price_chart(sel, held["avg_cost"] if held else 0),
            use_container_width=True,
            config=_CHART_CONFIG,
            key=f"tech_chart_{sel}",
        )

    seen: set[str] = set()
    rows = []
    for h in holdings:
        tk, t = h["ticker"], h["tech"]
        if tk in seen:
            continue
        seen.add(tk)
        rows.append(
            {
                "Ticker": tk,
                "Price": f"${h['current_price']:,.2f}",
                "RSI": f'{t["rsi"]:.0f}' if t.get("rsi") is not None else "N/A",
                "RSI Signal": t.get("rsi_label", "N/A"),
                "MACD": t.get("macd_label", "N/A"),
                "Bollinger": t.get("bb_label", "N/A"),
                "EMA": t.get("ema_label", "N/A"),
                "Volume": t.get("vol_label", "N/A"),
                "ATR Stop": f'${t["atr_stop"]:,.2f}' if t.get("atr_stop") else "N/A",
                "ATR Target": f'${t["atr_target"]:,.2f}' if t.get("atr_target") else "N/A",
            }
        )
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_risk_tab(holdings: list[dict], risk_d: dict, macro: dict) -> None:
    r1, r2, r3 = st.columns(3)
    r1.metric("Weighted Beta", f'{risk_d["weighted_beta"]:.2f}')
    r2.metric("Risk Rating", risk_d["risk_rating"])
    r3.metric("1-Day 95% VaR", dlr(risk_d["var_95"]))

    c1, c2 = st.columns([1, 1])
    with c1:
        alloc = build_allocation_bar(holdings)
        if alloc:
            st.plotly_chart(alloc, use_container_width=True, config={"displayModeBar": False}, key="alloc_bar")
    with c2:
        donut = build_sector_donut(risk_d)
        if donut:
            st.plotly_chart(donut, use_container_width=True, config={"displayModeBar": False}, key="sector_donut")

    if risk_d["positions"]:
        pdf = pd.DataFrame(risk_d["positions"]).rename(
            columns={"ticker": "Ticker", "weight": "Weight %", "beta": "Beta", "risk_1d": "1-Day Risk $"}
        )
        pdf["1-Day Risk $"] = pdf["1-Day Risk $"].map(lambda x: f"${x:,.2f}")
        st.dataframe(pdf, use_container_width=True, hide_index=True)
    if risk_d["sectors"]:
        sdf = pd.DataFrame(
            [
                {"Sector": k, "Exposure %": round(v, 1)}
                for k, v in sorted(risk_d["sectors"].items(), key=lambda x: -x[1])
            ]
        )
        st.dataframe(sdf, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(
        f'<div style="font-size:16px;font-weight:700;color:{WHITE};margin-bottom:10px;">Macro & Political Risk</div>',
        unsafe_allow_html=True,
    )
    for h in macro["headlines"][:6]:
        pub = f' -- {escape(h["publisher"])}' if h["publisher"] else ""
        st.markdown(
            f'<div class="news-item">{safe_link(h["title"], h["link"])}'
            f'<span style="color:{DIM};font-size:13px;">{pub}</span></div>',
            unsafe_allow_html=True,
        )
    if macro["risks"]:
        rdf = pd.DataFrame(macro["risks"])
        rdf.columns = [c.title() for c in rdf.columns]
        st.dataframe(rdf, use_container_width=True, hide_index=True)


COINS = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL", "binancecoin": "BNB", "ripple": "XRP"}


def _render_crypto_tab() -> None:
    fg = get_fear_greed()
    fg_val, fg_lbl = fg.get("value", 50), fg.get("label", "Neutral")
    fg_col = GREEN if fg_val > 60 else RED if fg_val < 40 else AMBER
    st.metric("Fear & Greed Index", f"{fg_val} — {fg_lbl}", delta=None)
    st.markdown(
        f'<div style="font-size:12px;color:{DIM};margin-bottom:16px;">'
        f'<span style="color:{fg_col};font-weight:700;">{fg_val}/100</span> — '
        f'Green = Greed, Red = Fear, Amber = Neutral</div>',
        unsafe_allow_html=True,
    )

    crypto = get_crypto_prices()
    for cid, sym in COINS.items():
        d = crypto.get(cid, {})
        price = d.get("usd", 0) or 0
        chg = d.get("usd_24h_change") or 0
        mcap = d.get("usd_market_cap") or 0
        mcap_s = f"${mcap / 1e9:.1f}B" if mcap >= 1e9 else f"${mcap / 1e6:.0f}M"
        st.markdown(
            f"""
        <div class="stock-card">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:18px;font-weight:800;color:{WHITE};">{sym}</span>
            <span style="font-size:16px;font-weight:700;color:{WHITE};">${price:,.2f}</span>
            <span style="color:{GREEN if chg >= 0 else RED};font-weight:700;">{chg:+.2f}%</span>
            <span style="font-size:12px;color:{DIM};">MCap: {mcap_s}</span>
          </div>
        </div>""",
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div style="font-size:14px;font-weight:700;color:{WHITE};margin:20px 0 10px;">Technicals (yfinance)</div>',
        unsafe_allow_html=True,
    )
    rows = []
    for sym in COINS.values():
        tech = compute_technicals(f"{sym}-USD")
        rows.append(
            {
                "Coin": sym,
                "RSI": f'{tech["rsi"]:.0f}' if tech.get("rsi") is not None else "N/A",
                "RSI Signal": tech.get("rsi_label", "N/A"),
                "MACD": tech.get("macd_label", "N/A"),
                "EMA": tech.get("ema_label", "N/A"),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.markdown(
        f'<div style="font-size:11px;color:{DIM};margin-top:16px;font-style:italic;">'
        f'Crypto trades 24/7. Technical indicators apply standard stock logic.</div>',
        unsafe_allow_html=True,
    )


def _render_dashboard(settings: Settings, owner_portfolio: list[dict]) -> None:
    ss = st.session_state
    if "holdings" not in ss:
        _run_analysis(settings, owner_portfolio)

    _render_header(ss.sp)
    _render_ticker_tape()

    if ss.get("email_sent") is True:
        st.success(f"Report sent to {ss.user_email}!")
    elif ss.user_email and ss.get("email_sent") is False:
        detail = f" ({ss.email_error})" if ss.get("email_error") else ""
        st.warning(f"Could not send email{detail} -- but your dashboard is ready below.")

    _render_kpi_row()
    display = ss.get("_live_holdings") or ss.holdings

    tab_port, tab_picks, tab_tech, tab_risk, tab_crypto = st.tabs(
        ["Portfolio", "Trade Ideas", "Technicals", "Risk & News", "Crypto"]
    )
    with tab_port:
        _render_portfolio_tab(display)
    with tab_picks:
        _render_picks_tab(ss.picks_m, ss.picks_s)
    with tab_tech:
        _render_technicals_tab(display)
    with tab_risk:
        _render_risk_tab(display, ss.risk_d, ss.macro)
    with tab_crypto:
        _render_crypto_tab()


def main() -> None:
    settings = _bridge_streamlit_secrets()
    st.set_page_config(page_title="Stock Analyst", page_icon=None, layout="wide", initial_sidebar_state="expanded")
    st.markdown(STARFIELD_CSS, unsafe_allow_html=True)
    _password_gate(settings)
    st.markdown(layout_css(), unsafe_allow_html=True)

    owner_portfolio = load_portfolio(settings.portfolio_path)
    _init_session(settings, owner_portfolio)
    _render_sidebar(settings, owner_portfolio)
    if st.session_state.portfolio_submitted:
        _render_dashboard(settings, owner_portfolio)
    else:
        _render_input_form()
