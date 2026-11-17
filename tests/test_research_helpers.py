"""Pure helpers in the research and dashboard layers (headline dedupe, risk flags, portfolio math, input validation)."""

import datetime as dt
import json

import pytest

from quant_research.dashboard.components import NY, apply_live_prices, is_market_open, is_valid_email, safe_link
from quant_research.research.market import parse_sp500_table, spy_mood
from quant_research.research.news import HeadlineSet, flag_macro_risks
from quant_research.research.portfolio import position_metrics
from quant_research.watchlist import MACRO_KEYWORDS, load_portfolio


def test_headline_set_drops_near_duplicates():
    hs = HeadlineSet()
    hs.add("Nvidia beats estimates as data center sales surge", "https://a")
    hs.add("Nvidia beats estimates as data-center sales surge!", "https://b")
    hs.add("Fed holds rates steady", "https://c")
    hs.add("")
    assert [i["link"] for i in hs.items] == ["https://a", "https://c"]


def test_flag_macro_risks():
    flags = flag_macro_risks(["New tariff threat on Korea", "Fed signals patience"], ["VOO", "EWY"], MACRO_KEYWORDS)
    by_ticker = {f["ticker"]: f for f in flags}
    assert by_ticker["EWY"]["level"] == "HIGH" and by_ticker["EWY"]["keyword"] == "tariff"
    assert by_ticker["VOO"]["level"] == "MEDIUM"


def test_flag_macro_wildcard_applies_to_portfolio():
    flags = flag_macro_risks(["Recession fears grow"], ["AAA", "BBB"], MACRO_KEYWORDS)
    assert {f["ticker"] for f in flags} == {"AAA", "BBB"}


def test_position_metrics():
    m = position_metrics(shares=10, avg=100, cur=110, prev=105, hi52=120, lo52=80)
    assert m["total_cost"] == 1000 and m["market_value"] == 1100
    assert m["open_pnl"] == 100 and m["open_pnl_pct"] == pytest.approx(10.0)
    assert m["day_pnl"] == 50 and m["day_pnl_pct"] == pytest.approx(4.7619, rel=1e-3)
    assert m["range_pct"] == pytest.approx(75.0)
    assert position_metrics(1, 0, 10, 0, None, None)["open_pnl_pct"] == 0


def test_load_portfolio(tmp_path):
    p = tmp_path / "portfolio.json"
    p.write_text(json.dumps({"portfolio": [{"ticker": "VOO", "shares": 6, "avgPrice": 631.55}, {"ticker": "BAD"}]}))
    assert load_portfolio(p) == [{"ticker": "VOO", "shares": 6, "avg_cost": 631.55}]
    assert load_portfolio(tmp_path / "missing.json") == []


def test_parse_sp500_table():
    html = (
        "<table><tr><th>Symbol</th><th>Security</th></tr>"
        "<tr><td>AAPL</td><td>Apple</td></tr><tr><td>BRK.B</td><td>Berkshire</td></tr></table>"
    )
    assert parse_sp500_table(html) == ["AAPL", "BRK-B"]


@pytest.mark.parametrize("rsi,mood", [(65, "Bullish"), (35, "Bearish"), (50, "Neutral"), (None, "Neutral")])
def test_spy_mood(rsi, mood):
    assert spy_mood(rsi) == mood


@pytest.mark.parametrize(
    "address,ok",
    [
        ("me@example.com", True),
        ("first.last+tag@mail.example.co", True),
        ("no-at-sign", False),
        ("a@b", False),
        ("victim@example.com\nBcc: everyone@example.com", False),  # header injection
        ("a@example.com, b@example.com", False),
        ("Name <a@example.com>", False),
        ("", False),
    ],
)
def test_email_validation(address, ok):
    assert is_valid_email(address) is ok


def test_safe_link():
    assert safe_link("<b>x</b>", "javascript:alert(1)") == "&lt;b&gt;x&lt;/b&gt;"
    assert 'href="https://ok.example/?a=1&amp;b=2"' in safe_link("t", "https://ok.example/?a=1&b=2")


def test_market_hours():
    assert is_market_open(NY.localize(dt.datetime(2026, 11, 13, 10, 0)))  # Friday
    assert not is_market_open(NY.localize(dt.datetime(2026, 11, 13, 9, 0)))  # pre-market
    assert not is_market_open(NY.localize(dt.datetime(2026, 11, 14, 12, 0)))  # Saturday


def test_apply_live_prices_returns_updated_copies():
    holdings = [{"ticker": "A", "shares": 10, "avg_cost": 100.0, "total_cost": 1000.0, "current_price": 100.0}]
    out = apply_live_prices(holdings, {"A": {"price": 110.0, "change": 2.0, "change_pct": 1.85}})
    assert out[0]["market_value"] == 1100.0 and out[0]["open_pnl"] == 100.0 and out[0]["day_pnl"] == 20.0
    assert holdings[0]["current_price"] == 100.0  # input untouched
    assert apply_live_prices(holdings, {"A": {"price": 0}})[0]["current_price"] == 100.0
