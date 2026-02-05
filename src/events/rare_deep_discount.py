import json
from datetime import datetime

EVENT_TYPE = "RARE_DEEP_DISCOUNT"


def detect(conn):
    """
    Detect rare deep discounts using:
    - latest price snapshot per product
    - currently available color/size combinations
    """

    now = datetime.utcnow().isoformat()

    rows = conn.execute("""
        WITH latest_prices AS (
            SELECT o.*
            FROM uniqlo_sale_observations o
            JOIN (
                SELECT
                    product_id,
                    MAX(scraped_at) AS max_scraped_at
                FROM uniqlo_sale_observations
                GROUP BY product_id
            ) latest
              ON o.product_id = latest.product_id
             AND o.scraped_at = latest.max_scraped_at
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
        WHERE lp.sale_price_num < 10
          AND lp.discount_pct >= 50
          AND a.is_available = 1
    """).fetchall()

    events = []

    for pid, catalog, color, size, sale, original, discount in rows:
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