"""Report builders, alerts and SMTP delivery (with a fake SMTP server)."""

import datetime as dt

import pandas as pd
import pytest

from quant_research.config import load_settings
from quant_research.reporting import emailer
from quant_research.reporting.alerts import alert_email, check_alerts, load_scores, save_scores
from quant_research.reporting.html import build_html, build_plain, html_macro, html_weekly_recap
from quant_research.reporting.user_report import build_user_report
from quant_research.watchlist import ALERT_RULES

SP = {"price": 6000.0, "change": 0.5, "spy_rsi": 55.0, "spy_mood": "Neutral"}
TECH = {
    "rsi": 50.0,
    "rsi_label": "NEUTRAL",
    "macd_label": "NEUTRAL",
    "bb_label": "MID RANGE",
    "ema_label": "GOLDEN CROSS",
    "vol_label": "NORMAL",
    "atr_stop": 95.0,
    "atr_target": 110.0,
}
TIMELINE = {
    "short_level": "s",
    "short_trigger": "t",
    "med_catalyst": "m",
    "med_target": "mt",
    "long_thesis": "l",
    "long_invalidate": "li",
}
EVIL = '<script>alert(1)</script>'


def _holding(**over):
    h = {
        "ticker": "AAPL",
        "name": "Apple & Co",
        "shares": 10,
        "avg_cost": 100.0,
        "current_price": 110.0,
        "total_cost": 1000.0,
        "market_value": 1100.0,
        "open_pnl": 100.0,
        "open_pnl_pct": 10.0,
        "day_pnl": 5.0,
        "day_pnl_pct": 0.5,
        "pe": 30.0,
        "signal": "HOLD",
        "reason": "No strong signals.",
        "action": "Thesis intact.",
        "score": 0.0,
        "score_breakdown": {"rsi": 0.0},
        "tech": TECH,
        "earn": {"days_to_earnings": None},
        "analyst": {
            "rec_buy": 5,
            "rec_hold": 2,
            "rec_sell": 1,
            "target_mean": None,
            "insider_buys": 0,
            "insider_sells": 0,
        },
        "news": {
            "headlines": [{"title": EVIL, "link": "javascript:alert(1)", "publisher": ""}],
            "sentiment_score": 0.0,
        },
        "timeline": TIMELINE,
        "relative_strength": {"relative_strength": 1.2, "outperforming": True},
    }
    h.update(over)
    return h


RISK = {
    "weighted_beta": 1.1,
    "risk_rating": "MEDIUM",
    "var_95": 25.0,
    "sectors": {"Technology": 100.0},
    "positions": [{"ticker": "AAPL", "weight": 100.0, "beta": 1.1, "risk_1d": 24.2}],
}
MOVERS = pd.DataFrame([{"Ticker": "XYZ", "Previous Close": 10.0, "Current Price": 11.0, "Change %": 10.0}])


def test_build_html_escapes_third_party_text():
    macro = {
        "headlines": [{"title": EVIL, "link": "https://example.com/a?b=1&c=2", "publisher": "<b>x</b>"}],
        "risks": [],
    }
    html = build_html(SP, macro, [], [_holding()], [], [], MOVERS, MOVERS, RISK, now=dt.datetime(2026, 11, 13, 7, 30))
    assert EVIL not in html
    assert "&lt;script&gt;" in html
    assert "javascript:" not in html  # non-http links are dropped entirely
    assert 'href="https://example.com/a?b=1&amp;c=2"' in html
    assert "Apple &amp; Co" in html
    assert "Friday, November 13, 2026" in html


def test_weekly_recap_only_when_given():
    html = build_html(
        SP,
        {"headlines": [], "risks": []},
        [],
        [_holding()],
        [],
        [],
        MOVERS,
        MOVERS,
        RISK,
        weekly_recap=(1.0, [("AAPL", 2.5), ("MSFT", -1.0)]),
    )
    assert "Weekly Recap" in html and "AAPL (+2.50%)" in html and "MSFT (-1.00%)" in html
    assert html_weekly_recap(1.0, []) == ""
    plain = build_html(SP, {"headlines": [], "risks": []}, [], [_holding()], [], [], MOVERS, MOVERS, RISK)
    assert "Weekly Recap" not in plain


def test_macro_section_lists_risk_flags():
    html = html_macro(
        {"headlines": [], "risks": [{"ticker": "EWY", "level": "HIGH", "reason": "Trade", "keyword": "tariff"}]}
    )
    assert "Portfolio Risk Flags" in html and "keyword: tariff" in html


def test_build_plain():
    pick = {"ticker": "NVDA", "current_price": 100.0, "entry": 99.2, "target": 106.0, "stop": 96.2, "status": "ACTIVE"}
    text = build_plain(SP, [_holding()], [pick], [], today=dt.date(2026, 11, 13))
    assert text.startswith("Stock Analyst -- 2026-11-13")
    assert "AAPL" in text and "NVDA" in text and "Not financial advice." in text


def test_user_report_escapes_user_input():
    html, text = build_user_report(
        [_holding(ticker="<img src=x>", name=EVIL)], RISK, SP, now=dt.datetime(2026, 11, 13, 9, 0)
    )
    assert "<img src=x>" not in html and EVIL not in html
    assert "&lt;img src=x&gt;" in html
    assert "Risk: Beta 1.10" in text


# ---------------------------------------------------------------- alerts


def test_check_alerts_rules():
    now = dt.datetime(2026, 11, 13, 9, 45)
    results = [
        {"ticker": "VOO", "day_pnl_pct": -2.1, "score": 1.0, "signal": "HOLD", "earn": {"days_to_earnings": 10}},
        {"ticker": "AAPL", "day_pnl_pct": 0.5, "score": 5.0, "signal": "BUY", "earn": {"days_to_earnings": 1}},
        {"ticker": "MSFT", "day_pnl_pct": 0.1, "score": 0.0, "signal": "HOLD", "earn": {}},
    ]
    alerts = check_alerts(results, {"AAPL": 1.0, "MSFT": 0.5}, ALERT_RULES, now=now)
    by_type = {(a["ticker"], a["type"]) for a in alerts}
    assert by_type == {("VOO", "PRICE_MOVE"), ("AAPL", "SIGNAL_CHANGE"), ("AAPL", "EARNINGS")}
    voo = next(a for a in alerts if a["ticker"] == "VOO")
    assert voo["message"] == "VOO is DOWN 2.1% today" and voo["time"] == "09:45 AM"


def test_first_run_has_no_score_change_alert():
    alerts = check_alerts([{"ticker": "AAPL", "day_pnl_pct": 0, "score": 9.0, "earn": {}}], {}, ALERT_RULES)
    assert alerts == []


def test_alert_email_and_score_cache(tmp_path):
    subject, body = alert_email([{"ticker": "B", "message": "b"}, {"ticker": "A", "message": "a"}])
    assert subject == "Stock Alert - A, B" and body == "- b\n- a"
    path = tmp_path / "scores.json"
    assert load_scores(path) == {}
    save_scores(path, [{"ticker": "A", "score": 2.5}])
    assert load_scores(path) == {"A": 2.5}
    path.write_text("not json")
    assert load_scores(path) == {}


# ---------------------------------------------------------------- email


class FakeSMTP:
    sent: list = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ehlo(self):
        pass

    def starttls(self):
        pass

    def login(self, user, password):
        self.user = user

    def sendmail(self, sender, recipients, raw):
        FakeSMTP.sent.append((sender, recipients, raw))


def test_send_email_requires_credentials():
    with pytest.raises(emailer.EmailNotConfigured):
        emailer.send_email(load_settings({}), "s", "body")


def test_send_email_uses_settings(monkeypatch):
    FakeSMTP.sent = []
    monkeypatch.setattr(emailer.smtplib, "SMTP", FakeSMTP)
    settings = load_settings(
        {"SENDER_EMAIL": "bot@example.com", "EMAIL_PASSWORD": "pw", "RECIPIENT_EMAIL": "me@example.com"}
    )
    emailer.send_email(settings, "Stock Report", "plain", "<b>html</b>")
    sender, recipients, raw = FakeSMTP.sent[0]
    assert sender == "bot@example.com" and recipients == ["me@example.com"]
    assert "Subject: Stock Report" in raw and "text/html" in raw


def test_send_email_ssl_fallback(monkeypatch):
    class Broken(FakeSMTP):
        def starttls(self):
            raise OSError("starttls refused")

    FakeSMTP.sent = []
    monkeypatch.setattr(emailer.smtplib, "SMTP", Broken)
    monkeypatch.setattr(emailer.smtplib, "SMTP_SSL", FakeSMTP)
    settings = load_settings({"SENDER_EMAIL": "bot@example.com", "EMAIL_PASSWORD": "pw"})
    with pytest.raises(OSError):
        emailer.send_email(settings, "s", "b", recipient="u@example.com")
    emailer.send_email(settings, "s", "b", recipient="u@example.com", ssl_fallback=True)
    assert FakeSMTP.sent[-1][1] == ["u@example.com"]
