# src/events/deep_discount.py
from datetime import datetime
from .base import EventDetector

class DeepDiscountDetector(EventDetector):
    event_type = "RARE_DEEP_DISCOUNT"

    def __init__(self, price_threshold=10.0, min_discount_pct=50.0):
        self.price_threshold = price_threshold
        self.min_discount_pct = min_discount_pct

    def detect(self, conn, catalog: str):
        now = datetime.utcnow().isoformat()

        rows = conn.execute("""
            WITH latest AS (
                SELECT *
                FROM uniqlo_sale_observations
                WHERE catalog = ?
                  AND scraped_at = (
                      SELECT MAX(scraped_at)
                      FROM uniqlo_sale_observations
                      WHERE catalog = ?
                  )
            )
            SELECT
                product_id,
                name,
                sale_price_num,
                discount_pct
            FROM latest
            WHERE
                sale_price_num < ?
                AND discount_pct >= ?
                AND (
                    xs_available = 1
                    OR s_available = 1
                    OR m_available = 1
                    OR l_available = 1
                    OR xl_available = 1
                )
        """, (
            catalog,
            catalog,
            self.price_threshold,
            self.min_discount_pct,
        )).fetchall()

        return [
            (
                now,
                catalog,
                self.event_type,
                product_id,
                f"{name} | £{price:.2f} | {discount:.0f}%"
            )
            for product_id, name, price, discount in rows
        ]