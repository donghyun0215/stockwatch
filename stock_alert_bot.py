#!/usr/bin/env python3
"""
Stock Price Alert Telegram Bot
- Watch multiple stocks
- Upper and lower price alerts
- Cooldown to prevent spam
- Set alerts via Telegram commands: /alert TSLA 200 below
"""

import os
import time
import json
import logging
import threading
from datetime import datetime, timedelta

import requests
import yfinance as yf

# ── Config ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8890627010:AAHCrKTRatarhddvhph7nvGmfJTLnK3gaag")
CHAT_ID        = os.getenv("TELEGRAM_CHAT_ID",   "1281048247")
CHECK_INTERVAL = 60          # seconds between price checks
COOLDOWN_MINS  = 30          # minutes before re-alerting same ticker+direction
ALERTS_FILE    = "alerts.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Persistence ───────────────────────────────────────────────────────────────
def load_alerts() -> dict:
    if os.path.exists(ALERTS_FILE):
        with open(ALERTS_FILE) as f:
            return json.load(f)
    return {}   # { "AAPL": [{"type": "below", "price": 180, "last_fired": null}, ...] }

def save_alerts(alerts: dict):
    with open(ALERTS_FILE, "w") as f:
        json.dump(alerts, f, indent=2)

alerts: dict = load_alerts()
cooldowns: dict = {}   # key = "TICKER-direction-price" → datetime last fired

# ── Telegram helpers ───────────────────────────────────────────────────────────
def tg_send(text: str, chat_id: str = CHAT_ID):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
        r.raise_for_status()
    except Exception as e:
        log.error("Telegram send failed: %s", e)

def tg_get_updates(offset: int = 0):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    try:
        r = requests.get(url, params={"offset": offset, "timeout": 30}, timeout=35)
        r.raise_for_status()
        return r.json().get("result", [])
    except Exception as e:
        log.error("getUpdates failed: %s", e)
        return []

# ── Price fetching ─────────────────────────────────────────────────────────────
def get_price(ticker: str) -> float | None:
    try:
        info = yf.Ticker(ticker).fast_info
        price = info.get("last_price") or info.get("regularMarketPrice")
        return float(price) if price else None
    except Exception as e:
        log.warning("Price fetch failed for %s: %s", ticker, e)
        return None

# ── Alert checking ─────────────────────────────────────────────────────────────
def check_all_alerts():
    if not alerts:
        return
    for ticker, rules in list(alerts.items()):
        price = get_price(ticker)
        if price is None:
            log.warning("Could not get price for %s", ticker)
            continue
        log.info("%-6s  $%.2f", ticker, price)
        for rule in rules:
            direction = rule["type"]   # "below" or "above"
            threshold = rule["price"]
            cd_key    = f"{ticker}-{direction}-{threshold}"

            triggered = (direction == "below" and price <= threshold) or \
                        (direction == "above" and price >= threshold)

            if triggered:
                last = cooldowns.get(cd_key)
                if last and datetime.now() - last < timedelta(minutes=COOLDOWN_MINS):
                    continue   # still in cooldown
                cooldowns[cd_key] = datetime.now()
                emoji = "📉" if direction == "below" else "📈"
                msg = (
                    f"{emoji} *ALERT: {ticker}*\n"
                    f"Price: *${price:.2f}*\n"
                    f"Trigger: {direction} ${threshold:.2f}\n"
                    f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
                tg_send(msg)
                log.info("ALERT SENT  %s %s $%.2f (price $%.2f)", ticker, direction, threshold, price)

# ── Command handling ───────────────────────────────────────────────────────────
HELP_TEXT = """
📊 *Stock Alert Bot Commands*

*/alert TICKER PRICE [above|below]*
  Add a price alert.  Default direction is *below*.
  Example: `/alert AAPL 180 below`
  Example: `/alert TSLA 300 above`

*/remove TICKER PRICE [above|below]*
  Remove an existing alert.
  Example: `/remove AAPL 180 below`

*/list*
  Show all active alerts with current prices.

*/price TICKER*
  Get the current price of a stock.

*/help*
  Show this message.
"""

def handle_command(text: str, chat_id: str):
    parts = text.strip().split()
    cmd   = parts[0].lower().lstrip("/")

    if cmd == "help":
        tg_send(HELP_TEXT, chat_id)

    elif cmd == "price":
        if len(parts) < 2:
            tg_send("Usage: `/price TICKER`", chat_id); return
        ticker = parts[1].upper()
        price  = get_price(ticker)
        if price:
            tg_send(f"💰 *{ticker}*: ${price:.2f}", chat_id)
        else:
            tg_send(f"❌ Could not fetch price for `{ticker}`. Check the ticker symbol.", chat_id)

    elif cmd == "alert":
        if len(parts) < 3:
            tg_send("Usage: `/alert TICKER PRICE [above|below]`", chat_id); return
        ticker    = parts[1].upper()
        try:
            threshold = float(parts[2])
        except ValueError:
            tg_send("❌ Invalid price. Example: `/alert AAPL 180 below`", chat_id); return
        direction = parts[3].lower() if len(parts) >= 4 else "below"
        if direction not in ("above", "below"):
            tg_send("❌ Direction must be `above` or `below`.", chat_id); return

        # Validate ticker
        price = get_price(ticker)
        if price is None:
            tg_send(f"❌ Ticker `{ticker}` not found.", chat_id); return

        if ticker not in alerts:
            alerts[ticker] = []
        # avoid duplicates
        for r in alerts[ticker]:
            if r["type"] == direction and r["price"] == threshold:
                tg_send(f"⚠️ Alert already exists for {ticker} {direction} ${threshold:.2f}", chat_id); return
        alerts[ticker].append({"type": direction, "price": threshold})
        save_alerts(alerts)
        emoji = "📉" if direction == "below" else "📈"
        tg_send(
            f"✅ Alert set!\n{emoji} *{ticker}* {direction} *${threshold:.2f}*\nCurrent price: ${price:.2f}",
            chat_id
        )
        log.info("Alert added: %s %s $%.2f", ticker, direction, threshold)

    elif cmd == "remove":
        if len(parts) < 3:
            tg_send("Usage: `/remove TICKER PRICE [above|below]`", chat_id); return
        ticker    = parts[1].upper()
        try:
            threshold = float(parts[2])
        except ValueError:
            tg_send("❌ Invalid price.", chat_id); return
        direction = parts[3].lower() if len(parts) >= 4 else "below"

        if ticker in alerts:
            before = len(alerts[ticker])
            alerts[ticker] = [r for r in alerts[ticker]
                               if not (r["type"] == direction and r["price"] == threshold)]
            if not alerts[ticker]:
                del alerts[ticker]
            save_alerts(alerts)
            if len(alerts.get(ticker, [])) < before or ticker not in alerts:
                tg_send(f"🗑️ Removed alert: *{ticker}* {direction} ${threshold:.2f}", chat_id)
                return
        tg_send(f"⚠️ No matching alert found for {ticker} {direction} ${threshold:.2f}", chat_id)

    elif cmd == "list":
        if not alerts:
            tg_send("📭 No active alerts.", chat_id); return
        lines = ["📋 *Active Alerts*\n"]
        for ticker, rules in alerts.items():
            price = get_price(ticker)
            price_str = f"(now ${price:.2f})" if price else ""
            for r in rules:
                emoji = "📉" if r["type"] == "below" else "📈"
                lines.append(f"{emoji} *{ticker}* {r['type']} ${r['price']:.2f} {price_str}")
        tg_send("\n".join(lines), chat_id)

    else:
        tg_send(f"❓ Unknown command `/{cmd}`. Try /help", chat_id)

# ── Long-poll loop ─────────────────────────────────────────────────────────────
def command_listener():
    log.info("Command listener started")
    offset = 0
    while True:
        updates = tg_get_updates(offset)
        for upd in updates:
            offset = upd["update_id"] + 1
            msg = upd.get("message", {})
            text = msg.get("text", "")
            chat_id = str(msg.get("chat", {}).get("id", CHAT_ID))
            if text.startswith("/"):
                log.info("CMD from %s: %s", chat_id, text)
                handle_command(text, chat_id)

# ── Price-check loop ───────────────────────────────────────────────────────────
def price_checker():
    log.info("Price checker started (interval: %ds)", CHECK_INTERVAL)
    while True:
        check_all_alerts()
        time.sleep(CHECK_INTERVAL)

# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("🚀 Stock Alert Bot starting...")
    tg_send(
        "🤖 *Stock Alert Bot is online!*\n"
        "Send /help to see available commands.\n"
        f"Checking prices every {CHECK_INTERVAL}s with {COOLDOWN_MINS}min cooldown."
    )

    t1 = threading.Thread(target=command_listener, daemon=True)
    t2 = threading.Thread(target=price_checker,    daemon=True)
    t1.start()
    t2.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Bot stopped.")
