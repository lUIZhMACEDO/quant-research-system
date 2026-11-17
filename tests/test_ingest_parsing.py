"""Ingest parsing: FRED CSV, yfinance OHLCV shapes and fundamentals mapping. No network."""

import numpy as np
import pandas as pd
import pytest

from quant_research.ingest import fred
from quant_research.ingest.fred import derive_macro_spreads, fetch_all_macro, parse_fred_csv
from quant_research.ingest.fundamentals import parse_fundamentals, safe_fcf_yield
from quant_research.ingest.prices import normalize_ohlcv
from quant_research.ingest.universe import FRED_SERIES, ingest_universe

# ---------------------------------------------------------------- FRED


def test_parse_fred_skips_missing_dot_and_returns_latest(fixtures_dir):
    text = (fixtures_dir / "fred_dgs10.csv").read_text()
    assert parse_fred_csv(text) == pytest.approx(4.19)


def test_parse_fred_handles_legacy_date_header(fixtures_dir):
    text = (fixtures_dir / "fred_unrate_legacy_header.csv").read_text()
    assert parse_fred_csv(text) == pytest.approx(4.3)


def test_parse_fred_all_missing_returns_none(fixtures_dir):
    assert parse_fred_csv((fixtures_dir / "fred_all_missing.csv").read_text()) is None


@pytest.mark.parametrize("text", ["", "   ", "observation_date\n2026-01-01\n"])
def test_parse_fred_degenerate_payloads(text):
    assert parse_fred_csv(text) is None


def test_fetch_fred_series_returns_none_on_http_error():
    class BoomSession:
        def get(self, *args, **kwargs):
            raise ConnectionError("offline")

    assert fred.fetch_fred_series("DGS10", session=BoomSession()) is None


def test_fetch_fred_series_parses_response(fixtures_dir):
    payload = (fixtures_dir / "fred_dgs10.csv").read_text()

    class Resp:
        text = payload

        def raise_for_status(self):
            return None

    class Session:
        def __init__(self):
            self.params = None

        def get(self, url, params=None, timeout=None):
            self.params = params
            return Resp()

    session = Session()
    assert fred.fetch_fred_series("DGS10", session=session) == pytest.approx(4.19)
    assert session.params["id"] == "DGS10"


def test_derive_macro_spreads_only_when_both_legs_exist():
    out = derive_macro_spreads(
        {"treasury_10y": 4.2, "treasury_3m": 4.5, "treasury_2y": None, "hy_spread": 3.1, "ig_spread": 0.9}
    )
    assert out == {"curve_slope_10y_3m": pytest.approx(-0.3), "hy_ig_differential": pytest.approx(2.2)}


def test_derive_macro_spreads_keeps_zero_values():
    # A 0.0 yield is a real value, not "missing".
    out = derive_macro_spreads({"treasury_10y": 0.0, "treasury_2y": 0.0})
    assert out == {"curve_slope_10y_2y": 0.0}


def test_fetch_all_macro_uses_injected_fetcher():
    values = {"DGS10": 4.0, "DGS3MO": 4.5, "DGS2": 3.9}
    out = fetch_all_macro(fetch=lambda sid: values.get(sid), delay=0)
    assert set(FRED_SERIES.values()) <= set(out)
    assert out["treasury_10y"] == 4.0
    assert out["curve_slope_10y_3m"] == pytest.approx(-0.5)
    assert out["vix"] is None


# ---------------------------------------------------------------- OHLCV


def _raw_yf(n=25, multi=False, ticker="SPY"):
    idx = pd.bdate_range("2026-01-02", periods=n)
    data = {
        "Open": np.arange(n) + 100.0,
        "High": np.arange(n) + 101.0,
        "Low": np.arange(n) + 99.0,
        "Close": np.arange(n) + 100.5,
        "Volume": np.full(n, 1e6),
    }
    df = pd.DataFrame(data, index=idx)
    if multi:
        df.columns = pd.MultiIndex.from_product([df.columns, [ticker]], names=["Price", "Ticker"])
    return df


def test_normalize_flat_columns():
    out = normalize_ohlcv(_raw_yf(), "SPY")
    assert list(out.columns) == ["ticker", "open", "high", "low", "close", "volume"]
    assert out.index.name == "date"
    assert (out["ticker"] == "SPY").all()


def test_normalize_multiindex_columns_from_new_yfinance():
    out = normalize_ohlcv(_raw_yf(multi=True), "SPY")
    assert out is not None
    assert out["close"].iloc[-1] == pytest.approx(124.5)


def test_normalize_multiindex_with_ticker_level_first():
    raw = _raw_yf(multi=True).swaplevel(axis=1)
    out = normalize_ohlcv(raw, "SPY")
    assert out is not None and "close" in out.columns


@pytest.mark.parametrize("raw", [None, pd.DataFrame()])
def test_normalize_empty_returns_none(raw):
    assert normalize_ohlcv(raw, "SPY") is None


def test_normalize_too_short_returns_none():
    assert normalize_ohlcv(_raw_yf(n=10), "SPY") is None


def test_normalize_missing_column_returns_none():
    assert normalize_ohlcv(_raw_yf().drop(columns=["Volume"]), "SPY") is None


def test_normalize_drops_rows_without_close():
    raw = _raw_yf(n=25)
    raw.iloc[3, raw.columns.get_loc("Close")] = np.nan
    assert len(normalize_ohlcv(raw, "SPY")) == 24


# ---------------------------------------------------------------- fundamentals


def test_parse_fundamentals_maps_info_keys():
    info = {
        "trailingPE": 25.1,
        "forwardPE": 21.0,
        "enterpriseToEbitda": 15.2,
        "freeCashflow": 5_000_000_000,
        "marketCap": 100_000_000_000,
        "recommendationMean": 1.9,
    }
    row = parse_fundamentals("MSFT", info, date="2026-11-13")
    assert row["ticker"] == "MSFT" and row["date"] == "2026-11-13"
    assert row["pe_ttm"] == 25.1 and row["pe_forward"] == 21.0
    assert row["ev_ebitda"] == 15.2
    assert row["analyst_rating"] == 1.9
    assert row["fcf_yield"] == pytest.approx(0.05)
    assert row["roe"] is None  # absent keys become NULLs, not KeyErrors


def test_parse_fundamentals_tolerates_none_info():
    row = parse_fundamentals("XYZ", None, date="2026-11-13")
    assert row["pe_ttm"] is None and row["fcf_yield"] is None


@pytest.mark.parametrize(
    "info,expected",
    [
        ({"freeCashflow": 10, "marketCap": 1000}, 0.01),
        ({"freeCashflow": -10, "marketCap": 1000}, -0.01),
        ({"freeCashflow": 10, "marketCap": 0}, None),
        ({"freeCashflow": None, "marketCap": 1000}, None),
        ({"freeCashflow": "bad", "marketCap": 1000}, None),
    ],
)
def test_safe_fcf_yield(info, expected):
    assert safe_fcf_yield(info) == expected


def test_ingest_universe_is_sorted_and_deduplicated():
    tickers = ingest_universe(["SPY", "ZZZZ"])
    assert tickers == sorted(set(tickers))
    assert "ZZZZ" in tickers and tickers.count("SPY") == 1
