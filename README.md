# Gold Rate Notifications

A daily Telegram notification service that sends live 22K & 24K gold prices for the **USA** and **Telangana (India)**, with trend analysis and a price estimate for the next day.

## What you get

Two notifications per day — once at your morning (PST) and once at India's morning (IST):

```
🥇 Good morning! Gold rates — Apr 14, 2026

1 oz (USD): $4,765.19
  Daily  : ▼ -$23.10 (-0.48%)
  Weekly : ▲ +$112.40 (+2.42%)

🇺🇸 USA (per gram)
  22K → $140.44
  24K → $153.20

🇮🇳 Telangana (per gram)
  22K → ₹14,110.00 — Lalithaa Jewellery
  24K → ₹14,284.60 — spot

📊 Trend Signal
  Direction  : ▼ Bearish
  Est. tomorrow : $4,778 – $4,912 /oz
  Based on 14‑day price trend · not financial advice

⏰ 08:00 AM PST | 09:30 PM IST
```

## Data sources

| Data | Source |
|---|---|
| 22K Telangana | [Lalithaa Jewellery](https://www.lalithaajewellery.com/) — their actual published rate |
| 24K Telangana | goldprice.org live INR spot price |
| USA (22K & 24K) | goldprice.org live USD spot price |
| Trend / history | Yahoo Finance (GC=F) — auto-seeded on first run |

## Features

- Live gold prices for USA and Telangana (Hyderabad)
- 22K from Lalithaa Jewellery's own API — the exact rate they publish
- Daily & weekly change with direction arrows
- Trend signal (Bullish / Bearish / Neutral) based on 7-day vs 30-day moving average
- Tomorrow's estimated price range using 14-day linear regression + volatility
- Scheduled via macOS launchd — runs automatically, no terminal needed
- Price history cached locally in `prices.json` (90 days), auto-seeded on first run

## Requirements

- macOS (uses launchd for scheduling)
- Python 3.11+
- A Telegram bot

## Setup

### 1. Create a Telegram bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the **bot token** you receive
4. Search for your new bot, tap **Start**, send it any message
5. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in your browser
6. Find `result[0].message.chat.id` — that's your **chat ID**

### 2. Configure credentials

```bash
cp .env.example .env
```

Edit `.env`:

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 3. Run setup

```bash
bash setup.sh
```

This will:
- Create a Python virtual environment and install dependencies
- Send a **test notification** to your Telegram
- Install two launchd jobs to run automatically every day

## Schedule

| Time | Notification |
|---|---|
| **8:00 AM PST** | Good morning (US) |
| **6:30 PM PST** | Good morning India (≈ 8:00 AM IST) |

## Useful commands

```bash
# Send notification manually
./venv/bin/python notify.py

# Watch live logs
tail -f notify.log

# Disable US morning job
launchctl unload ~/Library/LaunchAgents/com.goldrate.notify.us.plist

# Disable India morning job
launchctl unload ~/Library/LaunchAgents/com.goldrate.notify.india.plist

# Re-enable a job
launchctl load ~/Library/LaunchAgents/com.goldrate.notify.us.plist
```

## Project structure

```
GoldRate-Notifications/
├── notify.py        # Main script — fetches prices, computes trend, sends Telegram
├── setup.sh         # One-time setup: venv, test run, launchd install
├── requirements.txt # Python dependencies
├── .env             # Credentials (not committed)
├── .env.example     # Credentials template
├── prices.json      # Local price history cache (auto-created)
└── notify.log       # Run logs (auto-created)
```

## How the trend predictor works

On first run, 45+ days of historical gold prices are automatically fetched from Yahoo Finance (GC=F) to seed the local cache. After that, each daily run appends the current price.

The trend signal uses:
- **Direction** — 7-day moving average vs 30-day moving average crossover
- **Tomorrow's range** — linear regression on the last 14 days of prices, ± average daily volatility

> The estimate is a trend-based projection, not a financial forecast. Gold prices are heavily influenced by macroeconomic events no model can predict.

## Dependencies

```
requests
pytz
python-dotenv
```
