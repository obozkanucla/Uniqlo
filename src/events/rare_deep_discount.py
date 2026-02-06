import json
from datetime import datetime

EVENT_TYPE = "RARE_DEEP_DISCOUNT"

def detect(conn):
    now = datetime.utcnow().isoformat()
    rows = conn.execute("""
                    WITH latest_prices AS (
                    SELECT o.*
                    FROM uniqlo_sale_observations o
                    JOIN (
                        SELECT product_id, MAX(scraped_at) AS max_ts
                        FROM uniqlo_sale_observations
                        GROUP BY product_id
                    ) x
                      ON o.product_id = x.product_id
                     AND o.scraped_at = x.max_ts
                )
                SELECT
                    lp.product_id,
                    lp.catalog,
                    a.color,
                    a.size,
                    lp.sale_price_num,
                    lp.original_price_num,
                    lp.discount_pct
                FROM latest_prices lp
                JOIN uniqlo_sku_availability a
                  ON lp.product_id = a.product_id
                WHERE a.is_available = 1
                  AND lp.sale_price_num < 10
                  AND lp.discount_pct >= 70;
    """).fetchall()

    seen = set()
    events = []

    for pid, catalog, color, size, sale, original, discount in rows:
        key = (pid, catalog, color, size)
        if key in seen:
            continue
        seen.add(key)

        events.append((
            now,
            catalog,
            EVENT_TYPE,
            pid,
            color,
            size,
            json.dumps({
                "price": sale,
                "original_price": original,
                "discount": discount
            })
        ))

    return events