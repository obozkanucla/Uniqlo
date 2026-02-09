import json
from datetime import datetime

EVENT_TYPE = "RARE_DEEP_DISCOUNT"

def detect(conn):
    now = datetime.utcnow().isoformat()

    rows = conn.execute("""
        SELECT
            catalog,
            product_id,
            source_variant_id,
            sku_path,
            product_name,
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
            AND discount_pct >= 60
            AND sale_price < 15
    """).fetchall()

    events = []

    for (
            catalog,
            product_id,
            source_variant_id,
            sku_path,
            product_name,
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
            sku_path,
            source_variant_id,
            color_code,
            color_label,
            size_code,
            size_label,
            json.dumps({
                "product_name": product_name,
                "sale_price": sale,
                "original_price": original,
                "discount_pct": discount
            })
        ))

    return events