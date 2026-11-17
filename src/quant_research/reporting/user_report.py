"""Per-user portfolio report sent from the dashboard (HTML + plain text).

User-entered tickers and provider-supplied names are HTML-escaped before they are
interpolated into the email.
"""

from __future__ import annotations

import datetime as dt
from html import escape


def build_user_report(holdings: list[dict], risk_d: dict, sp: dict, now: dt.datetime | None = None) -> tuple[str, str]:
    """Return ``(html, text)`` for a dashboard user's holdings."""
    now = now or dt.datetime.now()
    today_s = now.strftime("%A, %B %d, %Y")
    now_s = now.strftime("%I:%M %p")

    B = "#0b0e11"
    C = "#141821"
    A = "#1a1f2b"
    BD = "#1e2533"
    T = "#d1d4dc"
    D = "#6b7280"
    G = "#00d26a"
    R = "#f6465d"
    AM = "#f0b90b"
    W = "#ffffff"
    CY = "#22d3ee"

    def ec(v):
        return G if v >= 0 else R

    def ep(v):
        return f'<span style="color:{ec(v)};font-weight:700;">{"+" if v >= 0 else ""}{v:.2f}%</span>'

    def kpi(label, val, color=W):
        return (
            f'<td style="padding:8px 12px;text-align:center;"><div style="font-size:9px;color:{D};'
            f'text-transform:uppercase;letter-spacing:.5px;">{label}</div>'
            f'<div style="font-size:14px;font-weight:700;color:{color};">{val}</div></td>'
        )

    def sig_html(sig):
        if "BUY" in sig.upper():
            sc = G
        elif "SELL" in sig.upper():
            sc = R
        elif "TRIM" in sig.upper() or "WATCH" in sig.upper():
            sc = AM
        else:
            sc = D
        return (
            f'<span style="padding:3px 12px;border-radius:4px;background:{sc}1a;'
            f'color:{sc};font-weight:700;font-size:11px;">{sig}</span>'
        )

    tv = sum(h["market_value"] for h in holdings)
    tc = sum(h["total_cost"] for h in holdings)
    tp = tv - tc
    tpct = tp / tc * 100 if tc else 0
    tdp = sum(h["day_pnl"] for h in holdings)

    mood_c = G if sp.get("spy_mood") == "Bullish" else R if sp.get("spy_mood") == "Bearish" else AM

    # ── Per-stock detail cards ──
    cards = ""
    for h in holdings:
        t = h.get("tech", {})
        e = h.get("earn", {})
        a = h.get("analyst", {})
        tl = h.get("timeline", {})
        pe_s = f'{h["pe"]:.1f}' if h.get("pe") else "N/A"
        rsi_s = f'{t["rsi"]:.0f} ({t["rsi_label"]})' if t.get("rsi") else "N/A"

        info_parts = []
        if e.get("days_to_earnings") is not None:
            info_parts.append(
                f'Earnings in {e["days_to_earnings"]}d'
                + (f' ({e["next_earnings"].strftime("%b %d")})' if e.get("next_earnings") else "")
            )
        info_parts.append(
            f'Analyst: {a.get("rec_buy", 0)} Buy / {a.get("rec_hold", 0)} Hold / {a.get("rec_sell", 0)} Sell'
        )
        if a.get("target_mean"):
            info_parts.append(f'Target: ${a["target_low"]:.0f} / ${a["target_mean"]:.0f} / ${a["target_high"]:.0f}')
        info_parts.append(f'Insider (30d): {a.get("insider_buys", 0)} buys / {a.get("insider_sells", 0)} sells')

        cards += f"""
        <div style="background:{C};border:1px solid {BD};border-radius:10px;padding:18px 22px;margin-bottom:14px;">
          <table width="100%" cellpadding="0" cellspacing="0"><tr>
            <td style="padding:0;"><span style="font-size:18px;font-weight:800;color:{W};">{escape(h["ticker"])}</span>
              <span style="font-size:12px;color:{D};margin-left:8px;">{escape(h["name"])}</span></td>
            <td style="padding:0;text-align:right;">{sig_html(h["signal"])}</td>
          </tr></table>
          <div style="font-size:11px;color:{D};margin-top:4px;font-style:italic;">{escape(h["reason"])}</div>
          <div style="font-size:12px;color:{AM};margin-top:4px;font-weight:600;">Action: {h["action"]}</div>

          <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px;background:{A};border-radius:6px;">
            <tr>
              {kpi("Price", f'${h["current_price"]:,.2f}', W)}
              {kpi("Avg Cost", f'${h["avg_cost"]:,.2f}', T)}
              {kpi("Shares", int(h["shares"]), W)}
              {kpi("PE", pe_s, AM)}
              {kpi("RSI", rsi_s, W)}
            </tr>
          </table>

          <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:6px;background:{A};border-radius:6px;">
            <tr>
              {kpi("Open P&L", f'{"+" if h["open_pnl"] >= 0 else ""}${h["open_pnl"]:,.2f}', ec(h["open_pnl"]))}
              {kpi("Open P&L %", f'{"+" if h["open_pnl_pct"] >= 0 else ""}{h["open_pnl_pct"]:.2f}%', ec(h["open_pnl_pct"]))}
              {kpi("Day P&L", f'{"+" if h["day_pnl"] >= 0 else ""}${h["day_pnl"]:,.2f}', ec(h["day_pnl"]))}
              {kpi("Day P&L %", f'{"+" if h["day_pnl_pct"] >= 0 else ""}{h["day_pnl_pct"]:.2f}%', ec(h["day_pnl_pct"]))}
            </tr>
          </table>

          <div style="margin-top:10px;padding:10px 14px;background:{A};border-radius:6px;
                      font-size:11px;color:{T};line-height:1.7;">
            {"<br>".join(info_parts)}
          </div>

          <div style="margin-top:10px;padding:10px 14px;background:{A};border-radius:6px;font-size:11px;line-height:1.7;">
            <div style="color:{CY};font-weight:600;">Short-term (0-30d):</div>
            <div style="color:{T};">{tl.get("short_level", "N/A")}<br>{tl.get("short_trigger", "")}</div>
            <div style="color:{CY};font-weight:600;margin-top:4px;">Medium-term (1-6mo):</div>
            <div style="color:{T};">{tl.get("med_catalyst", "N/A")}<br>{tl.get("med_target", "")}</div>
            <div style="color:{CY};font-weight:600;margin-top:4px;">Long-term (6-24mo):</div>
            <div style="color:{T};">{tl.get("long_thesis", "N/A")}<br>Invalidate: {tl.get("long_invalidate", "N/A")}</div>
          </div>
        </div>"""

    # ── Technicals table ──
    tech_rows = ""
    for h in holdings:
        t = h.get("tech", {})
        tech_rows += f"""<tr style="background:{C};">
          <td style="padding:8px 10px;color:{W};font-weight:700;border-bottom:1px solid {BD};">{escape(h["ticker"])}</td>
          <td style="padding:8px 10px;color:{W};border-bottom:1px solid {BD};">${h["current_price"]:,.2f}</td>
          <td style="padding:8px 10px;color:{T};border-bottom:1px solid {BD};">{f'{t["rsi"]:.0f}' if t.get("rsi") else "N/A"}</td>
          <td style="padding:8px 10px;color:{T};border-bottom:1px solid {BD};">{t.get("rsi_label", "N/A")}</td>
          <td style="padding:8px 10px;color:{T};border-bottom:1px solid {BD};">{t.get("macd_label", "N/A")}</td>
          <td style="padding:8px 10px;color:{T};border-bottom:1px solid {BD};">{t.get("bb_label", "N/A")}</td>
          <td style="padding:8px 10px;color:{T};border-bottom:1px solid {BD};">{t.get("ema_label", "N/A")}</td>
          <td style="padding:8px 10px;color:{T};border-bottom:1px solid {BD};">{t.get("vol_label", "N/A")}</td>
        </tr>"""

    # ── Risk dashboard ──
    risk_rows = ""
    for p in risk_d.get("positions", []):
        risk_rows += f"""<tr style="background:{C};">
          <td style="padding:6px 10px;color:{W};font-weight:700;border-bottom:1px solid {BD};">{escape(p["ticker"])}</td>
          <td style="padding:6px 10px;color:{T};border-bottom:1px solid {BD};">{p["weight"]:.1f}%</td>
          <td style="padding:6px 10px;color:{T};border-bottom:1px solid {BD};">{p["beta"]:.2f}</td>
          <td style="padding:6px 10px;color:{T};border-bottom:1px solid {BD};">${p["risk_1d"]:,.2f}</td>
        </tr>"""

    sector_html = ""
    for sec, exp in sorted(risk_d.get("sectors", {}).items(), key=lambda x: -x[1]):
        sector_html += f'<span style="display:inline-block;margin:2px 6px 2px 0;padding:3px 10px;background:{A};border-radius:4px;font-size:11px;color:{T};">{escape(str(sec))} {exp:.1f}%</span>'

    html = f"""<html><head><meta charset="utf-8"></head>
    <body style="margin:0;padding:0;background:{B};font-family:'Segoe UI',Arial,sans-serif;">
    <div style="max-width:700px;margin:0 auto;padding:20px;">

      <!-- HEADER -->
      <div style="background:linear-gradient(135deg,{C},{A});border-radius:12px;padding:20px 24px;
                  margin-bottom:16px;border:1px solid {BD};">
        <table width="100%" cellpadding="0" cellspacing="0"><tr>
          <td style="padding:0;">
            <div style="font-size:22px;font-weight:800;color:{W};">Stock Analyst</div>
            <div style="font-size:11px;color:{D};margin-top:2px;">{today_s} | {now_s}</div>
          </td>
          <td style="padding:0;text-align:right;">
            <div style="color:{D};font-size:11px;">S&amp;P 500</div>
            <div><span style="font-size:18px;font-weight:800;color:{W};">${sp["price"]:,.2f}</span>
              {ep(sp["change"])}</div>
            <div style="font-size:11px;margin-top:2px;">
              <span style="color:{D};">SPY</span>
              <span style="color:{mood_c};font-weight:700;margin-left:4px;">{sp.get("spy_mood", "")}</span>
            </div>
          </td>
        </tr></table>
      </div>

      <!-- PORTFOLIO KPIs -->
      <div style="background:{C};border-radius:10px;padding:16px 20px;margin-bottom:16px;border:1px solid {BD};">
        <div style="font-size:13px;color:{AM};font-weight:700;margin-bottom:10px;">PORTFOLIO SUMMARY</div>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            {kpi("Value", f"${tv:,.2f}", W)}
            {kpi("Cost", f"${tc:,.2f}", T)}
            {kpi("Open P&L", f'{"+" if tp >= 0 else ""}${tp:,.2f} ({tpct:+.1f}%)', ec(tp))}
            {kpi("Today P&L", f'{"+" if tdp >= 0 else ""}${tdp:,.2f}', ec(tdp))}
          </tr>
        </table>
      </div>

      <!-- STOCK DETAIL CARDS -->
      <div style="font-size:15px;font-weight:700;color:{W};margin-bottom:10px;">YOUR HOLDINGS</div>
      {cards}

      <!-- TECHNICALS -->
      <div style="font-size:15px;font-weight:700;color:{W};margin:20px 0 10px;">TECHNICAL SNAPSHOT</div>
      <div style="overflow-x:auto;">
        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
          <thead><tr style="background:{A};">
            <th style="padding:8px 10px;text-align:left;color:{
        D
    };font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">Ticker</th>
            <th style="padding:8px 10px;text-align:left;color:{
        D
    };font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">Price</th>
            <th style="padding:8px 10px;text-align:left;color:{
        D
    };font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">RSI</th>
            <th style="padding:8px 10px;text-align:left;color:{
        D
    };font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">Signal</th>
            <th style="padding:8px 10px;text-align:left;color:{
        D
    };font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">MACD</th>
            <th style="padding:8px 10px;text-align:left;color:{
        D
    };font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">Bollinger</th>
            <th style="padding:8px 10px;text-align:left;color:{
        D
    };font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">EMA</th>
            <th style="padding:8px 10px;text-align:left;color:{
        D
    };font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">Volume</th>
          </tr></thead>
          <tbody>{tech_rows}</tbody>
        </table>
      </div>

      <!-- RISK DASHBOARD -->
      <div style="font-size:15px;font-weight:700;color:{W};margin:20px 0 10px;">RISK DASHBOARD</div>
      <div style="background:{C};border-radius:10px;padding:16px 20px;margin-bottom:14px;border:1px solid {BD};">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            {kpi("Weighted Beta", f'{risk_d["weighted_beta"]:.2f}', W)}
            {kpi("Risk Rating", risk_d["risk_rating"], AM)}
            {kpi("1-Day 95% VaR", f'${risk_d["var_95"]:,.2f}', R)}
          </tr>
        </table>
        {
        ""
        if not risk_rows
        else f'''
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:10px;border-collapse:collapse;">
          <thead><tr style="background:{A};">
            <th style="padding:6px 10px;text-align:left;color:{D};font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">Ticker</th>
            <th style="padding:6px 10px;text-align:left;color:{D};font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">Weight</th>
            <th style="padding:6px 10px;text-align:left;color:{D};font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">Beta</th>
            <th style="padding:6px 10px;text-align:left;color:{D};font-size:9px;text-transform:uppercase;border-bottom:2px solid {BD};">1-Day Risk</th>
          </tr></thead>
          <tbody>{risk_rows}</tbody>
        </table>'''
    }
        {
        ""
        if not sector_html
        else f'<div style="margin-top:10px;"><div style="font-size:10px;color:{D};margin-bottom:4px;">SECTOR EXPOSURE</div>{sector_html}</div>'
    }
      </div>

      <!-- FOOTER -->
      <div style="text-align:center;padding:16px 0;">
        <div style="font-size:10px;color:{D};">Generated by Stock Analyst | Not financial advice</div>
      </div>
    </div></body></html>"""

    # Plain-text fallback
    text = f"Stock Analyst Report -- {today_s}\n"
    text += f"S&P 500: ${sp['price']:,.2f} ({sp['change']:+.2f}%)\n\n"
    for h in holdings:
        t = h.get("tech", {})
        tl = h.get("timeline", {})
        rsi_s = f'RSI {t["rsi"]:.0f} ({t["rsi_label"]})' if t.get("rsi") else "RSI N/A"
        text += f"{'=' * 50}\n"
        text += f"{h['ticker']}  {h['name']}\n"
        text += f"  Price: ${h['current_price']:,.2f}  |  Avg: ${h['avg_cost']:,.2f}  |  Shares: {int(h['shares'])}\n"
        text += f"  Open P&L: ${h['open_pnl']:+,.2f} ({h['open_pnl_pct']:+.2f}%)\n"
        text += f"  Day P&L:  ${h['day_pnl']:+,.2f} ({h['day_pnl_pct']:+.2f}%)\n"
        text += f"  Signal: {h['signal']} -- {h['reason']}\n"
        text += f"  Action: {h['action']}\n"
        text += f"  PE: {h['pe'] or 'N/A'}  |  {rsi_s}  |  MACD: {t.get('macd_label', 'N/A')}\n"
        text += f"  Short: {tl.get('short_level', 'N/A')} | {tl.get('short_trigger', '')}\n"
        text += f"  Medium: {tl.get('med_catalyst', 'N/A')} | {tl.get('med_target', '')}\n"
        text += f"  Long: {tl.get('long_thesis', 'N/A')} | Invalidate: {tl.get('long_invalidate', 'N/A')}\n\n"
    text += f"Risk: Beta {risk_d['weighted_beta']:.2f} | VaR ${risk_d['var_95']:,.2f} | {risk_d['risk_rating']}\n"

    return html, text
