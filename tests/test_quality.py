import datetime as dt

import numpy as np
import pandas as pd

from conftest import make_ohlcv
from quant_research.ingest.quality import check_ohlcv


def _frame(n=30, end_offset_days=0):
    df = make_ohlcv(np.linspace(100, 110, n), start="2026-10-01")
    return df, df.index[-1].date() + dt.timedelta(days=end_offset_days)


def test_clean_series_has_no_issues():
    df, today = _frame()
    assert check_ohlcv(df, today) == []


def test_missing_data():
    assert check_ohlcv(None, dt.date(2026, 11, 13)) == ["no_ohlcv"]


def test_stale_after_three_days():
    df, today = _frame(end_offset_days=4)
    last = df.index[-1].date().isoformat()
    assert check_ohlcv(df, today) == [f"stale_{last}"]


def test_weekend_gap_is_not_stale():
    df, today = _frame(end_offset_days=3)
    assert check_ohlcv(df, today) == []


def test_duplicate_dates():
    df, today = _frame()
    df = pd.concat([df, df.iloc[[-1]]])
    assert "duplicate_dates" in check_ohlcv(df, today)


def test_nonpositive_close_and_inverted_bar():
    df, today = _frame()
    df.iloc[5, df.columns.get_loc("close")] = 0
    df.iloc[6, df.columns.get_loc("high")] = df.iloc[6]["low"] - 1
    issues = check_ohlcv(df, today)
    assert "nonpositive_close" in issues
    assert "high_below_low" in issues


def test_missing_values():
    df, today = _frame()
    df.iloc[2, df.columns.get_loc("open")] = np.nan
    assert check_ohlcv(df, today) == ["missing_values"]
