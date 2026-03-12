#!/usr/bin/env python3
"""
Market Dashboard Data Updater
Fetches live data via yfinance + CoinGecko, writes to JSON + regenerates index.html
"""

import json
import os
import traceback
from datetime import datetime
import pytz
import yfinance as yf
import requests

# ── 时区 ──────────────────────────────────────────────────────────────────────
SGT = pytz.timezone("Asia/Singapore")
UTC = pytz.utc

def sgt_now():
    return datetime.now(SGT).strftime("%Y-%m-%d %H:%M SGT")

# ── 战前基准数据（2026-02-27 已验证）────────────────────────────────────────
BASELINES = {
    "gold":    {"price": 5230,       "date": "2026-02-27", "src": "Bitget/Intellectia"},
    "oil":     {"price": 63.80,      "date": "2026-02-27", "src": "FXDailyReport"},
    "dxy":     {"price": 97.57,      "date": "2026-02-27", "src": "FXDailyReport"},
    "btc":     {"price": 65000,      "date": "2026-02-27", "src": "CoinDesk"},
    "sp500":   {"price": 6878.88,    "date": "2026-02-27", "src": "CNBC Official"},
    "nasdaq":  {"price": 22668.21,   "date": "2026-02-27", "src": "CNBC Official"},
    "sse":     {"price": 4162.88,    "date": "2026-02-27", "src": "Yahoo Finance"},
    "hsi":     {"price": 26630.54,   "date": "2026-02-27", "src": "Yahoo Finance"},
    "sti":     {"price": 4995.07,    "date": "2026-02-27", "src": "Yahoo Finance"},
    "twii":    {"price": 35414.49,   "date": "2026-02-27", "src": "Yahoo Finance"},
    "tsmc":    {"price": 2025,       "date": "2026-02-25", "src": "TradingView ATH"},
    "sia":     {"price": 7.17,       "date": "2026-02-27", "src": "SGX"},
    "dbs":     {"price": 57.50,      "date": "2026-02-27", "src": "SGX"},
}

# ── Yahoo Finance tickers ─────────────────────────────────────────────────────
TICKERS = {
    "gold":   "GC=F",       # Gold Futures
    "oil":    "CL=F",       # WTI Crude Futures
    "dxy":    "DX-Y.NYB",   # US Dollar Index
    "btc":    "BTC-USD",    # Bitcoin via Yahoo Finance (fallback)
    "sp500":  "^GSPC",
    "nasdaq": "^IXIC",
    "sse":    "000001.SS",
    "hsi":    "^HSI",
    "sti":    "^STI",
    "twii":   "^TWII",
    "tsmc":   "2330.TW",
    "sia":    "C6L.SI",
    "dbs":    "D05.SI",
}

def fetch_yfinance(key, ticker):
    """Fetch latest price from Yahoo Finance."""
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        price = getattr(info, "last_price", None) or getattr(info, "regularMarketPrice", None)
        if price is None:
            hist = t.history(period="2d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
        return round(float(price), 4) if price else None
    except Exception as e:
        print(f"  ⚠ yfinance {key} ({ticker}): {e}")
        return None

def fetch_btc_coingecko():
    """Fetch BTC price from CoinGecko free API."""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        r = requests.get(url, params={"ids": "bitcoin", "vs_currencies": "usd"}, timeout=10)
        r.raise_for_status()
        return round(r.json()["bitcoin"]["usd"], 2)
    except Exception as e:
        print(f"  ⚠ CoinGecko BTC: {e}")
        return None

def calc_change(current, baseline):
    if current is None or baseline is None or baseline == 0:
        return None, None
    delta = current - baseline
    pct = delta / baseline * 100
    return round(delta, 4), round(pct, 2)

def arrow(pct):
    if pct is None:
        return "—"
    return "▲" if pct >= 0 else "▼"

def fmt_pct(pct, decimals=2):
    if pct is None:
        return "N/A"
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.{decimals}f}%"

def fmt_price(val, decimals=2):
    if val is None:
        return "N/A"
    if val >= 10000:
        return f"{val:,.0f}"
    if val >= 1000:
        return f"{val:,.2f}"
    return f"{val:.{decimals}f}"

# ── FETCH ALL DATA ────────────────────────────────────────────────────────────
print("🔄 Fetching market data...")
data = {}

# Yahoo Finance assets
for key, ticker in TICKERS.items():
    print(f"  Fetching {key} ({ticker})...")
    price = fetch_yfinance(key, ticker)
    base  = BASELINES[key]["price"]
    delta, pct = calc_change(price, base)
    data[key] = {
        "price":    price,
        "baseline": base,
        "delta":    delta,
        "pct":      pct,
        "src":      BASELINES[key]["src"],
        "base_date": BASELINES[key]["date"],
    }

# BTC override via CoinGecko (more accurate than Yahoo Finance)
# data["btc"] already exists from yfinance loop above (BTC-USD ticker)
print("  Fetching BTC (CoinGecko override)...")
btc_price = fetch_btc_coingecko()
if btc_price:
    d, p = calc_change(btc_price, BASELINES["btc"]["price"])
    data["btc"].update({"price": btc_price, "delta": d, "pct": p})
    print(f"  ✓ CoinGecko BTC override: ${btc_price:,.0f}")
else:
    yf_btc = data.get("btc", {}).get("price")
    if yf_btc:
        print(f"  ℹ CoinGecko failed, using yfinance BTC-USD: ${yf_btc:,.0f}")
    else:
        print("  ⚠ BTC price unavailable from both sources")

updated_at = sgt_now()
print(f"\n✅ Data fetched at {updated_at}")
for k, v in data.items():
    status = f"{fmt_price(v['price'])}  {fmt_pct(v.get('pct'))}" if v["price"] else "FAILED"
    print(f"   {k:8s}  {status}")

# ── SAVE JSON ─────────────────────────────────────────────────────────────────
os.makedirs("data", exist_ok=True)
payload = {"updated_at": updated_at, "assets": data}
with open("data/market_data.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
print("\n💾 Saved data/market_data.json")

# ── GENERATE HTML ─────────────────────────────────────────────────────────────
def color_class(pct, invert=False):
    """Return CSS class based on direction."""
    if pct is None:
        return "muted"
    positive = pct >= 0
    if invert:
        positive = not positive
    return "g" if positive else "r"

def sig_badge(key):
    signals = {
        "gold":   ("s-str", "強力買入"),
        "oil":    ("s-hld", "戰時持倉"),
        "dxy":    ("s-hld", "避險支撐"),
        "btc":    ("s-wtc", "謹慎觀望"),
        "sp500":  ("s-hld", "等待整固"),
        "nasdaq": ("s-hld", "謹慎中性"),
        "sse":    ("s-hld", "謹慎配置"),
        "hsi":    ("s-wtc", "關注佈局"),
        "sti":    ("s-hld", "持平中性"),
        "twii":   ("s-hld", "逢低分批"),
        "tsmc":   ("s-str", "戰略重倉"),
        "sia":    ("s-avd", "強烈回避"),
        "dbs":    ("s-buy", "逢低買入"),
    }
    cls, label = signals.get(key, ("s-wtc", "觀望"))
    return f'<span class="sig {cls}">{label}</span>'

def row(icon, name, sub, key, price_fmt=None, base_fmt=None, extra_note="", target="", analyst_note="", analysis="", market_label=""):
    d = data.get(key, {})
    cur  = d.get("price")
    base = d.get("baseline")
    pct  = d.get("pct")
    delta = d.get("delta")

    cur_str  = fmt_price(cur)  if price_fmt is None else price_fmt(cur)
    base_str = fmt_price(base) if base_fmt  is None else base_fmt(base)

    cc = color_class(pct)
    delta_str = ""
    if delta is not None:
        sign = "+" if delta >= 0 else ""
        delta_str = f"{sign}{fmt_price(delta)}"

    bar_w  = min(abs(pct or 0) * 1.5, 100)
    bar_cl = "var(--green)" if (pct or 0) >= 0 else "var(--red)"

    src_label = d.get("src", "")

    return f"""
    <tr>
      <td><div class="c"><div class="arow">
        <div class="aico">{icon}</div>
        <div><div class="aname">{name}</div><div class="asub">{sub}</div></div>
      </div></div></td>
      {f'<td><div class="c ra"><span class="sig s-wtc" style="font-size:7.5px">{market_label}</span></div></td>' if market_label else ''}
      <td><div class="c ra">
        <div class="pm go">{base_str}</div>
        <div class="ps">{d.get('base_date','')} · {src_label}</div>
      </div></td>
      <td><div class="c ra">
        <div class="pm {cc}">{cur_str if cur else '抓取中…'}</div>
        {f'<div class="pn" style="color:var(--muted);font-size:8.5px">{extra_note}</div>' if extra_note else ''}
      </div></td>
      <td><div class="c ra"><div class="dabs {cc}">{delta_str if delta else '—'}</div></div></td>
      <td><div class="c ra">
        <div class="dpct {cc}">{fmt_pct(pct)}</div>
        <div class="bar-bg"><div class="bar-f" style="width:{bar_w:.0f}%;background:{bar_cl}"></div></div>
      </div></td>
      <td><div class="c ra">{sig_badge(key)}</div></td>
      {'<td><div class="c ra"><div class="pm go" style="font-size:12px">' + target + '</div><div class="pn">' + analyst_note + '</div></div></td>' if target else ''}
      <td><div class="c"><div class="nt">{analysis}</div></div></td>
    </tr>"""

# Build table rows
g  = data.get("gold",   {})
o  = data.get("oil",    {})
b  = data.get("btc",    {})
dx = data.get("dxy",    {})
sp = data.get("sp500",  {})
nq = data.get("nasdaq", {})
ss = data.get("sse",    {})
hs = data.get("hsi",    {})
st = data.get("sti",    {})
tw = data.get("twii",   {})
ts = data.get("tsmc",   {})
si = data.get("sia",    {})
db = data.get("dbs",    {})

html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="3600"><!-- 每60分鐘瀏覽器自動刷新（Actions每日4次更新） -->
<title>全球市場戰前 vs 最新 · 自動更新版</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{{
  --bg:#09100f;--surface:#101a18;--s2:#162120;--s3:#1d2b28;
  --border:#243028;--border2:#2e3d38;
  --text:#ddeadd;--muted:#607870;--dim:#354a44;
  --red:#e05040;--red-bg:rgba(224,80,64,.1);--red-mid:#5a1e14;
  --green:#3dbf82;--green-bg:rgba(61,191,130,.08);--green-mid:#1a5035;
  --gold:#d4a847;--gold-bg:rgba(212,168,71,.08);
  --blue:#5b9bd5;--blue-bg:rgba(91,155,213,.08);
  --serif:'Playfair Display',Georgia,serif;
  --sans:'IBM Plex Sans',system-ui,sans-serif;
  --mono:'IBM Plex Mono','Courier New',monospace;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:var(--sans);font-size:13px;line-height:1.6;min-height:100vh}}
header{{background:linear-gradient(135deg,#091210 0%,#0f1e1a 60%,#091510 100%);border-bottom:1px solid var(--border2);padding:36px 28px 28px;position:relative;overflow:hidden}}
header::after{{content:'';position:absolute;inset:0;pointer-events:none;background:radial-gradient(ellipse 80% 70% at 85% 20%,rgba(212,168,71,.06) 0%,transparent 60%),radial-gradient(ellipse 50% 50% at 10% 80%,rgba(61,191,130,.04) 0%,transparent 60%)}}
.h-inner{{max-width:1300px;margin:0 auto;position:relative}}
.war-chip{{display:inline-flex;align-items:center;gap:7px;background:rgba(224,80,64,.15);border:1px solid rgba(224,80,64,.35);color:#f08070;font-family:var(--mono);font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;padding:5px 13px;border-radius:2px;margin-bottom:16px}}
.wd{{width:6px;height:6px;background:var(--red);border-radius:50%;animation:blink 1.4s ease-in-out infinite}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
h1{{font-family:var(--serif);font-size:clamp(24px,5vw,50px);font-weight:900;letter-spacing:-.02em;line-height:1.04;margin-bottom:8px;color:#eaf5ea}}
h1 em{{color:var(--gold);font-style:normal}}
.h-sub{{font-family:var(--mono);font-size:10px;color:var(--muted);letter-spacing:.06em;margin-bottom:22px}}
.update-badge{{display:inline-flex;align-items:center;gap:8px;background:var(--s2);border:1px solid var(--border2);padding:6px 14px;border-radius:2px;font-family:var(--mono);font-size:10px;color:var(--green);margin-bottom:24px}}
.kpi-row{{display:flex;flex-wrap:wrap;gap:2px}}
.kpi{{background:var(--surface);border:1px solid var(--border);padding:12px 16px;flex:1;min-width:130px}}
.kpi-l{{font-family:var(--mono);font-size:8.5px;text-transform:uppercase;letter-spacing:.13em;color:var(--muted);margin-bottom:3px}}
.kpi-v{{font-family:var(--mono);font-size:16px;font-weight:500}}
.kpi-n{{font-size:9.5px;color:var(--muted);margin-top:2px}}
.r{{color:var(--red)}}.g{{color:var(--green)}}.go{{color:var(--gold)}}.b{{color:var(--blue)}}.muted{{color:var(--muted)}}
.wrap{{max-width:1300px;margin:0 auto;padding:0 16px}}
.sec{{display:flex;align-items:flex-end;gap:12px;padding:28px 0 8px;border-bottom:1px solid var(--border2)}}
.sec-n{{font-family:var(--mono);font-size:10px;color:var(--dim);letter-spacing:.1em}}
.sec h2{{font-family:var(--serif);font-size:20px;font-weight:700;color:#c8e0c8}}
.sec small{{font-family:var(--mono);font-size:9px;color:var(--muted);margin-left:auto;margin-bottom:2px}}
.tbl{{overflow-x:auto;border:1px solid var(--border);margin-top:0;margin-bottom:4px}}
table{{width:100%;border-collapse:collapse}}
thead th{{background:var(--s2);color:var(--muted);font-family:var(--mono);font-size:8.5px;font-weight:500;text-transform:uppercase;letter-spacing:.12em;padding:10px 13px;text-align:left;white-space:nowrap;border-bottom:1px solid var(--border2);border-right:1px solid var(--border)}}
thead th:last-child{{border-right:none}}
thead th.ra{{text-align:right}}
tbody td{{padding:0;border-bottom:1px solid var(--border);border-right:1px solid rgba(36,48,40,.5);vertical-align:top}}
tbody td:last-child{{border-right:none}}
tbody tr:last-child td{{border-bottom:none}}
tbody tr:hover td{{background:rgba(255,255,255,.015)}}
.c{{padding:12px 13px;height:100%}}
.c.ra{{text-align:right}}
.arow{{display:flex;align-items:center;gap:10px}}
.aico{{width:34px;height:34px;border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0}}
.aname{{font-family:var(--serif);font-size:13px;font-weight:700;color:#d8ead8}}
.asub{{font-family:var(--mono);font-size:8.5px;color:var(--muted);margin-top:1px}}
.pm{{font-family:var(--mono);font-size:14px;font-weight:500;line-height:1.1}}
.pn{{font-family:var(--mono);font-size:8.5px;color:var(--muted);margin-top:3px}}
.ps{{font-family:var(--mono);font-size:8px;color:var(--dim);margin-top:2px}}
.dabs{{font-family:var(--mono);font-size:10px;font-weight:500;margin-bottom:2px}}
.dpct{{font-family:var(--mono);font-size:14px;font-weight:700}}
.bar-bg{{width:52px;height:4px;background:var(--s3);border-radius:2px;overflow:hidden;margin-top:4px;margin-left:auto}}
.bar-f{{height:100%;border-radius:2px}}
.sig{{display:inline-block;font-family:var(--mono);font-size:8px;font-weight:500;padding:3px 10px;border-radius:2px;text-transform:uppercase;letter-spacing:.08em;white-space:nowrap}}
.s-str{{background:#142a1a;color:#50d08a;border:1px solid #1e5030}}
.s-buy{{background:var(--green-bg);color:var(--green);border:1px solid var(--green-mid)}}
.s-hld{{background:var(--gold-bg);color:var(--gold);border:1px solid #4a3810}}
.s-wtc{{background:var(--blue-bg);color:var(--blue);border:1px solid #1e3550}}
.s-avd{{background:var(--red-bg);color:var(--red);border:1px solid var(--red-mid)}}
.nt{{font-size:11px;color:#637a6a;line-height:1.75}}
.nt .hi{{color:var(--red);font-weight:500}}
.nt .pos{{color:var(--green);font-weight:500}}
.nt .gld{{color:var(--gold);font-weight:500}}
.rg{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px;margin:12px 0 28px}}
.rc{{background:var(--surface);border:1px solid var(--border);border-radius:3px;overflow:hidden;transition:transform .2s,border-color .2s}}
.rc:hover{{transform:translateY(-2px);border-color:var(--border2)}}
.rc-bar{{height:3px}}
.rb-s{{background:linear-gradient(90deg,#1a4a28,var(--green))}}
.rb-h{{background:linear-gradient(90deg,#4a3008,var(--gold))}}
.rb-a{{background:linear-gradient(90deg,#4a1008,var(--red))}}
.rb-w{{background:linear-gradient(90deg,#0a2040,var(--blue))}}
.rc-b{{padding:15px}}
.rc-top{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:3px}}
.rc-n{{font-family:var(--serif);font-size:14px;font-weight:700;color:#d8ead8}}
.rc-t{{font-family:var(--mono);font-size:8.5px;background:var(--s2);padding:2px 8px;border:1px solid var(--border2);color:var(--muted);border-radius:2px}}
.rc-c{{font-family:var(--mono);font-size:9px;color:var(--muted);margin-bottom:7px}}
.rc-st{{font-size:12px;color:var(--gold);letter-spacing:2px;margin-bottom:8px}}
.rc-tx{{font-size:11px;color:#5a786a;line-height:1.8;margin-bottom:10px}}
.rc-tx .hi{{color:var(--red);font-weight:500}}
.rc-tx .pos{{color:var(--green);font-weight:500}}
.rc-tx .gld{{color:var(--gold);font-weight:500}}
.rc-m{{display:flex;border-top:1px solid var(--border)}}
.rm{{flex:1;padding:9px 10px;text-align:center;border-right:1px solid var(--border)}}
.rm:last-child{{border-right:none}}
.rm-l{{font-family:var(--mono);font-size:8px;text-transform:uppercase;letter-spacing:.1em;color:var(--dim);margin-bottom:3px}}
.rm-v{{font-family:var(--mono);font-size:12px;font-weight:500}}
.footer{{max-width:1300px;margin:40px auto 0;padding:18px 16px;border-top:1px solid var(--border);font-family:var(--mono);font-size:9px;color:var(--dim);line-height:1.9}}
.footer .warn{{color:rgba(224,80,64,.7)}}
.sg{{display:grid;grid-template-columns:repeat(3,1fr);gap:2px;margin:8px 0 28px}}
.sc{{background:var(--surface);border:1px solid var(--border);padding:18px;position:relative;overflow:hidden}}
.sc::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px}}
.sc-g::before{{background:linear-gradient(90deg,#204030,var(--green))}}
.sc-y::before{{background:linear-gradient(90deg,#504010,var(--gold))}}
.sc-r::before{{background:linear-gradient(90deg,#502010,var(--red))}}
.sc-t{{font-family:var(--serif);font-size:16px;font-weight:700;margin-bottom:3px}}
.sc-p{{font-family:var(--mono);font-size:9px;color:var(--muted);margin-bottom:12px;letter-spacing:.06em}}
.sc-b{{font-size:11.5px;color:#5a786a;line-height:1.8}}
@media(max-width:768px){{header{{padding:24px 14px 20px}}.kpi{{min-width:100px;padding:10px 12px}}.kpi-v{{font-size:13px}}.sg{{grid-template-columns:1fr}}.rg{{grid-template-columns:1fr}}.wrap{{padding:0 10px}}}}
</style>
</head>
<body>

<header>
<div class="h-inner">
  <div class="war-chip"><div class="wd"></div>AUTO-UPDATE · GITHUB ACTIONS</div>
  <h1>全球市場 <em>戰前 vs 最新</em></h1>
  <div class="h-sub">以色列·伊朗戰爭 2026-02-28 基準 · GitHub Actions 每日自動更新 · 數據源：Yahoo Finance + CoinGecko</div>
  <div class="update-badge">⟳ 最後更新：{updated_at} · 每日 08:30 / 09:15 / 16:45 / 05:05 SGT 自動刷新（4次/日）</div>
  <div class="kpi-row">
    <div class="kpi">
      <div class="kpi-l">黃金 當前</div>
      <div class="kpi-v go">${fmt_price(g.get('price'))}</div>
      <div class="kpi-n">{fmt_pct(g.get('pct'))} vs 戰前 $5,230</div>
    </div>
    <div class="kpi">
      <div class="kpi-l">WTI 石油</div>
      <div class="kpi-v {'r' if (o.get('pct') or 0) > 0 else 'g'}">${fmt_price(o.get('price'))}</div>
      <div class="kpi-n">{fmt_pct(o.get('pct'))} vs 戰前 $63.80</div>
    </div>
    <div class="kpi">
      <div class="kpi-l">S&amp;P 500</div>
      <div class="kpi-v {'g' if (sp.get('pct') or 0) >= 0 else 'r'}">{fmt_price(sp.get('price'))}</div>
      <div class="kpi-n">{fmt_pct(sp.get('pct'))} vs 戰前 6,878</div>
    </div>
    <div class="kpi">
      <div class="kpi-l">Bitcoin BTC</div>
      <div class="kpi-v {'g' if (b.get('pct') or 0) >= 0 else 'r'}">${fmt_price(b.get('price'))}</div>
      <div class="kpi-n">{fmt_pct(b.get('pct'))} vs 戰前 $65,000</div>
    </div>
    <div class="kpi">
      <div class="kpi-l">台積電 TSMC</div>
      <div class="kpi-v {'g' if (ts.get('pct') or 0) >= 0 else 'r'}">TWD {fmt_price(ts.get('price'))}</div>
      <div class="kpi-n">{fmt_pct(ts.get('pct'))} vs ATH 2,025</div>
    </div>
    <div class="kpi">
      <div class="kpi-l">DBS 星展</div>
      <div class="kpi-v {'g' if (db.get('pct') or 0) >= 0 else 'r'}">SGD {fmt_price(db.get('price'))}</div>
      <div class="kpi-n">{fmt_pct(db.get('pct'))} vs 戰前 57.50</div>
    </div>
  </div>
</div>
</header>

<div class="wrap">

<!-- TABLE 1: COMMODITIES -->
<div class="sec">
  <span class="sec-n">§ 01</span>
  <h2>大宗商品 · 外匯 · 加密</h2>
  <small>Yahoo Finance + CoinGecko · 自動更新</small>
</div>
<div class="tbl">
<table>
  <thead><tr>
    <th style="min-width:155px">資產</th>
    <th class="ra" style="min-width:110px">戰前 02-27</th>
    <th class="ra" style="min-width:110px">最新價格</th>
    <th class="ra" style="min-width:75px">變幅</th>
    <th class="ra" style="min-width:62px">%</th>
    <th class="ra" style="min-width:76px">信號</th>
    <th style="min-width:200px">分析要點</th>
  </tr></thead>
  <tbody>
    {row("🥇","黃金 Gold","XAU/USD · GC=F","gold",
         extra_note="戰後峰值 $5,418（03-02 BullionVault）",
         analysis='戰後峰值 <span class="hi">$5,418</span>，JPMorgan 目標 <span class="pos">$6,300</span>。PBoC 連續 16 月購金，三重支撐（央行+地緣+弱美元）結構性牛市不變。')}
    {row("🛢","石油 WTI","CL=F · 近月合約","oil",
         extra_note="週漲35%創1983史上最大 · 峰值$119.94",
         analysis='霍爾木茲封閉影響全球 20% 石油供應。峰值 <span class="hi">$119.94</span>（FXDailyReport）。週漲 35% 創 1983 年期貨史上最大。Trump 停火訊號令油價回落。Goldman Sachs 極端情景 <span class="hi">$130+</span>。')}
    {row("💵","美元指數 DXY","DX-Y.NYB · USD Index","dxy",
         analysis='戰後避險買盤推升美元。高油價通脹長期侵蝕購買力。Fed 利率政策不確定性仍高。')}
    {row("₿","比特幣 Bitcoin","BTC/USD · CoinGecko","btc",
         extra_note="2月ATH $126K已腰斬 · ETF資金結構改變",
         analysis='2 月 ATH <span class="hi">$126,000</span> 後大幅回落。$90 億 BTC ETF 改變持倉結構，與宏觀資產相關性增加。Trump 停火訊號觸發反彈。非傳統避險資產。')}
  </tbody>
</table>
</div>

<!-- TABLE 2: INDICES -->
<div class="sec">
  <span class="sec-n">§ 02</span>
  <h2>全球股票指數</h2>
  <small>Yahoo Finance · 每日自動更新</small>
</div>
<div class="tbl">
<table>
  <thead><tr>
    <th style="min-width:155px">指數</th>
    <th class="ra" style="min-width:110px">戰前 02-27（已驗）</th>
    <th class="ra" style="min-width:110px">最新</th>
    <th class="ra" style="min-width:75px">變幅</th>
    <th class="ra" style="min-width:62px">%</th>
    <th class="ra" style="min-width:76px">信號</th>
    <th style="min-width:200px">分析</th>
  </tr></thead>
  <tbody>
    {row("🇺🇸","標普 500","^GSPC","sp500",
         analysis='02-27 精確值 <span class="gld">6,878.88</span>（CNBC）。VIX 偏高，Trump 停火訊號帶動反彈。歷史規律：地緣危機後 12 個月 S&P 平均上漲 11%。')}
    {row("💻","納斯達克綜合","^IXIC","nasdaq",
         analysis='02-27 精確值 <span class="gld">22,668.21</span>（CNBC）。盤中跌破 200 日均線後反彈。AI 長期結構性需求不變，短線波動大。')}
    {row("🇨🇳","上證綜合 SSE","000001.SS","sse",
         extra_note="02-27精確值：4,162.88（Yahoo驗證）",
         analysis='戰前精確值 <span class="gld">4,162.88</span>。北京 GDP 目標 4.5–5% 政策托底。中東能源依賴是主要外部風險。')}
    {row("🇭🇰","恒生指數 HSI","^HSI","hsi",
         extra_note="02-27精確值：26,630.54（Yahoo驗證）",
         analysis='戰前精確值 <span class="gld">26,630.54</span>。52 周高 27,381。跌幅遠優於日韓。TradingEconomics：早盤領漲科技股。低估值+政策托底。')}
    {row("🇸🇬","海峽時報指數 STI","^STI · SGX","sti",
         extra_note="02-27精確值：4,995.07 · ATH 5,041.33（02-23）",
         analysis='戰前精確值 <span class="gld">4,995.07</span>，ATH 5,041（02-23 TradingView）。三大銀行（DBS/OCBC/UOB）佔 STI ~50%，是主要支撐。')}
    {row("🇹🇼","台灣加權 TWII","^TWII · TWSE","twii",
         extra_note="⚠ 02-27精確值：35,414.49（非誤傳20,600）",
         analysis='<span class="hi">⚠</span> 戰前精確值 <span class="gld">35,414.49</span>（非誤傳的 20,600）。台積電 AI 熱潮推至歷史新高後回調。結構性 AI 需求完整，調整可視為佈局機會。')}
  </tbody>
</table>
</div>

<!-- TABLE 3: STOCKS -->
<div class="sec">
  <span class="sec-n">§ 03</span>
  <h2>個股 · 台積電 · 新航 · DBS</h2>
  <small>Yahoo Finance · SGX · 每日自動更新</small>
</div>
<div class="tbl">
<table>
  <thead><tr>
    <th style="min-width:155px">股票</th>
    <th class="ra">市場</th>
    <th class="ra" style="min-width:110px">戰前</th>
    <th class="ra" style="min-width:110px">最新</th>
    <th class="ra" style="min-width:75px">變幅</th>
    <th class="ra" style="min-width:62px">%</th>
    <th class="ra" style="min-width:76px">信號</th>
    <th class="ra" style="min-width:88px">分析師目標</th>
    <th style="min-width:185px">分析</th>
  </tr></thead>
  <tbody>
    {row("🇹🇼","台積電 TSMC","2330.TW · 台灣","tsmc",
         market_label="TWSE",target="TWD 2,290",analyst_note="31分析師共識 · +21%",
         extra_note="ATH TWD 2,025（02-25 TradingView）",
         analysis='ATH <span class="gld">TWD 2,025（02-25 TradingView）</span>。AI 需求獨立於戰爭，逢低佈局機會。目標 <span class="pos">+21%</span>。美國亞利桑那廠降低台海風險溢價。')}
    {row("✈️","新航 SIA","C6L.SI · SGX","sia",
         market_label="SGX",target="SGD 7.157",analyst_note="GrowBeanSprout · +9%",
         extra_note="中東航線停飛 · 燃油費暴漲+200%",
         analysis='中東航線停飛+噴射燃料暴漲 <span class="hi">+200%</span>（Rystad Energy）。雖分析師目標 $7.157，但燃油成本壓制淨利率，<span class="hi">停火前強烈迴避</span>。')}
    {row("🏦","DBS 星展","D05.SI · SGX","dbs",
         market_label="SGX",target="SGD 61.10",analyst_note="GrowBeanSprout · +10.5%",
         extra_note="ATH SGD 60.00（01-29 TradingView）· 股息率5.18%",
         analysis='ATH <span class="gld">SGD 60.00（01-29）</span>。股息率 5.18%，04-08 除息 SGD 0.81。目標 <span class="pos">+10.5%</span>。油價高位維持高利率，銀行淨息差受益。')}
  </tbody>
</table>
</div>

<!-- SCENARIOS -->
<div class="sec">
  <span class="sec-n">§ 04</span>
  <h2>戰爭情景分析</h2>
  <small>Goldman Sachs · JPMorgan · BlackRock · Wells Fargo</small>
</div>
<div class="sg">
  <div class="sc sc-g">
    <div class="sc-t" style="color:var(--green)">🟢 牛市 · 快速停火</div>
    <div class="sc-p">概率 ~20%</div>
    <div class="sc-b">WTI 回落 $70–80，科技/航空/加密大幅反彈。台積電重測 ATH。黃金回調但結構牛市不變。SIA 回升 SGD 7+。BTC 重返 $80K+。</div>
  </div>
  <div class="sc sc-y">
    <div class="sc-t" style="color:var(--gold)">🟡 基準 · 持續震盪</div>
    <div class="sc-p">概率 ~50% · 2–4 月區域衝突</div>
    <div class="sc-b">WTI 維持 $80–100。黃金 $5,000–5,500（JPM 目標 $6,300 年底）。S&P 在 6,500–7,000 整固。台積電 AI 需求強，DBS 股息吸引力維持。</div>
  </div>
  <div class="sc sc-r">
    <div class="sc-t" style="color:var(--red)">🔴 熊市 · 全面升級</div>
    <div class="sc-p">概率 ~30% · 卡達/沙烏地波及</div>
    <div class="sc-b">WTI 測試 $130+（Goldman）。黃金 $6,000+（JPM 極端）。通脹失控，Fed 加息，S&P 跌破 6,000。BTC 可能再測 $47,000。</div>
  </div>
</div>

<!-- RECOMMENDATIONS -->
<div class="sec">
  <span class="sec-n">§ 05</span>
  <h2>投資標的建議</h2>
  <small>基於當前戰時環境 · 僅供參考，非投資建議</small>
</div>
<div class="rg">
  <div class="rc"><div class="rc-bar rb-s"></div><div class="rc-b">
    <div class="rc-top"><div class="rc-n">🥇 黃金 / ETF</div><span class="rc-t">GLD · IAU</span></div>
    <div class="rc-c">大宗商品 · 戰時首選 #1</div>
    <div class="rc-st">★★★★★</div>
    <div class="rc-tx">目前 <strong style="color:var(--gold)">${fmt_price(g.get('price'))}</strong>，較戰前 {fmt_pct(g.get('pct'))}。JPMorgan 目標 <span class="pos">$6,300（+{round((6300/(g.get('price') or 5099)-1)*100,1)}%）</span>。PBoC 央行持續購金，結構性牛市。</div>
    <div class="rc-m">
      <div class="rm"><div class="rm-l">當前</div><div class="rm-v go">${fmt_price(g.get('price'))}</div></div>
      <div class="rm"><div class="rm-l">JPM目標</div><div class="rm-v g">$6,300</div></div>
      <div class="rm"><div class="rm-l">上行</div><div class="rm-v g">+{round((6300/(g.get('price') or 5099)-1)*100,1)}%</div></div>
    </div>
  </div></div>

  <div class="rc"><div class="rc-bar rb-s"></div><div class="rc-b">
    <div class="rc-top"><div class="rc-n">🛢 能源股 ETF</div><span class="rc-t">XLE · CVX · XOM</span></div>
    <div class="rc-c">美股能源 · 戰爭最直接受益</div>
    <div class="rc-st">★★★★☆</div>
    <div class="rc-tx">WTI 當前 <strong style="color:var(--red)">${fmt_price(o.get('price'))}</strong>，戰後漲幅 {fmt_pct(o.get('pct'))}。峰值 $119.94。<span class="hi">停火後急跌風險</span>，必須設好止損。</div>
    <div class="rc-m">
      <div class="rm"><div class="rm-l">WTI當前</div><div class="rm-v r">${fmt_price(o.get('price'))}</div></div>
      <div class="rm"><div class="rm-l">峰值</div><div class="rm-v r">$119.94</div></div>
      <div class="rm"><div class="rm-l">風險</div><div class="rm-v r">停戰急跌</div></div>
    </div>
  </div></div>

  <div class="rc"><div class="rc-bar rb-s"></div><div class="rc-b">
    <div class="rc-top"><div class="rc-n">🇹🇼 台積電 TSMC</div><span class="rc-t">2330.TW · TSM</span></div>
    <div class="rc-c">AI 結構性龍頭 · 戰略重倉</div>
    <div class="rc-st">★★★★★</div>
    <div class="rc-tx">當前 <strong style="color:{'var(--green)' if (ts.get('pct') or 0) >= 0 else 'var(--red)'}">TWD {fmt_price(ts.get('price'))}</strong>（{fmt_pct(ts.get('pct'))} vs ATH 2,025）。31 分析師目標 <span class="pos">2,290（+{round((2290/(ts.get('price') or 1890)-1)*100,1)}%）</span>。</div>
    <div class="rc-m">
      <div class="rm"><div class="rm-l">當前(TWD)</div><div class="rm-v">{fmt_price(ts.get('price'))}</div></div>
      <div class="rm"><div class="rm-l">目標</div><div class="rm-v g">2,290</div></div>
      <div class="rm"><div class="rm-l">上行</div><div class="rm-v g">+{round((2290/(ts.get('price') or 1890)-1)*100,1)}%</div></div>
    </div>
  </div></div>

  <div class="rc"><div class="rc-bar rb-s"></div><div class="rc-b">
    <div class="rc-top"><div class="rc-n">🏦 DBS 星展銀行</div><span class="rc-t">D05.SI · SGX</span></div>
    <div class="rc-c">高股息 · 超賣逢低</div>
    <div class="rc-st">★★★★☆</div>
    <div class="rc-tx">當前 <strong style="color:{'var(--green)' if (db.get('pct') or 0) >= 0 else 'var(--red)'}">SGD {fmt_price(db.get('price'))}</strong>。目標 <span class="pos">SGD 61.10（+{round((61.10/(db.get('price') or 55)-1)*100,1)}%）</span>。股息率 5.18%，04-08 除息 SGD 0.81。</div>
    <div class="rc-m">
      <div class="rm"><div class="rm-l">當前(SGD)</div><div class="rm-v">{fmt_price(db.get('price'))}</div></div>
      <div class="rm"><div class="rm-l">目標</div><div class="rm-v g">61.10</div></div>
      <div class="rm"><div class="rm-l">股息率</div><div class="rm-v g">5.18%</div></div>
    </div>
  </div></div>

  <div class="rc"><div class="rc-bar rb-h"></div><div class="rc-b">
    <div class="rc-top"><div class="rc-n">🛡 國防科技</div><span class="rc-t">LMT · ITA ETF</span></div>
    <div class="rc-c">戰爭政策直接受益</div>
    <div class="rc-st">★★★☆☆</div>
    <div class="rc-tx">LMT 戰後首日升至 5 年高位 <span class="pos">$702（+3.37%）</span>。建議以 <span class="pos">ITA ETF</span> 分散佈局。停戰後快速反轉風險高，不宜重倉。</div>
    <div class="rc-m">
      <div class="rm"><div class="rm-l">LMT首日</div><div class="rm-v g">+3.37%</div></div>
      <div class="rm"><div class="rm-l">建議</div><div class="rm-v b">ITA ETF</div></div>
      <div class="rm"><div class="rm-l">風險</div><div class="rm-v r">停戰反轉</div></div>
    </div>
  </div></div>

  <div class="rc"><div class="rc-bar rb-a"></div><div class="rc-b">
    <div class="rc-top"><div class="rc-n">✈️ 新航 SIA</div><span class="rc-t">C6L.SI · SGX</span></div>
    <div class="rc-c">⚠ 強烈回避</div>
    <div class="rc-st" style="color:var(--red)">★☆☆☆☆</div>
    <div class="rc-tx">當前 <strong style="color:var(--red)">SGD {fmt_price(si.get('price'))}</strong>（{fmt_pct(si.get('pct'))} vs 戰前）。中東航線停飛 + 燃油 <span class="hi">+200%</span>。停火前強烈迴避。</div>
    <div class="rc-m">
      <div class="rm"><div class="rm-l">當前(SGD)</div><div class="rm-v r">{fmt_price(si.get('price'))}</div></div>
      <div class="rm"><div class="rm-l">跌幅</div><div class="rm-v r">{fmt_pct(si.get('pct'))}</div></div>
      <div class="rm"><div class="rm-l">燃油漲</div><div class="rm-v r">+200%</div></div>
    </div>
  </div></div>
</div>

</div><!-- /wrap -->

<div class="footer">
  <strong>數據來源：</strong>Yahoo Finance (yfinance) · CoinGecko (BTC) · 戰前基準：FXDailyReport · Bitget/Intellectia · CNBC · Yahoo Finance · TradingView ·
  戰前基準數據（02-27）已人工驗證，不參與自動更新。最新價格每日 4 次自動更新（SGT 08:30 / 09:15 / 16:45 / 05:05，工作日）。<br>
  <span class="warn">⚠ 本報告不構成任何投資建議。投資涉及風險，過去表現不代表未來結果。請諮詢持牌專業財務顧問。</span>
</div>

</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("✅ index.html regenerated successfully!")
print(f"   Updated at: {updated_at}")
