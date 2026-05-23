# 📈 Stock Price Alert Telegram Bot

A Python bot that watches stock prices and sends you Telegram alerts.

## Features
- 📉📈 Upper **and** lower price alerts
- 🔕 Cooldown (30 min default) to prevent spam
- 📊 Watch **multiple stocks** simultaneously
- 💬 Control everything via **Telegram commands**
- 💾 Alerts persist across restarts (`alerts.json`)

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set your credentials (optional — already embedded)
```bash
export TELEGRAM_BOT_TOKEN="your_token_here"
export TELEGRAM_CHAT_ID="your_chat_id_here"
```

### 3. Run the bot
```bash
python stock_alert_bot.py
```

---

## Telegram Commands

| Command | Description |
|---|---|
| `/alert AAPL 180 below` | Alert when AAPL drops below $180 |
| `/alert TSLA 300 above` | Alert when TSLA rises above $300 |
| `/remove AAPL 180 below` | Remove that alert |
| `/list` | Show all active alerts + current prices |
| `/price AAPL` | Get current price of any stock |
| `/help` | Show all commands |

---

## Run 24/7 (Recommended)

### Option A: Run as a background process (Linux/Mac)
```bash
nohup python stock_alert_bot.py > bot.log 2>&1 &
```
Check logs: `tail -f bot.log`
Stop it: `kill $(pgrep -f stock_alert_bot.py)`

### Option B: systemd service (Linux)
Create `/etc/systemd/system/stockbot.service`:
```ini
[Unit]
Description=Stock Alert Telegram Bot
After=network.target

[Service]
ExecStart=/usr/bin/python3 /path/to/stock_alert_bot.py
Restart=always
Environment=TELEGRAM_BOT_TOKEN=your_token
Environment=TELEGRAM_CHAT_ID=your_chat_id

[Install]
WantedBy=multi-user.target
```
Then:
```bash
sudo systemctl enable stockbot
sudo systemctl start stockbot
```

### Option C: Deploy free to Railway
1. Go to https://railway.app
2. New Project → Deploy from GitHub repo
3. Add env vars `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
4. Done — runs 24/7 free

---

## Configuration (edit top of script)
| Variable | Default | Description |
|---|---|---|
| `CHECK_INTERVAL` | `60` | Seconds between price checks |
| `COOLDOWN_MINS` | `30` | Minutes before re-alerting same alert |
