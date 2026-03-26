#!/usr/bin/env python3
"""email_report.py -- Daily morning portfolio report sender
Reads data/master_portfolio.json and data/users.json
Sends personalized HTML emails with P&L, signals, macro, private exposure
Required Secrets: SENDER_EMAIL, EMAIL_PASSWORD, RECIPIENT_EMAIL
"""

import os, json, smtplib, datetime
import yfinance as yf
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

SENDER      = os.environ["SENDER_EMAIL"]
PASSWORD    = os.environ["EMAIL_PASSWORD"]
OWNER_EMAIL = os.environ["RECIPIENT_EMAIL"]
TODAY       = datetime.date.today().strftime("%A, %B %d, %Y")
BASE_DIR    = Path(__file__).parent

PRIVATE_COMPANIES = {
    "Anthropic": {"valuation": "$61.5B", "round": "Series F",
                  "proxies": ["AMZN","GOOG","NVDA","MSFT","ARM"],
                  "weights": {"AMZN":0.27,"GOOG":0.10,"NVDA":0.30,"MSFT":0.15,"ARM":0.18}},
    "SpaceX":    {"valuation": "$350B",  "round": "Tender Offer",
                  "proxies": ["RKLB","ASTS","LUNR","KTOS"],
                  "weights": {"RKLB":0.35,"ASTS":0.25,"LUNR":0.20,"KTOS":0.20}},
    "OpenAI":    {"valuation": "$300B",  "round": "Series F+",
                  "proxies": ["MSFT","NVDA","ARM"],
                  "weights": {"MSFT":0.60,"NVDA":0.30,"ARM":0.10}},
    "xAI":       {"valuation": "$50B",   "round": "Series B",
                  "proxies": ["TSLA"], "weights": {"TSLA":1.0}},
    "Stripe":    {"valuation": "$91.5B", "round": "Secondary",
                  "proxies": ["SQ","ADYEN"], "weights": {"SQ":0.55,"ADYEN":0.45}},
}

MACRO_TICKERS = {
    "S&P 500": "SPY", "NASDAQ": "QQQ", "VIX": "^VIX",
    "10Y Treasury": "^TNX", "2Y Treasury": "^IRX",
    "Dollar (DXY)": "DX-Y.NYB", "Gold": "GC=F", "Oil": "CL=F"
}


def load_json(rel_path, key):
    p = BASE_DIR / rel_path
    if p.exists():
        return json.loads(p.read_text()).get(key, [])
    return []


def fetch_prices(tickers):
    if not tickers: return {}
    data = yf.download(list(set(tickers)), period="2d", auto_adjust=True, progress=False)
    results = {}
    for t in tickers:
        try:
            closes = data["Close"][t].dropna()
            if len(closes) >= 2:
                price = float(closes.iloc[-1])
                prev  = float(closes.iloc[-2])
                results[t] = {"price": price, "prev": prev,
                              "change": price - prev,
                              "change_pct": ((price - prev) / prev) * 100}
            elif len(closes) == 1:
                price = float(closes.iloc[-1])
                results[t] = {"price": price, "prev": price, "change": 0, "change_pct": 0}
        except Exception:
            pass
    return results


def portfolio_stats(holdings, prices):
    rows = []
    total_cost = total_val = total_pnl = 0
    for h in holdings:
        t      = h.get("ticker", "").upper()
        avg    = float(h.get("avgPrice", 0))
        shares = float(h.get("shares", 0))
        p      = prices.get(t, {})
        price  = p.get("price")
        cost   = avg * shares
        value  = price * shares if price else None
        pnl    = value - cost if value is not None else None
        dpnl   = p.get("change", 0) * shares if price else None
        total_cost += cost
        total_val  += value or 0
        total_pnl  += pnl or 0
        rows.append({"ticker": t, "shares": shares, "avg": avg, "price": price,
                     "value": value, "pnl": pnl, "daily_pnl": dpnl,
                     "change_pct": p.get("change_pct", 0)})
    ret = ((total_val - total_cost) / total_cost * 100) if total_cost else 0
    return rows, total_cost, total_val, total_pnl, ret


def compute_rsi(closes, period=14):
    delta = closes.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss
    return (100 - 100 / (1 + rs)).iloc[-1]


def compute_signals(tickers, prices):
    if not tickers: return []
    data = yf.download(list(set(tickers)), period="60d", auto_adjust=True, progress=False)
    out  = []
    for t in tickers:
        try:
            closes = data["Close"][t].dropna()
            if len(closes) < 20: continue
            rsi    = compute_rsi(closes)
            price  = prices.get(t, {}).get("price", float(closes.iloc[-1]))
            mom5d  = ((closes.iloc[-1] / closes.iloc[-5])  - 1) * 100 if len(closes) >= 5  else 0
            mom21d = ((closes.iloc[-1] / closes.iloc[-21]) - 1) * 100 if len(closes) >= 21 else 0
            if   rsi < 30: sig = "STRONG BUY"
            elif rsi < 45: sig = "BUY"
            elif rsi > 70: sig = "STRONG SELL"
            elif rsi > 60: sig = "SELL"
            else:          sig = "NEUTRAL"
            out.append({"ticker": t, "price": price, "rsi": round(rsi, 1),
                        "mom5d": round(mom5d, 2), "mom21d": round(mom21d, 2), "signal": sig})
        except Exception:
            pass
    return out


def private_scores(prices):
    out = {}
    for co, info in PRIVATE_COMPANIES.items():
        weighted = total_w = 0
        for t, w in info["weights"].items():
            p = prices.get(t, {})
            if p.get("change_pct") is not None:
                weighted += p["change_pct"] * w
                total_w  += w
        out[co] = {"valuation": info["valuation"], "round": info["round"],
                   "score": round(weighted / total_w, 3) if total_w else 0}
    return out


# HTML helpers
def clr(v):  return "#3fb950" if (v or 0) >= 0 else "#f85149"
def fpct(v): return ("+{:.2f}%".format(v) if v >= 0 else "{:.2f}%".format(v))
def fusd(v):
    if v is None: return "—"
    return ("+${:,.2f}".format(v) if v >= 0 else "-${:,.2f}".format(abs(v)))
def sig_clr(s):
    return {"STRONG BUY":"#3fb950","BUY":"#3fb950",
            "NEUTRAL":"#8b949e","SELL":"#f85149","STRONG SELL":"#f85149"}.get(s,"#8b949e")

TH = "padding:8px;text-align:left;font-size:.78rem;color:#8b949e;"
CARD = "background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:12px 16px;flex:1;min-width:140px;"


def build_html(name, rows, cost, val, pnl, ret, signals, macro_p, priv_s):
    # Portfolio rows
    p_rows = ""
    for r in rows:
        c   = r["avg"] * r["shares"]
        ret2 = (r["pnl"] / c * 100) if r["pnl"] is not None and c else 0
        ps  = "${:.2f}".format(r["price"]) if r["price"] else "—"
        p_rows += (
            "<tr>"
            "<td style='padding:8px;font-weight:600'>{tk}</td>"
            "<td style='padding:8px'>{sh}</td>"
            "<td style='padding:8px'>${avg:.2f}</td>"
            "<td style='padding:8px'>{ps}</td>"
            "<td style='padding:8px'>{val}</td>"
            "<td style='padding:8px;color:{cpnl}'>{fpnl}</td>"
            "<td style='padding:8px;color:{cret}'>{fret}</td>"
            "<td style='padding:8px;color:{ctd}'>{ftd}</td>"
            "</tr>"
        ).format(tk=r["ticker"],sh=r["shares"],avg=r["avg"],ps=ps,
                 val=fusd(r["value"]),
                 cpnl=clr(r["pnl"]),fpnl=fusd(r["pnl"]),
                 cret=clr(ret2),fret=fpct(ret2),
                 ctd=clr(r["change_pct"]),ftd=fpct(r["change_pct"]))

    # Signal rows
    s_rows = ""
    for s in signals:
        s_rows += (
            "<tr>"
            "<td style='padding:8px;font-weight:600'>{tk}</td>"
            "<td style='padding:8px'>${pr:.2f}</td>"
            "<td style='padding:8px'>{rsi}</td>"
            "<td style='padding:8px;color:{c5}'>{f5}</td>"
            "<td style='padding:8px;color:{c21}'>{f21}</td>"
            "<td style='padding:8px;color:{csg};font-weight:700'>{sig}</td>"
            "</tr>"
        ).format(tk=s["ticker"],pr=s["price"],rsi=s["rsi"],
                 c5=clr(s["mom5d"]),f5=fpct(s["mom5d"]),
                 c21=clr(s["mom21d"]),f21=fpct(s["mom21d"]),
                 csg=sig_clr(s["signal"]),sig=s["signal"])

    # Macro rows
    m_rows = ""
    for label, key in MACRO_TICKERS.items():
        m = macro_p.get(key, {})
        if not m: continue
        m_rows += (
            "<tr>"
            "<td style='padding:8px'>{lb}</td>"
            "<td style='padding:8px'>${pr:.2f}</td>"
            "<td style='padding:8px;color:{c}'>{f}</td>"
            "</tr>"
        ).format(lb=label, pr=m.get("price",0),
                 c=clr(m.get("change_pct",0)), f=fpct(m.get("change_pct",0)))

    # Private rows
    pr_rows = ""
    for co, info in priv_s.items():
        sc = info["score"]
        pr_rows += (
            "<tr>"
            "<td style='padding:8px;font-weight:600'>{co}</td>"
            "<td style='padding:8px'>{val}</td>"
            "<td style='padding:8px'>{rnd}</td>"
            "<td style='padding:8px;color:{c};font-weight:700'>{f}</td>"
            "</tr>"
        ).format(co=co, val=info["valuation"], rnd=info["round"],
                 c=clr(sc), f=fpct(sc))

    # Build full HTML - using format() so no f-string curly brace conflicts
    html_parts = [
        "<!DOCTYPE html><html><head><meta charset='UTF-8'/></head>",
        "<body style='margin:0;padding:0;background:#0d1117;font-family:Segoe UI,Arial,sans-serif;color:#e6edf3;'>",
        "<div style='max-width:700px;margin:0 auto;padding:24px;'>",

        # Header
        "<div style='background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px 24px;margin-bottom:16px;'>",
        "  <h2 style='margin:0 0 4px;color:#58a6ff;'>&#9642; Quant Research System</h2>",
        "  <p style='margin:0;color:#8b949e;font-size:.85rem;'>Morning Report &mdash; " + TODAY + "</p>",
        "  <p style='margin:4px 0 0;'>Good morning, <strong>" + name + "</strong>.</p>",
        "</div>",

        # Portfolio summary
        "<div style='background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px 24px;margin-bottom:16px;'>",
        "  <h3 style='margin:0 0 12px;'>Portfolio Summary</h3>",
        "  <div style='display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;'>",
        ("    <div style='" + CARD + "'><div style='font-size:.78rem;color:#8b949e;text-transform:uppercase;'>Market Value</div>"
         "    <div style='font-size:1.4rem;font-weight:700;'>${val:,.2f}</div></div>").format(val=val),
        ("    <div style='" + CARD + "'><div style='font-size:.78rem;color:#8b949e;text-transform:uppercase;'>Total P&amp;L</div>"
         "    <div style='font-size:1.4rem;font-weight:700;color:{c};'>{f}</div></div>").format(c=clr(pnl),f=fusd(pnl)),
        ("    <div style='" + CARD + "'><div style='font-size:.78rem;color:#8b949e;text-transform:uppercase;'>Total Return</div>"
         "    <div style='font-size:1.4rem;font-weight:700;color:{c};'>{f}</div></div>").format(c=clr(ret),f=fpct(ret)),
        "  </div>",
        "  <table style='width:100%;border-collapse:collapse;'>",
        "    <thead><tr style='border-bottom:1px solid #30363d;'>",
        ("      <th style='" + TH + "'>TICKER</th><th style='" + TH + "'>SHARES</th>"
         "      <th style='" + TH + "'>AVG</th><th style='" + TH + "'>PRICE</th>"
         "      <th style='" + TH + "'>VALUE</th><th style='" + TH + "'>P&amp;L</th>"
         "      <th style='" + TH + "'>RETURN</th><th style='" + TH + "'>TODAY</th>"),
        "    </tr></thead>",
        "    <tbody>" + p_rows + "</tbody>",
        "  </table>",
        "</div>",

        # Signals
        "<div style='background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px 24px;margin-bottom:16px;'>",
        "  <h3 style='margin:0 0 12px;'>Signal Table</h3>",
        "  <table style='width:100%;border-collapse:collapse;'>",
        "    <thead><tr style='border-bottom:1px solid #30363d;'>",
        ("      <th style='" + TH + "'>TICKER</th><th style='" + TH + "'>PRICE</th>"
         "      <th style='" + TH + "'>RSI</th><th style='" + TH + "'>MOM 5D</th>"
         "      <th style='" + TH + "'>MOM 21D</th><th style='" + TH + "'>SIGNAL</th>"),
        "    </tr></thead>",
        "    <tbody>" + s_rows + "</tbody>",
        "  </table>",
        "</div>",

        # Macro
        "<div style='background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px 24px;margin-bottom:16px;'>",
        "  <h3 style='margin:0 0 12px;'>Macro Snapshot</h3>",
        "  <table style='width:100%;border-collapse:collapse;'>",
        "    <thead><tr style='border-bottom:1px solid #30363d;'>",
        ("      <th style='" + TH + "'>MARKET</th><th style='" + TH + "'>PRICE</th><th style='" + TH + "'>CHG</th>"),
        "    </tr></thead>",
        "    <tbody>" + m_rows + "</tbody>",
        "  </table>",
        "</div>",

        # Private exposure
        "<div style='background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px 24px;margin-bottom:16px;'>",
        "  <h3 style='margin:0 0 4px;'>Private Company Exposure</h3>",
        "  <p style='color:#8b949e;font-size:.8rem;margin-bottom:12px;'>Proxy-weighted momentum. Positive = tailwind.</p>",
        "  <table style='width:100%;border-collapse:collapse;'>",
        "    <thead><tr style='border-bottom:1px solid #30363d;'>",
        ("      <th style='" + TH + "'>COMPANY</th><th style='" + TH + "'>VALUATION</th>"
         "      <th style='" + TH + "'>ROUND</th><th style='" + TH + "'>PROXY SCORE</th>"),
        "    </tr></thead>",
        "    <tbody>" + pr_rows + "</tbody>",
        "  </table>",
        "</div>",

        "<p style='text-align:center;color:#8b949e;font-size:.75rem;margin-top:24px;'>",
        "Quant Research System &bull; <a href='https://luizhmacedo.github.io/quant-research-system'",
        " style='color:#58a6ff;'>luizhmacedo.github.io/quant-research-system</a></p>",
        "</div></body></html>"
    ]
    return "".join(html_parts)


def send_email(to, subject, html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER
    msg["To"]      = to
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(SENDER, PASSWORD)
        s.sendmail(SENDER, to, msg.as_string())
    print("  Sent to", to)


def main():
    print("=== Morning Report:", TODAY, "===")
    master = load_json("data/master_portfolio.json", "portfolio")
    users  = load_json("data/users.json", "users")

    all_tickers = set()
    for h in master: all_tickers.add(h["ticker"].upper())
    for u in users:
        for h in u.get("stocks", []): all_tickers.add(h["ticker"].upper())
    for co in PRIVATE_COMPANIES.values(): all_tickers.update(co["proxies"])
    all_tickers.update(MACRO_TICKERS.values())

    print("Fetching", len(all_tickers), "tickers...")
    prices  = fetch_prices(list(all_tickers))
    macro_p = {k: prices.get(v, {}) for k, v in MACRO_TICKERS.items()}
    priv_s  = private_scores(prices)

    if master:
        rows, cost, val, pnl, ret = portfolio_stats(master, prices)
        signals = compute_signals([h["ticker"].upper() for h in master], prices)
        html    = build_html("Luiz", rows, cost, val, pnl, ret, signals, macro_p, priv_s)
        subj    = "Morning Report {} - ${:,.0f} ({})".format(TODAY, val, fpct(ret))
        send_email(OWNER_EMAIL, subj, html)

    for u in users:
        name  = u.get("name", "Investor")
        email = u.get("email", "")
        stks  = u.get("stocks", [])
        if not email or not stks: continue
        rows, cost, val, pnl, ret = portfolio_stats(stks, prices)
        signals = compute_signals([h["ticker"].upper() for h in stks], prices)
        html    = build_html(name, rows, cost, val, pnl, ret, signals, macro_p, priv_s)
        subj    = "Morning Report {} - ${:,.0f} ({})".format(TODAY, val, fpct(ret))
        try:    send_email(email, subj, html)
        except Exception as e: print("  ERROR", email, e)

    print("=== Done ===")


if __name__ == "__main__":
    main()
