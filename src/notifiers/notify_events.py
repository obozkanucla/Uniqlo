import os
import json
import requests
from collections import defaultdict
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.notifiers.rules import USER_NOTIFICATION_RULES

load_dotenv()

BASE_DOMAIN = "https://www.uniqlo.com"


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

    LOOKBACK_MINUTES = 60
    since = (datetime.utcnow() - timedelta(minutes=LOOKBACK_MINUTES)).isoformat()

    rows = conn.execute("""
        SELECT
            event_time,
            catalog,
            event_type,
            product_id,
            sku_path,
            source_variant_id,
            color_code,
            color_label,
            size_label,
            event_value
        FROM uniqlo_events
        WHERE event_time >= ?
    """, (since,)).fetchall()

    log(f"[NOTIFY] Loaded {len(rows)} raw events")

    for user, cfg in USER_NOTIFICATION_RULES.items():
        chat_id = cfg.get("chat_id")
        if not chat_id:
            continue

        grouped = defaultdict(lambda: {"sizes": set()})

        for (
            _event_time,
            catalog,
            event_type,
            product_id,
            sku_path,
            _source_variant_id,
            color_code,
            color_label,
            size_label,
            event_value
        ) in rows:
            rule = cfg.get("events", {}).get(event_type, {}).get(catalog)
            if not rule:
                continue

            # size filter
            if rule.get("sizes") and size_label not in rule["sizes"]:
                continue

            # color filter
            if rule.get("colors") and color_label not in rule["colors"]:
                continue

            payload = json.loads(event_value)

            key = (
                catalog,
                event_type,
                product_id,
                payload["product_name"],
                color_code,
                color_label,
                sku_path,
            )

            g = grouped[key]
            g.update({
                "catalog": catalog,
                "event_type": event_type,
                "product_id": product_id,
                "product_name": payload["product_name"],
                "color_code": color_code,
                "color_label": color_label,
                "sku_path": sku_path,
                "sale": payload["sale_price"],
                "original": payload["original_price"],
                "discount": payload["discount_pct"],
            })
            g["sizes"].add(size_label)

        log(f"[NOTIFY] {user}: {len(grouped)} messages")

        for g in grouped.values():
            if not g["sizes"]:
                continue

            sizes_text = ", ".join(sorted(g["sizes"]))

            url = (
                f"{BASE_DOMAIN}{g['sku_path']}"
                f"?colorDisplayCode={g['color_code']}"
            )

            text = (
                "🔥 UNIQLO RARE DEEP DISCOUNT\n\n"
                f"{g['catalog'].upper()}\n"
                f"{g['product_name']}\n"
                f"Color: {g['color_label']}\n"
                f"Sizes: {sizes_text}\n\n"
                f"£{g['sale']} (was £{g['original']}, -{g['discount']}%)\n\n"
                f"{url}"
            )

            send_telegram_message(bot_token, chat_id, text)

            conn.execute(
                """
                INSERT OR REPLACE INTO uniqlo_notifications
                (notified_at, chat_id, event_type, sku_path, size_code)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    datetime.utcnow().isoformat(),
                    chat_id,
                    g["event_type"],
                    g["sku_path"],
                    "MULTI",
                ),
            )

        conn.commit()

    log("[NOTIFY] Notifications sent")