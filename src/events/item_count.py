from datetime import datetime, timedelta
from .base import EventDetector

class ItemCountIncrease(EventDetector):
    event_type = "ITEM_COUNT_INCREASE"

    def __init__(self, window_minutes=30):
        self.window = timedelta(minutes=window_minutes)

    def detect(self, conn, catalog: str):
        now = datetime.utcnow()
        cur_start = (now - self.window).isoformat()
        prev_start = (now - 2 * self.window).isoformat()

        current = conn.execute("""
            SELECT COUNT(DISTINCT product_id)
            FROM uniqlo_sale_observations
            WHERE catalog = ?
              AND scraped_at >= ?
        """, (catalog, cur_start)).fetchone()[0] or 0

        previous = conn.execute("""
            SELECT COUNT(DISTINCT product_id)
            FROM uniqlo_sale_observations
            WHERE catalog = ?
              AND scraped_at >= ?
              AND scraped_at < ?
        """, (catalog, prev_start, cur_start)).fetchone()[0] or 0

        # 🔒 bootstrap suppression
        if previous == 0:
            return []

        if current > previous:
            return [(
                now.isoformat(),
                catalog,
                self.event_type,
                None,
                f"{previous} → {current} (+{current - previous})"
            )]

        return []