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
    cols = [c[1] for c in conn.execute("PRAGMA table_info(uniqlo_events)")]
    assert "sku_path" in cols, f"Schema mismatch: {cols}"
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
    # print(conn.execute("PRAGMA table_info(uniqlo_events)").fetchall())
    events = conn.execute(
        """
        SELECT 
            event_time, 
            catalog, 
            event_type, 
            product_id, 
            sku_path, 
            source_variant_id, 
            color_code, 
            color_label, 
            size_code, 
            size_label, 
            event_value
        FROM uniqlo_events
        WHERE event_time >= ?
        """,
        (since,),
    ).fetchall()

    log(f"[NOTIFY] Loaded {len(events)} recent events")
    skip_counts = {
        "no_chat": 0,
        "no_rule": 0,
        "size": 0,
        "color": 0,
        "sent": 0,
    }
    total = 0
    for (
            event_time,
            catalog,
            etype,
            product_id,
            sku_path,
            source_variant_id,
            color_code,
            color_label,
            size_code,
            size_label,
            event_value,
        ) in events:

        payload = json.loads(event_value)
        sale = payload["sale_price"]
        original = payload["original_price"]
        discount = payload["discount_pct"]

        for user, cfg in rules.items():
            total += 1

            chat_id = cfg.get("chat_id")
            if not chat_id:
                skip_counts["no_chat"] += 1
                log(f"[NOTIFY][SKIP] no_chat → {skip_counts['no_chat']}/{total}")
                continue

            rule = cfg.get("events", {}).get(etype, {}).get(catalog)
            if not rule:
                skip_counts["no_rule"] += 1
                log(f"[NOTIFY][SKIP] no_rule → {skip_counts['no_rule']}/{total}")
                continue

            if rule.get("sizes") and size_label not in rule["sizes"]:
                skip_counts["size"] += 1
                log(f"[NOTIFY][SKIP] size → {skip_counts['size']}/{total}")
                continue

            if rule.get("colors") and color_label not in rule["colors"]:
                skip_counts["color"] += 1
                log(f"[NOTIFY][SKIP] color → {skip_counts['color']}/{total}")
                continue

            skip_counts["sent"] += 1
            log(f"[NOTIFY][PASS] sent → {skip_counts['sent']}/{total}")

            # --------------------------------------------------
            # Idempotency / cooldown
            # --------------------------------------------------
            last = conn.execute(
                """
                SELECT notified_at
                FROM uniqlo_notifications
                WHERE chat_id = ?
                  AND event_type = ?
                  AND sku_path = ?
                  AND size_code = ?
                """,
                (chat_id, etype, sku_path, size_code),
            ).fetchone()

            if last:
                delta = datetime.utcnow() - datetime.fromisoformat(last[0])
                if delta < timedelta(minutes=COOLDOWN_MINUTES):
                    continue
            BASE_DOMAIN = "https://www.uniqlo.com"

            url = (
                f"{BASE_DOMAIN}{sku_path}"
                f"?colorDisplayCode={color_code}"
                f"&sizeDisplayCode={size_code}"
            )
            text = (
                "🔥 UNIQLO RARE DEEP DISCOUNT\n\n"
                f"{catalog.upper()}\n"
                f"Product: {product_id}\n"
                f"SKU: {sku_path}\n"
                f"Color: {color_label}\n"
                f"Size: {size_label}\n"
                f"£{sale} (was £{original}, -{discount}%)\n\n"
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
                    etype,
                    sku_path,
                    size_code,
                ),
            )
            conn.commit()

            log(
                f"[NOTIFY] SENT → {user} {sku_path} {color_code} {size_code} "
                f"{color_label} {size_label}"
            )