import sqlite3
import uuid
from pathlib import Path
from datetime import datetime

from db.schema import init_db
from src.scrapers.scrape_sku_state import scrape_sku_state
from src.events.rare_deep_discount import detect
from src.notifiers.notify_events import notify
from src.scrapers.catalog_scraper import scrape_catalog
from dotenv import load_dotenv
load_dotenv()
from db.schema import reset_events_table

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "db" / "uniqlo.sqlite"

def log(msg: str):
    print(f"[{datetime.utcnow().isoformat()}] {msg}", flush=True)

def persist_catalog(df, conn):
    if df.empty:
        return

    df.to_sql(
        "uniqlo_sale_observations",
        conn,
        if_exists="append",
        index=False,
    )

def main():
    log("START orchestrator")

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    log("Resetting events table")
    reset_events_table(conn)
    log("DB initialized")

    # 1. Scrape catalog (PURE)
    log("Scraping catalog")
    scrape_catalog(conn, log)

    # 2. Scrape SKU availability
    log("Scraping SKU availability")
    scrape_sku_state(conn, log)#, max_variants=5)
    log("SKU availability scraped")

    # 3. Detect events
    log("Detecting events")
    events = detect(conn)
    log(f"Events detected: {len(events)}")

    if events:
        conn.executemany("""
                         INSERT INTO uniqlo_events (
                            event_time,
                            catalog,
                            event_type,
                            product_id,
                            variant_id,
                            color_code,
                            color_label,
                            size_code,
                            size_label,
                            event_value
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                         """, events)
        conn.commit()

    # 4. Notify
    log("Notifying")
    notify(conn)
    log("Notifications done")

    conn.close()
    log("END orchestrator")

if __name__ == "__main__":
    main()