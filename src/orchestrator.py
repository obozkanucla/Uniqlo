import sqlite3
import uuid
from pathlib import Path
from datetime import datetime

from db.schema import init_db
from scrapers.catalog_scraper import scrape_catalog
from scrapers.color_availability_playwright import scrape_sku_availability
from events.rare_deep_discount import detect as detect_rare_deep_discount
from notifiers.notify_events import notify
from dotenv import load_dotenv
load_dotenv()

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
    log("DB initialized")

    # 1. Scrape catalog (PURE)
    log("Scraping catalog")
    catalog_df = scrape_catalog()
    log(f"Catalog scraped: {len(catalog_df)} rows")

    if catalog_df.empty:
        log("Catalog empty — exiting")
        return

    # inject scrape identity ONCE
    scrape_id = uuid.uuid4().hex
    catalog_df["scrape_id"] = scrape_id

    log("Persisting catalog")
    persist_catalog(catalog_df, conn)
    log("Catalog persisted")

    # 2. Scrape SKU availability
    log("Scraping SKU availability")
    scrape_sku_availability(conn, log) #, max_products=5)
    log("SKU availability scraped")

    # 3. Detect events
    log("Detecting events")
    events = detect_rare_deep_discount(conn)
    log(f"Events detected: {len(events)}")

    if events:
        conn.executemany("""
            INSERT OR IGNORE INTO uniqlo_events
            (event_time, catalog, event_type, product_id, color, size, event_value)
            VALUES (?, ?, ?, ?, ?, ?, ?)
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