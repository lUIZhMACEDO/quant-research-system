"""Daily report job (``python main.py``): analyse, alert, build and email the report.

Scheduled Monday-Friday by ``.github/workflows/daily-report.yml``.
"""

from __future__ import annotations

import datetime as dt
import io
import logging
import subprocess
import sys

import requests

from quant_research.config import REPO_ROOT, Settings, get_settings
from quant_research.reporting.alerts import alert_email, check_alerts, load_scores, save_alerts, save_scores
from quant_research.reporting.emailer import send_email
from quant_research.reporting.html import build_html, build_plain
from quant_research.research.market import (
    analyse_stocks,
    fetch_market_summary,
    fetch_sp500_tickers,
    get_premarket_movers,
    get_top_movers,
)
from quant_research.research.market_data import get_hist
from quant_research.research.news import get_macro_news
from quant_research.research.portfolio import (
    analyse_portfolio,
    catalyst_universe,
    compute_risk_dashboard,
    enrich_picks,
)
from quant_research.research.ticker_data import get_weekly_catalysts
from quant_research.watchlist import (
    ALERT_RULES,
    MACRO_KEYWORDS,
    MOMENTUM_PICKS,
    SWING_PICKS,
    WATCHLIST,
    load_portfolio,
)

log = logging.getLogger(__name__)

TASK_NAME = "Stock_Analyst_Daily"
SCHEDULE_TIME = "07:30"


def setup_windows_scheduler() -> None:
    """Register a Mon-Fri Windows Task Scheduler job for local runs (no-op elsewhere)."""
    if sys.platform != "win32":
        return
    try:
        r = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME], capture_output=True, text=True)
        if r.returncode == 0:
            log.info("Task '%s' exists.", TASK_NAME)
            return
        script = REPO_ROOT / "main.py"
        cmd = [
            "schtasks",
            "/Create",
            "/TN",
            TASK_NAME,
            "/TR",
            f'"{sys.executable}" "{script}"',
            "/SC",
            "WEEKLY",
            "/D",
            "MON,TUE,WED,THU,FRI",
            "/ST",
            SCHEDULE_TIME,
            "/F",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            log.info("Task created. Mon-Fri at %s.", SCHEDULE_TIME)
        else:
            log.warning("Task creation failed: %s", r.stderr.strip())
    except FileNotFoundError:
        pass


def weekly_recap_data(holdings: list[dict]) -> tuple[float, list[tuple[str, float]]]:
    """SPY's and each holding's return over the last ~7 sessions."""
    spy_7d = 0.0
    spy_hist = get_hist("SPY", "10d", "1d")
    if not spy_hist.empty and len(spy_hist) >= 5:
        spy_7d = (spy_hist["Close"].iloc[-1] / spy_hist["Close"].iloc[0] - 1) * 100
    returns = []
    for h in holdings:
        hist = get_hist(h["ticker"], "10d", "1d")
        if hist.empty or len(hist) < 2:
            continue
        returns.append((h["ticker"], (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100))
    return spy_7d, returns


def _push_alerts(settings: Settings, alerts: list[dict]) -> None:
    if not settings.push_alert_url:
        return
    for alert in alerts:
        try:
            requests.post(
                settings.push_alert_url, json={"ticker": alert["ticker"], "message": alert["message"]}, timeout=3
            )
        except requests.RequestException:
            pass


def run_daily_report(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    portfolio = load_portfolio(settings.portfolio_path)

    log.info("[1/7] Market summary...")
    sp = fetch_market_summary()
    log.info(f"S&P 500: ${sp['price']:,.2f} ({sp['change']:+.2f}%)  SPY: {sp['spy_mood']}")

    log.info("[2/7] Pre-market movers...")
    premarket = get_premarket_movers(portfolio, WATCHLIST)
    log.info("%d pre-market movers >2%%", len(premarket))

    log.info("[3/7] Macro news & catalysts...")
    macro = get_macro_news([p["ticker"] for p in portfolio], MACRO_KEYWORDS)
    catalysts = get_weekly_catalysts(catalyst_universe(portfolio))
    log.info("%d headlines, %d risk flags, %d catalysts", len(macro["headlines"]), len(macro["risks"]), len(catalysts))

    log.info("[4/7] Portfolio analysis (composite scoring)...")
    holdings = analyse_portfolio(portfolio)
    risk_d = compute_risk_dashboard(holdings)
    log.info(f"Beta: {risk_d['weighted_beta']:.2f}  Risk: {risk_d['risk_rating']}  VaR: ${risk_d['var_95']:,.2f}")

    alerts = check_alerts(holdings, load_scores(settings.scores_cache_file), ALERT_RULES)
    save_scores(settings.scores_cache_file, holdings)
    save_alerts(settings.alerts_file, alerts)
    high = [a for a in alerts if a["severity"] == "HIGH"]
    if high:
        subject, body = alert_email(high)
        try:
            send_email(settings, subject, body)
            log.info("Alert email sent (%d alerts).", len(high))
        except Exception as exc:
            log.warning("Alert email failed: %s", exc)
        _push_alerts(settings, high)

    log.info("[5/7] Enriching smart picks...")
    picks_m = enrich_picks(MOMENTUM_PICKS)
    picks_s = enrich_picks(SWING_PICKS)

    log.info("[6/7] Scanning S&P 500...")
    df = analyse_stocks(fetch_sp500_tickers())
    if df.empty:
        log.error("No S&P 500 data; report not sent.")
        return
    gainers, losers = get_top_movers(df)

    log.info("[7/7] Building & sending report...")
    recap = weekly_recap_data(holdings) if dt.date.today().weekday() == 4 else None
    html = build_html(
        sp,
        macro,
        catalysts,
        holdings,
        picks_m,
        picks_s,
        gainers,
        losers,
        risk_d,
        premarket_movers=premarket,
        weekly_recap=recap,
    )
    text = build_plain(sp, holdings, picks_m, picks_s)
    send_email(settings, f"Stock Report -- {dt.date.today()}", text, html)
    log.info("Email sent. Done.")


def _utf8_stdio() -> None:
    """Windows consoles default to cp1252; keep log output from crashing on non-ASCII headlines."""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        if stream and getattr(stream, "encoding", "").lower() not in ("utf-8", "utf8") and hasattr(stream, "buffer"):
            setattr(sys, name, io.TextIOWrapper(stream.buffer, encoding="utf-8", errors="replace"))


def main() -> None:
    _utf8_stdio()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    setup_windows_scheduler()
    run_daily_report()


if __name__ == "__main__":
    main()
