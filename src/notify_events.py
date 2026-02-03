import sqlite3
from pathlib import Path
import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# --------------------------------------------------
# ENV
# --------------------------------------------------
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError("Telegram credentials missing")

CHAT_ID = int(CHAT_ID)

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "db" / "uniqlo.sqlite"

LOOKBACK_MINUTES = 35   # slightly > scraper interval
DRY_RUN = False         # set True to test locally

# --------------------------------------------------
# TELEGRAM
# --------------------------------------------------
def send_telegram_message(text: str):
    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "disable_web_page_preview": True
        },
        timeout=10
    )
    r.raise_for_status()

# --------------------------------------------------
# MAIN
# --------------------------------------------------
def main():
    since = (datetime.utcnow() - timedelta(minutes=LOOKBACK_MINUTES)).isoformat()

    conn = sqlite3.connect(DB_PATH)

    events = conn.execute("""
        SELECT event_time, catalog, event_type, event_value
        FROM uniqlo_events
        WHERE event_time >= ?
        ORDER BY event_time ASC
    """, (since,)).fetchall()

    conn.close()

    if not events:
        print("No new events to notify.")
        return

    for event_time, catalog, event_type, event_value in events:
        text = (
            "🆕 UNIQLO SALE UPDATE\n\n"
            f"Catalog: {catalog.upper()}\n"
            f"Event: {event_type.replace('_', ' ').title()}\n"
            f"Change: {event_value}\n"
            f"Time: {event_time} UTC"
        )

        print("\nTelegram message:")
        print(text)

        if not DRY_RUN:
            send_telegram_message(text)
        else:
            print("DRY RUN — not sent")

if __name__ == "__main__":
    main()