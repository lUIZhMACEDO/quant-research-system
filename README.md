# Quant Research System

A daily equity research pipeline I built to stop checking tickers by hand. It pulls end-of-day
market data, computes indicators, runs five screens over a watchlist, and emails me a report every
weekday morning. There's also a Streamlit dashboard for looking at a single name in more detail.

Live dashboard: https://ai-stock-analyst-1.streamlit.app

## What it actually does

**Ingest** (`ingest.py`)

- 5 years of daily OHLCV per ticker from yfinance, with Tiingo as the backup source
- 16 FRED series: the Treasury curve (3M–30Y), 10Y–2Y and 10Y–3M spreads, high-yield and
  investment-grade OAS, the broad dollar index, VIX, unemployment, CPI, M2, fed funds, 30Y mortgage
- Fundamentals per ticker: trailing and forward P/E, price/book, price/sales, EV/EBITDA, FCF yield,
  ROE, margins, debt/equity, analyst target and consensus rating, short interest
- Indicators computed in one vectorized pass over the full series rather than row by row: RSI-14 and
  its 252-day z-score, MACD, Bollinger bands and position within the band, SMA 50/200, EMA 20,
  golden/death cross, ATR-14, 21-day realized volatility, 5/21/63/252-day momentum, volume z-score,
  and a Hurst exponent over 64-bar windows (rescaled-range method) as a trend/mean-reversion read
- Everything lands in SQLite (`schema.sql`, 13 tables, WAL mode)

**Screens and report** (`main.py`)

Five rule-based screens run per ticker — RSI/MACD confluence, Bollinger mean reversion, golden
cross, post-earnings rebound, and an analyst/institutional screen — and their agreement becomes a
composite score. News headlines are pulled per ticker and rated with the Anthropic API, and the
result goes into a dark-themed HTML email built with `smtplib`. A GitHub Actions workflow runs this
Monday through Friday.

**Dashboard** (`app.py`)

Streamlit app with live Finnhub quotes (yfinance fallback), candlestick charts with Bollinger bands
plus RSI and MACD panels, sector exposure, and a portfolio view. The ticker tape and KPI row refresh
on a fragment so the whole page doesn't reload.

## What it does not do

Worth saying plainly, because the layout invites the assumption:

- **No machine learning in this repo.** The walk-forward models, the ensemble, and the cost-modeled
  backtester live in [trading-bot-ml](https://github.com/lUIZhMACEDO/trading-bot-ml). The screens
  here are rules, not fitted models.
- **The private-company exposure scores are a heuristic**, not a valuation. They combine a handful of
  public proxy tickers with weights I set by hand, and the reported funding-round valuations are
  whatever was public when I wrote them down.
- **It's research, not execution.** Nothing here places an order, and none of it is investment advice.

## Running it

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# create a .env with the keys listed below
python ingest.py            # builds quant.db — first run takes a few minutes
streamlit run app.py        # dashboard
python main.py              # scores the watchlist and sends the email report
```

Environment variables: `TIINGO_API_KEY`, `FINNHUB_API_KEY`, `ANTHROPIC_API_KEY`, and SMTP settings
for the email report (`SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `REPORT_TO`). FRED's public series need
no key. The dashboard runs without the email settings.

## Layout

```
ingest.py      data pipeline: prices, macro, fundamentals, indicators
main.py        screens, news sentiment, HTML email report
app.py         Streamlit dashboard
schema.sql     SQLite schema, 13 tables
.github/workflows/daily-report.yml   weekday run of main.py
```

## Notes

Data comes from yfinance, Tiingo, Finnhub, and FRED, each under its own terms — check them before
you reuse anything here. The watchlist and thresholds are mine and are not tuned for anyone else's
risk tolerance.
