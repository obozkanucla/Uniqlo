import json
from datetime import datetime

EVENT_TYPE = "RARE_DEEP_DISCOUNT"


def detect(conn):
    now = datetime.utcnow().isoformat()

    rows = conn.execute("""
        SELECT
            o.product_id,
            o.catalog,
            a.color,
            a.size,
            o.sale_price_num,
            o.discount_pct
        FROM uniqlo_sale_observations o
        JOIN uniqlo_sku_availability a
          ON o.product_id = a.product_id
        WHERE o.sale_price_num < 10
          AND o.discount_pct >= 50
          AND a.is_available = 1
    """).fetchall()

    events = []

    for pid, catalog, color, size, price, discount in rows:
        events.append((
            now,
            catalog,
            EVENT_TYPE,
            pid,
            color,
            size,
            json.dumps({
                "price": price,
                "discount": discount
            })
        ))

    return events