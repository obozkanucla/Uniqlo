# src/notify_events.py
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import requests
from dotenv import load_dotenv

from src.notifications.rules import USER_NOTIFICATION_RULES

# --------------------------------------------------
# ENV
# --------------------------------------------------
load_dotenv()

BOT_TOKEN = Path(__file__).resolve().parents[1]
BOT_TOKEN = None

import os
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN missing")

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "db" / "uniqlo.sqlite"

LOOKBACK_MINUTES = 40          # slightly > scrape interval
COOLDOWN_HOURS   = 24          # per product per user
DRY_RUN = False

# --------------------------------------------------
# TELEGRAM
# --------------------------------------------------
def send_telegram_message(chat_id: str, text: str):
    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True
        },
        timeout=10
    )
    r.raise_for_status()

# --------------------------------------------------
# DB HELPERS
# --------------------------------------------------
def ensure_notification_table(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS uniqlo_notified (
        user_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        last_sent_at TEXT NOT NULL,
        PRIMARY KEY (user_id, product_id, event_type)
    )
    """)
    conn.commit()

def was_recently_notified(conn, user_id, product_id, event_type, cutoff):
    row = conn.execute("""
        SELECT 1
        FROM uniqlo_notified
        WHERE user_id = ?
          AND product_id = ?
          AND event_type = ?
          AND last_sent_at >= ?
    """, (user_id, product_id, event_type, cutoff)).fetchone()
    return row is not None

def mark_notified(conn, user_id, product_id, event_type):
    conn.execute("""
        INSERT OR REPLACE INTO uniqlo_notified
        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        product_id,
        event_type,
        datetime.utcnow().isoformat()
    ))
    conn.commit()

# --------------------------------------------------
# MAIN
# --------------------------------------------------
def main():
    since = (datetime.utcnow() - timedelta(minutes=LOOKBACK_MINUTES)).isoformat()
    cooldown_cutoff = (datetime.utcnow() - timedelta(hours=COOLDOWN_HOURS)).isoformat()

    conn = sqlite3.connect(DB_PATH)
    ensure_notification_table(conn)

    events = conn.execute("""
        SELECT event_time, catalog, event_type, product_id, event_value
        FROM uniqlo_events
        WHERE event_time >= ?
        ORDER BY event_time ASC
    """, (since,)).fetchall()

    if not events:
        print("No new events.")
        return

    for user_id, cfg in USER_NOTIFICATION_RULES.items():
        chat_id = cfg.get("chat_id")
        if not chat_id:
            continue

        for event_time, catalog, event_type, product_id, event_value in events:

            # user not subscribed to this event
            if event_type not in cfg["events"]:
                continue

            # user not interested in this catalog
            if catalog not in cfg["events"][event_type]:
                continue

            # cooldown check
            if was_recently_notified(
                conn,
                user_id,
                product_id,
                event_type,
                cooldown_cutoff
            ):
                continue

            text = (
                "🔥 UNIQLO RARE DEEP DISCOUNT\n\n"
                f"{catalog.upper()}\n\n"
                f"{event_value}\n\n"
                f"{event_time} UTC"
            )

            if DRY_RUN:
                print(f"[DRY RUN] → {user_id}: {text}")
            else:
                send_telegram_message(chat_id, text)
                mark_notified(conn, user_id, product_id, event_type)
                print(f"Notified {user_id} — {product_id}")

    conn.close()

if __name__ == "__main__":
    main()