import sqlite3
from pathlib import Path
from src.events.item_count import ItemCountIncrease
from src.events.deep_discount import DeepDiscountDetector

DB_PATH = Path("db/uniqlo.sqlite")

DETECTORS = [
    ItemCountIncrease(window_minutes=30),
    DeepDiscountDetector(price_threshold=10.0, min_discount_pct=50.0),
]

CATALOGS = ["men", "women"]

def main():
    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS uniqlo_events (
        event_time TEXT NOT NULL,
        catalog TEXT NOT NULL,
        event_type TEXT NOT NULL,
        event_value TEXT,
        PRIMARY KEY (event_time, catalog, event_type, event_value)
    )
    """)

    for catalog in CATALOGS:
        for detector in DETECTORS:
            events = detector.detect(conn, catalog)
            for event_time, catalog, event_type, event_value in events:
                conn.execute("""
                INSERT OR IGNORE INTO uniqlo_events
                VALUES (?, ?, ?, ?)
                """, (event_time, catalog, event_type, event_value))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()