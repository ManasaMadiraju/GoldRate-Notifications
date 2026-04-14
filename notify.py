#!/usr/bin/env python3
"""
Gold Rate Notification Service
Sends 22K & 24K gold prices for USA and Telangana (Lalithaa Jewellery) via Telegram.
Includes trend signal with daily/weekly change and tomorrow's price estimate.

Run twice daily:
  - 8:00 AM PST  → US morning
  - 6:30 PM PST  → India morning (≈ 8:00 AM IST in standard time)
"""

import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
import pytz
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TROY_OZ_TO_GRAM = 31.1035
TELANGANA_STATE_ID = "2ce06e73-3310-4ea1-9c4d-fd707e4e5efd"
CACHE_FILE = Path(__file__).parent / "prices.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


# ── Data fetching ─────────────────────────────────────────────────────────────

def fetch_usd_spot() -> dict:
    r = requests.get(
        "https://data-asg.goldprice.org/dbXRates/USD",
        headers={**HEADERS, "Referer": "https://goldprice.org/"},
        timeout=15,
    )
    r.raise_for_status()
    per_oz = r.json()["items"][0]["xauPrice"]
    per_gram = per_oz / TROY_OZ_TO_GRAM
    return {
        "per_oz": round(per_oz, 2),
        "24K": round(per_gram, 2),
        "22K": round(per_gram * 22 / 24, 2),
    }


def fetch_inr_spot_24k() -> float:
    r = requests.get(
        "https://data-asg.goldprice.org/dbXRates/INR",
        headers={**HEADERS, "Referer": "https://goldprice.org/"},
        timeout=15,
    )
    r.raise_for_status()
    return round(r.json()["items"][0]["xauPrice"] / TROY_OZ_TO_GRAM, 2)


def fetch_lalithaa_22k() -> float:
    r = requests.get(
        f"https://api.lalithaajewellery.com/public/pricings/latest?state_id={TELANGANA_STATE_ID}",
        headers={**HEADERS, "Referer": "https://www.lalithaajewellery.com/", "Origin": "https://www.lalithaajewellery.com"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["data"]["prices"]["gold"]["price"]


# ── Historical data (seed) ────────────────────────────────────────────────────

def fetch_yahoo_history(days: int = 60) -> list[dict]:
    """Fetch historical daily gold prices (per oz USD) from Yahoo Finance GC=F."""
    end = int(datetime.utcnow().timestamp())
    start = int((datetime.utcnow() - timedelta(days=days + 5)).timestamp())
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/GC=F?period1={start}&period2={end}&interval=1d"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    r.raise_for_status()
    result = r.json()["chart"]["result"][0]
    timestamps = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]
    entries = []
    for ts, price in zip(timestamps, closes):
        if price is None:
            continue
        date = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
        entries.append({"date": date, "usd_per_oz": round(price, 2)})
    return sorted(entries, key=lambda e: e["date"])


# ── Cache ─────────────────────────────────────────────────────────────────────

def load_cache() -> list:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return []


def save_cache(history: list):
    # Deduplicate by date (keep latest entry per date), sort, keep 90 days
    by_date = {}
    for e in history:
        by_date[e["date"]] = e
    cutoff = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")
    cleaned = sorted([e for e in by_date.values() if e["date"] >= cutoff], key=lambda e: e["date"])
    CACHE_FILE.write_text(json.dumps(cleaned, indent=2))


def ensure_seeded(history: list) -> list:
    """If we have fewer than 30 days of history, seed from Yahoo Finance."""
    if len(history) >= 30:
        return history
    print("  [INFO] Seeding price history from Yahoo Finance...")
    yahoo = fetch_yahoo_history(60)
    merged = {e["date"]: e for e in history}
    for e in yahoo:
        if e["date"] not in merged:
            merged[e["date"]] = e
    result = sorted(merged.values(), key=lambda e: e["date"])
    save_cache(result)
    print(f"  [INFO] Cache seeded with {len(result)} days of data.")
    return result


def closest_entry(history: list, days_ago: int) -> dict | None:
    """Find cached entry closest to N days ago (within ±3 days)."""
    target = datetime.utcnow() - timedelta(days=days_ago)
    best, best_diff = None, float("inf")
    for e in history:
        d = datetime.strptime(e["date"], "%Y-%m-%d")
        diff = abs((d - target).days)
        if diff < best_diff and diff <= 3:
            best, best_diff = e, diff
    return best


# ── Trend analysis ────────────────────────────────────────────────────────────

def moving_average(prices: list[float], n: int) -> float | None:
    if len(prices) < n:
        return None
    return sum(prices[-n:]) / n


def linear_regression(prices: list[float]) -> tuple[float, float]:
    """Returns (slope_per_day, tomorrow_estimate) using simple linear regression."""
    n = len(prices)
    xs = list(range(n))
    sum_x = sum(xs)
    sum_y = sum(prices)
    sum_xy = sum(x * y for x, y in zip(xs, prices))
    sum_x2 = sum(x * x for x in xs)
    denom = n * sum_x2 - sum_x ** 2
    if denom == 0:
        return 0.0, prices[-1]
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    tomorrow = slope * n + intercept
    return slope, round(tomorrow, 2)


def avg_daily_volatility(prices: list[float]) -> float:
    if len(prices) < 2:
        return 0.0
    return sum(abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))) / (len(prices) - 1)


def build_trend_signal(history: list, current_oz: float) -> dict:
    """Compute all trend metrics from price history."""
    prices = [e["usd_per_oz"] for e in history] + [current_oz]

    ma7 = moving_average(prices, 7)
    ma30 = moving_average(prices, 30)

    prev_day = closest_entry(history, 1)
    prev_week = closest_entry(history, 7)

    day_change = day_pct = None
    if prev_day:
        day_change = current_oz - prev_day["usd_per_oz"]
        day_pct = (day_change / prev_day["usd_per_oz"]) * 100

    week_change = week_pct = None
    if prev_week:
        week_change = current_oz - prev_week["usd_per_oz"]
        week_pct = (week_change / prev_week["usd_per_oz"]) * 100

    # Use last 14 days + today for regression
    recent = [e["usd_per_oz"] for e in history[-14:]] + [current_oz]
    slope, tomorrow_est = linear_regression(recent)
    volatility = avg_daily_volatility(recent)

    # Trend direction from MA crossover
    if ma7 and ma30:
        if ma7 > ma30 * 1.001:
            direction, signal = "Bullish", "▲"
        elif ma7 < ma30 * 0.999:
            direction, signal = "Bearish", "▼"
        else:
            direction, signal = "Neutral", "→"
    else:
        direction, signal = "N/A (building history)", "–"

    return {
        "direction": direction,
        "signal": signal,
        "ma7": ma7,
        "ma30": ma30,
        "day_change": day_change,
        "day_pct": day_pct,
        "week_change": week_change,
        "week_pct": week_pct,
        "tomorrow_low": round(tomorrow_est - volatility, 2),
        "tomorrow_high": round(tomorrow_est + volatility, 2),
        "tomorrow_est": tomorrow_est,
    }


# ── Message formatting ────────────────────────────────────────────────────────

def _chg(change: float | None, pct: float | None, symbol: str = "") -> str:
    if change is None:
        return "_no prior data_"
    arrow = "▲" if change >= 0 else "▼"
    sign = "+" if change >= 0 else ""
    return f"{arrow} {sign}{symbol}{change:,.2f} ({sign}{pct:.2f}%)"


def format_message(usd: dict, inr_22k: float, inr_24k: float, trend: dict) -> str:
    pst = pytz.timezone("America/Los_Angeles")
    ist = pytz.timezone("Asia/Kolkata")
    now_pst = datetime.now(pst)
    now_ist = datetime.now(ist)

    pst_hour = now_pst.hour
    if 6 <= pst_hour < 14:
        greeting = f"Good morning! Gold rates \u2014 {now_pst.strftime('%b %d, %Y')}"
    else:
        greeting = f"Good morning India! Gold rates \u2014 {now_ist.strftime('%b %d, %Y')}"

    lines = [
        f"*\U0001f947 {greeting}*",
        "",
        f"*1 oz (USD):* `${usd['per_oz']:,.2f}`",
        f"  Daily  : {_chg(trend['day_change'], trend['day_pct'], '$')}",
        f"  Weekly : {_chg(trend['week_change'], trend['week_pct'], '$')}",
        "",
        f"\U0001f1fa\U0001f1f8 *USA* (per gram)",
        f"  22K \u2192 `${usd['22K']:.2f}`",
        f"  24K \u2192 `${usd['24K']:.2f}`",
        "",
        f"\U0001f1ee\U0001f1f3 *Telangana* (per gram)",
        f"  22K \u2192 `\u20b9{inr_22k:,.2f}` _\u2014 Lalithaa Jewellery_",
        f"  24K \u2192 `\u20b9{inr_24k:,.2f}` _\u2014 spot_",
        "",
        f"\U0001f4ca *Trend Signal*",
        f"  Direction : {trend['signal']} {trend['direction']}",
        f"  Est. tomorrow : `${trend['tomorrow_low']:,.0f} \u2013 ${trend['tomorrow_high']:,.0f}` /oz",
        f"  _Based on 14\u2011day price trend \u00b7 not financial advice_",
        "",
        f"\u23f0 {now_pst.strftime('%I:%M %p')} PST  |  {now_ist.strftime('%I:%M %p')} IST",
    ]
    return "\n".join(lines)


# ── Telegram ──────────────────────────────────────────────────────────────────

def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env")
    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fetching gold prices...")

    usd = fetch_usd_spot()
    inr_22k = fetch_lalithaa_22k()
    inr_24k = fetch_inr_spot_24k()

    print(f"  1 oz      — ${usd['per_oz']:,}")
    print(f"  USA       — 22K: ${usd['22K']}, 24K: ${usd['24K']}")
    print(f"  Telangana — 22K: \u20b9{inr_22k:,}, 24K: \u20b9{inr_24k:,}")

    history = load_cache()
    history = ensure_seeded(history)

    trend = build_trend_signal(history, usd["per_oz"])
    print(f"  Trend     — {trend['signal']} {trend['direction']}, est. ${trend['tomorrow_low']:,}–${trend['tomorrow_high']:,}/oz tomorrow")

    message = format_message(usd, inr_22k, inr_24k, trend)

    # Append today's price to cache (once per day)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if not any(e["date"] == today for e in history):
        history.append({"date": today, "usd_per_oz": usd["per_oz"]})
        save_cache(history)

    result = send_telegram(message)
    print(f"  Telegram message sent (id={result['result']['message_id']})")


if __name__ == "__main__":
    main()
