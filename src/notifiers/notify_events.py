import os
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.notifiers.rules import USER_NOTIFICATION_RULES

load_dotenv()

# ---- TEST MODE ----
COOLDOWN_MINUTES = 0
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
    LOOKBACK_MINUTES = 40
    since = (datetime.utcnow() - timedelta(minutes=LOOKBACK_MINUTES)).isoformat()
    events = conn.execute("""
                          SELECT e.event_time,
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
                          WHERE e.event_time >= ?
                          ORDER BY e.event_time ASC
                          """, (since,)).fetchall()

    log(f"[NOTIFY] Loaded {len(events)} recent events")

    for _, etype, pid, catalog, color, size, sale, orig, discount in events:

        # ---- HARD REVALIDATION ----
        if sale > MAX_PRICE:
            # log(f"[NOTIFY] SKIP {pid}: price {sale} > {MAX_PRICE}")
            continue

        if discount < MIN_DISCOUNT:
            # log(f"[NOTIFY] SKIP {pid}: discount {discount} < {MIN_DISCOUNT}")
            continue
        # log(f"[NOTIFY] DEAL CAUGHT {pid}: price {sale} < {MAX_PRICE}")
        # log(f"[NOTIFY] DEAL CAUGHT {pid}: discount {discount} > {MIN_DISCOUNT}")

        for user, cfg in rules.items():
            chat_id = cfg.get("chat_id")
            if not chat_id:
                continue

            user_event_rules = cfg["events"].get(etype, {})
            log(f"[DEBUG] USER={user} RULE CATALOG KEYS={list(user_event_rules.keys())}")
            log(f"[DEBUG] EVENT etype={etype} catalog={catalog} user={user}")
            log(f"[DEBUG] USER RULES for etype={etype}: {cfg['events'].get(etype)}")

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
                delta = datetime.utcnow() - datetime.fromisoformat(last[0])
                if delta < timedelta(minutes=COOLDOWN_MINUTES):
                    log(f"[NOTIFY] {user}: cooldown active ({delta.seconds}s)")
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
            log(
                f"[DEBUG] PASS user={user} "
                f"pid={pid} catalog={catalog} "
                f"color={color} size={size} "
                f"price={sale} discount={discount}"
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