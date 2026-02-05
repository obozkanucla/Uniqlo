import os
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.notifiers.rules import USER_NOTIFICATION_RULES

load_dotenv()

COOLDOWN_HOURS = 24
MAX_PRICE = 20
MIN_DISCOUNT = 50


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


def notify(conn, log=print):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    rules = USER_NOTIFICATION_RULES

    if not bot_token:
        log("[NOTIFY] No TELEGRAM_BOT_TOKEN — skipping")
        return

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
            e.event_time,
            e.event_type,
            e.product_id,
            e.catalog,
            e.color,
            e.size,
            o.sale_price_num,
            o.original_price_num,
            o.discount_pct
        FROM uniqlo_events e
        JOIN uniqlo_sale_observations o
          ON e.product_id = o.product_id
        ORDER BY e.event_time ASC
    """).fetchall()

    log(f"[NOTIFY] Loaded {len(events)} events")

    for _, etype, pid, catalog, color, size, sale, orig, discount in events:

        # ---- HARD REVALIDATION ----
        if sale > MAX_PRICE:
            # log(f"[NOTIFY] SKIP {pid}: price {sale} > {MAX_PRICE}")
            continue

        if discount < MIN_DISCOUNT:
            # log(f"[NOTIFY] SKIP {pid}: discount {discount} < {MIN_DISCOUNT}")
            continue
        log(f"[NOTIFY] DEAL CAUGHT {pid}: price {sale} < {MAX_PRICE}")
        log(f"[NOTIFY] DEAL CAUGHT {pid}: discount {discount} < {MIN_DISCOUNT}")

        for user, cfg in rules.items():
            chat_id = cfg.get("chat_id")
            if not chat_id:
                continue

            rule = cfg["events"].get(etype, {}).get(catalog)
            if not rule:
                continue

            if rule.get("sizes") and size not in rule["sizes"]:
                continue

            if rule.get("colors") and color not in rule["colors"]:
                continue

            last = conn.execute("""
                SELECT notified_at
                FROM uniqlo_notifications
                WHERE chat_id=? AND event_type=? AND product_id=?
                  AND color=? AND size=?
            """, (chat_id, etype, pid, color, size)).fetchone()

            if last:
                if datetime.utcnow() - datetime.fromisoformat(last[0]) < timedelta(hours=COOLDOWN_HOURS):
                    continue

            text = (
                "🔥 UNIQLO RARE DEEP DISCOUNT\n\n"
                f"{catalog.upper()}\n"
                f"Product: {pid}\n"
                f"Color: {color}\n"
                f"Size: {size}\n"
                f"£{sale} (was £{orig}, -{discount}%)\n\n"
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