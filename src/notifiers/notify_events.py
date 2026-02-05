import requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
import os

from src.notifiers.rules import USER_NOTIFICATION_RULES

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "db" / "uniqlo.sqlite"
LOOKBACK_MINUTES = 40
COOLDOWN_HOURS = 24

def send_telegram_message(bot_token, chat_id: str, text: str):
    requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True
        },
        timeout=10
    ).raise_for_status()

import json
from datetime import datetime, timedelta

COOLDOWN_HOURS = 24

def notify(conn, log=print):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    rules = USER_NOTIFICATION_RULES
    if not bot_token:
        log("[NOTIFY] No bot token — skipping")
        return

    # Ensure notification table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS uniqlo_notifications (
            notified_at TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            product_id TEXT NOT NULL,
            color TEXT NOT NULL,
            size TEXT NOT NULL,
            PRIMARY KEY (chat_id, event_type, product_id, color, size)
        )
    """)
    conn.commit()

    events = conn.execute("""
        SELECT
            event_time,
            event_type,
            product_id,
            catalog,
            color,
            size,
            event_value
        FROM uniqlo_events
        ORDER BY event_time ASC
    """).fetchall()

    log(f"[NOTIFY] Loaded {len(events)} events")

    for event_time, etype, pid, catalog, color, size, payload in events:
        data = json.loads(payload)

        for user, cfg in rules.items():
            chat_id = cfg.get("chat_id")
            if not chat_id:
                log(f"[NOTIFY] {user}: no chat_id")
                continue

            rule = cfg["events"].get(etype, {}).get(catalog)
            if not rule:
                log(f"[NOTIFY] {user}: no rule for {etype}/{catalog}")
                continue

            # ---- size filter ----
            allowed_sizes = rule.get("sizes")
            if allowed_sizes and size not in allowed_sizes:
                log(f"[NOTIFY] {user}: size {size} not allowed")
                continue

            # ---- color filter ----
            allowed_colors = rule.get("colors")
            if allowed_colors and color not in allowed_colors:
                log(f"[NOTIFY] {user}: color {color} not allowed")
                continue

            # ---- cooldown ----
            last = conn.execute("""
                SELECT notified_at
                FROM uniqlo_notifications
                WHERE chat_id=? AND event_type=? AND product_id=?
                  AND color=? AND size=?
            """, (chat_id, etype, pid, color, size)).fetchone()

            if last:
                delta = datetime.utcnow() - datetime.fromisoformat(last[0])
                if delta < timedelta(hours=COOLDOWN_HOURS):
                    log(f"[NOTIFY] {user}: cooldown active")
                    continue

            # ---- SEND ----
            text = (
                "🔥 UNIQLO RARE DEEP DISCOUNT\n\n"
                f"{catalog.upper()}\n"
                f"Product: {pid}\n"
                f"Color: {color}\n"
                f"Size: {size}\n"
                f"£{data['price']} ({data['discount']}%)\n\n"
                f"https://www.uniqlo.com/uk/en/products/E{pid}"
            )

            send_telegram_message(bot_token, chat_id, text)

            conn.execute("""
                INSERT OR REPLACE INTO uniqlo_notifications
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.utcnow().isoformat(),
                chat_id, etype, pid, color, size
            ))
            conn.commit()

            log(f"[NOTIFY] SENT → {user} {pid} {color} {size}")