# src/notify_events.py
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import requests
import os
from dotenv import load_dotenv

from src.notifications.rules import USER_NOTIFICATION_RULES

# --------------------------------------------------
# ENV
# --------------------------------------------------
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN missing")

# --------------------------------------------------
# PATHS
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "db" / "uniqlo.sqlite"

LOOKBACK_MINUTES = 40     # > scrape interval
COOLDOWN_HOURS = 24       # do not notify same item/event/user more than once per day
DRY_RUN = False

# --------------------------------------------------
# TELEGRAM
# --------------------------------------------------
def send_telegram_message(chat_id: int, text: str):
    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=10,
    )
    r.raise_for_status()

# --------------------------------------------------
# DB INIT
# --------------------------------------------------
def ensure_notification_log(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS uniqlo_notifications (
        sent_at TEXT NOT NULL,
        user TEXT NOT NULL,
        event_type TEXT NOT NULL,
        catalog TEXT NOT NULL,
        product_id TEXT NOT NULL,
        PRIMARY KEY (user, event_type, catalog, product_id)
    )
    """)
    conn.commit()

# --------------------------------------------------
# MAIN
# --------------------------------------------------
def main():
    since = (datetime.utcnow() - timedelta(minutes=LOOKBACK_MINUTES)).isoformat()
    cooldown_since = (datetime.utcnow() - timedelta(hours=COOLDOWN_HOURS)).isoformat()

    conn = sqlite3.connect(DB_PATH)
    ensure_notification_log(conn)

    events = conn.execute("""
        SELECT event_time, catalog, event_type, event_value
        FROM uniqlo_events
        WHERE event_time >= ?
        ORDER BY event_time ASC
    """, (since,)).fetchall()

    if not events:
        print("No new events.")
        conn.close()
        return

    for event_time, catalog, event_type, event_value in events:
        # Expected event_value format:
        # "<name> | £<price> | <discount>% | Size <X> | <product_id>"
        try:
            parts = [p.strip() for p in event_value.split("|")]
            name = parts[0]
            size = parts[3].replace("Size", "").strip()
            product_id = parts[4]
        except Exception:
            # Malformed event — skip
            continue

        for user, cfg in USER_NOTIFICATION_RULES.items():
            chat_id = cfg.get("chat_id")
            if not chat_id:
                continue

            event_cfg = cfg["events"].get(event_type)
            if not event_cfg:
                continue

            catalog_cfg = event_cfg.get(catalog)
            if not catalog_cfg:
                continue

            allowed_sizes = catalog_cfg.get("size", [])
            if size not in allowed_sizes:
                continue

            # Cooldown check
            already_sent = conn.execute("""
                SELECT 1
                FROM uniqlo_notifications
                WHERE user = ?
                  AND event_type = ?
                  AND catalog = ?
                  AND product_id = ?
                  AND sent_at >= ?
            """, (user, event_type, catalog, product_id, cooldown_since)).fetchone()

            if already_sent:
                continue

            # Build message
            text = (
                "🔥 UNIQLO RARE DEEP DISCOUNT\n\n"
                f"{catalog.upper()}\n\n"
                f"{name}\n"
                f"{event_value}\n\n"
                f"{event_time} UTC"
            )

            if DRY_RUN:
                print(f"[DRY RUN] Would notify {user}: {text}")
            else:
                send_telegram_message(chat_id, text)

            # Record notification
            conn.execute("""
                INSERT OR IGNORE INTO uniqlo_notifications
                VALUES (?, ?, ?, ?, ?)
            """, (
                datetime.utcnow().isoformat(),
                user,
                event_type,
                catalog,
                product_id,
            ))
            conn.commit()

    conn.close()

if __name__ == "__main__":
    main()