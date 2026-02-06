import json
from datetime import datetime

EVENT_TYPE = "RARE_DEEP_DISCOUNT"

def detect(conn):
    now = datetime.utcnow().isoformat()

    rows = conn.execute("""
        SELECT
            catalog,
            product_id,
            variant_id,
            color_code,
            color_label,
            size_code,
            size_label,
            sale_price,
            original_price,
            discount_pct
        FROM uniqlo_sku_state
        WHERE
            is_available = 1
            AND discount_pct >= 70
            AND sale_price < 10
    """).fetchall()

    events = []

    for (
            catalog,
            product_id,
            variant_id,
            color_code,
            color_label,
            size_code,
            size_label,
            sale,
            original,
            discount
    ) in rows:
        events.append((
            now,
            catalog,
            EVENT_TYPE,
            product_id,
            variant_id,
            color_code,
            color_label,
            size_code,
            size_label,
            json.dumps({
                "sale_price": sale,
                "original_price": original,
                "discount_pct": discount
            })
        ))

    return events