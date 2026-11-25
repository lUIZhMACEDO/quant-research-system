"""Shared fixtures. Nothing here touches the network: price paths are synthetic or read from tests/fixtures."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Fail loudly if any test tries to reach a non-loopback host.

    Loopback stays allowed because asyncio (used by Streamlit's AppTest) builds its
    self-pipe from a 127.0.0.1 socket pair on Windows.
    """
    import socket

    real_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise RuntimeError(f"Network access is not allowed in unit tests (tried {host})")
        return real_connect(self, address)

    def no_create_connection(address, *args, **kwargs):
        raise RuntimeError(f"Network access is not allowed in unit tests (tried {address[0]})")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "create_connection", no_create_connection)


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


def make_ohlcv(
    close: np.ndarray, start: str = "2025-01-02", volume: float = 1_000_000, capitalised: bool = False
) -> pd.DataFrame:
    """OHLCV frame around a close path. ``capitalised`` gives yfinance-style column names."""
    close = np.asarray(close, dtype=float)
    idx = pd.bdate_range(start, periods=len(close), name="date")
    df = pd.DataFrame(
        {
            "open": close * 0.998,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.full(len(close), volume),
        },
        index=idx,
    )
    if capitalised:
        df.columns = [c.capitalize() for c in df.columns]
    return df


@pytest.fixture
def rising_close() -> np.ndarray:
    """Steady uptrend with small noise (300 bars)."""
    rng = np.random.default_rng(1)
    return np.linspace(100, 200, 300) + rng.normal(0, 0.3, 300)


@pytest.fixture
def falling_close() -> np.ndarray:
    rng = np.random.default_rng(2)
    return np.linspace(200, 100, 300) + rng.normal(0, 0.3, 300)


@pytest.fixture
def spy_fixture(fixtures_dir) -> pd.DataFrame:
    df = pd.read_csv(fixtures_dir / "ohlcv_spy_30d.csv", parse_dates=["Date"], index_col="Date")
    return df
