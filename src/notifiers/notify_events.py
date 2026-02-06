import os
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.notifiers.rules import USER_NOTIFICATION_RULES

load_dotenv()

COOLDOWN_MINUTES = 0


def send_telegram_message(bot_token, chat_id: str, text: str):
    requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=10,
    ).raise_for_status()


def notify(conn, log=print):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        log("[NOTIFY] No TELEGRAM_BOT_TOKEN — skipping")
        return

    rules = USER_NOTIFICATION_RULES

    # --------------------------------------------------
    # Load recent events (already filtered + deduped)
    # --------------------------------------------------
    LOOKBACK_MINUTES = 60
    since = (datetime.utcnow() - timedelta(minutes=LOOKBACK_MINUTES)).isoformat()

    events = conn.execute(
        """
        SELECT
            event_time,
            catalog,
            event_type,
            product_id,
            variant_id,
            color,
            size,
            event_value
        FROM uniqlo_events
        WHERE event_time >= ?
        ORDER BY event_time ASC
        """,
        (since,),
    ).fetchall()

    log(f"[NOTIFY] Loaded {len(events)} recent events")

    for (
        event_time,
        catalog,
        etype,
        product_id,
        variant_id,
        color,
        size,
        event_value,
    ) in events:

        payload = json.loads(event_value)
        sale = payload["sale_price"]
        original = payload["original_price"]
        discount = payload["discount_pct"]

        for user, cfg in rules.items():
            chat_id = cfg.get("chat_id")
            if not chat_id:
                continue

            rule = cfg.get("events", {}).get(etype, {}).get(catalog)
            if not rule:
                continue

            if rule.get("sizes") and size not in rule["sizes"]:
                continue

            if rule.get("colors") and color not in rule["colors"]:
                continue

            # --------------------------------------------------
            # Idempotency / cooldown
            # --------------------------------------------------
            last = conn.execute(
                """
                SELECT notified_at
                FROM uniqlo_notifications
                WHERE
                    chat_id = ?
                    AND event_type = ?
                    AND variant_id = ?
                    AND color = ?
                    AND size = ?
                """,
                (chat_id, etype, variant_id, color, size),
            ).fetchone()

            if last:
                delta = datetime.utcnow() - datetime.fromisoformat(last[0])
                if delta < timedelta(minutes=COOLDOWN_MINUTES):
                    continue
            url = (f"https://www.uniqlo.com/uk/en/products/{variant_id}"f"?colorDisplayCode={color}")
            text = (
                "🔥 UNIQLO RARE DEEP DISCOUNT\n\n"
                f"{catalog.upper()}\n"
                f"Product: {product_id}\n"
                f"Variant: {variant_id}\n"
                f"Color: {color}\n"
                f"Size: {size}\n"
                f"£{sale} (was £{original}, -{discount}%)\n\n"
                f"https://www.uniqlo.com/uk/en/products/{variant_id}"
            )

            send_telegram_message(bot_token, chat_id, text)

            conn.execute(
                """
                INSERT OR REPLACE INTO uniqlo_notifications
                (notified_at, chat_id, event_type, variant_id, color, size)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.utcnow().isoformat(),
                    chat_id,
                    etype,
                    variant_id,
                    color,
                    size,
                ),
            )
            conn.commit()

            log(f"[NOTIFY] SENT → {user} {variant_id} {color} {size}")