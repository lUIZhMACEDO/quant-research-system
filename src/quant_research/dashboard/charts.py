"""Plotly figures for the dashboard."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from quant_research.dashboard.theme import AMBER, BG, BLUE, CYAN, DIM, GREEN, PURPLE, RED, WHITE
from quant_research.research.market_data import get_hist


def hex_rgba(h: str, a: float = 1.0) -> str:
    r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
    return f"rgba({r},{g},{b},{a})"


def sparkline_chart(ticker: str):
    """Mini 30-day sparkline for portfolio cards."""
    hist = get_hist(ticker, "30d", "1d")
    if hist.empty or len(hist) < 2:
        return None
    prices = hist["Close"].tolist()
    color = GREEN if prices[-1] >= prices[0] else RED
    fill_color = hex_rgba(color, 0.08)
    fig = go.Figure(
        go.Scatter(
            y=prices,
            mode="lines",
            line=dict(color=color, width=1.5),
            fill="tozeroy",
            fillcolor=fill_color,
        )
    )
    fig.update_layout(
        height=60,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


_CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#0f1318",
    font=dict(color="#d1d4dc", size=12),
    margin=dict(l=0, r=0, t=32, b=0),
    xaxis=dict(showgrid=False, color="#4b5568", zeroline=False, rangeslider=dict(visible=False)),
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


def build_price_chart(ticker: str, avg_cost: float) -> go.Figure:
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
        rows=3,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.60, 0.20, 0.20],
        vertical_spacing=0.03,
    )

    fig.add_trace(
        go.Candlestick(
            x=dates,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=close,
            name=ticker,
            increasing_line_color=GREEN,
            decreasing_line_color=RED,
            increasing_fillcolor=hex_rgba(GREEN, 0.53),
            decreasing_fillcolor=hex_rgba(RED, 0.53),
            line=dict(width=1),
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=dates,
            y=bb_up,
            name="BB Upper",
            line=dict(color=hex_rgba(CYAN, 0.33), width=1, dash="dot"),
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=bb_dn,
            name="BB Lower",
            line=dict(color=hex_rgba(CYAN, 0.33), width=1, dash="dot"),
            fill="tonexty",
            fillcolor="rgba(34,211,238,0.08)",
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=bb_mid,
            name="BB Mid",
            line=dict(color=hex_rgba(CYAN, 0.5), width=1),
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    if avg_cost and avg_cost > 0:
        fig.add_hline(
            y=avg_cost,
            line_color=AMBER,
            line_dash="dash",
            line_width=1.5,
            annotation_text=f"Avg ${avg_cost:.2f}",
            annotation_font_color=AMBER,
            annotation_font_size=11,
            row=1,
            col=1,
        )

    fig.add_trace(
        go.Scatter(
            x=dates,
            y=rsi,
            name="RSI",
            line=dict(color=PURPLE, width=1.5),
            showlegend=False,
        ),
        row=2,
        col=1,
    )
    fig.add_hline(y=70, line_color=hex_rgba(RED, 0.4), line_dash="dot", line_width=1, row=2, col=1)
    fig.add_hline(y=30, line_color=hex_rgba(GREEN, 0.4), line_dash="dot", line_width=1, row=2, col=1)
    fig.add_hrect(y0=70, y1=100, fillcolor=hex_rgba(RED, 0.03), line_width=0, row=2, col=1)
    fig.add_hrect(y0=0, y1=30, fillcolor=hex_rgba(GREEN, 0.03), line_width=0, row=2, col=1)

    fig.add_trace(
        go.Bar(
            x=dates,
            y=hist,
            name="MACD Hist",
            marker_color=hist_colors,
            showlegend=False,
        ),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=macd,
            name="MACD",
            line=dict(color=BLUE, width=1.5),
            showlegend=False,
        ),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=signal,
            name="Signal",
            line=dict(color=AMBER, width=1.2),
            showlegend=False,
        ),
        row=3,
        col=1,
    )

    layout = dict(**_CHART_LAYOUT)
    layout.update(
        height=520,
        title=dict(text=f"<b>{ticker}</b>  60-Day Chart", font=dict(size=14, color=WHITE), x=0),
        yaxis2=dict(title="RSI", showgrid=True, gridcolor="#1e2533", color="#4b5568", range=[0, 100], zeroline=False),
        yaxis3=dict(title="MACD", showgrid=True, gridcolor="#1e2533", color="#4b5568", zeroline=False),
        xaxis3=dict(showgrid=False, color="#4b5568", zeroline=False, rangeslider=dict(visible=False)),
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
    colors = [BLUE, CYAN, PURPLE, AMBER, GREEN, RED, "#f97316", "#84cc16", "#ec4899", "#14b8a6"][: len(labels)]
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.55,
            marker=dict(colors=colors, line=dict(color=BG, width=2)),
            textinfo="label+percent",
            textfont=dict(size=12, color=WHITE),
            hovertemplate="%{label}: %{value:.1f}%<extra></extra>",
        )
    )
    _lay = dict(**_CHART_LAYOUT)
    _lay.update(
        height=280,
        margin=dict(l=0, r=0, t=36, b=0),
        title=dict(text="Sector Exposure", font=dict(size=13, color=WHITE), x=0),
        showlegend=False,
    )
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

    fig = go.Figure(
        go.Bar(
            x=pcts,
            y=tickers,
            orientation="h",
            marker=dict(color=colors, opacity=0.85),
            text=[f"{p:.1f}%" for p in pcts],
            textposition="outside",
            textfont=dict(color=WHITE, size=12),
            hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
        )
    )
    _lay = dict(**_CHART_LAYOUT)
    _lay.update(
        height=max(180, len(tickers) * 48),
        margin=dict(l=0, r=80, t=36, b=20),
        title=dict(text="Portfolio Allocation", font=dict(size=13, color=WHITE), x=0),
        xaxis=dict(
            showgrid=True,
            gridcolor="#1e2533",
            color="#4b5568",
            ticksuffix="%",
            zeroline=False,
            rangeslider=dict(visible=False),
        ),
        yaxis=dict(showgrid=False, color=WHITE, zeroline=False, autorange="reversed"),
    )
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

    fig = go.Figure(
        go.Bar(
            x=tickers,
            y=pnls,
            marker=dict(color=colors, opacity=0.85),
            text=[f"{p:+.1f}%" for p in pcts],
            textposition="auto",
            textfont=dict(color=WHITE, size=11),
            hovertemplate="%{x}<br>P&L: $%{y:,.2f}<extra></extra>",
        )
    )
    fig.add_hline(y=0, line_color=DIM, line_width=1)
    _lay = dict(**_CHART_LAYOUT)
    _lay.update(
        height=320,
        margin=dict(l=0, r=0, t=50, b=50),
        title=dict(text="Open P&L by Position", font=dict(size=13, color=WHITE), x=0),
        yaxis=dict(**_CHART_YAXIS, tickprefix="$", automargin=True),
    )
    fig.update_layout(**_lay)
    return fig
