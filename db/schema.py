# src/db/schema.py
def init_db(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS uniqlo_sale_observations (
        scrape_id TEXT NOT NULL,
        scraped_at TEXT NOT NULL,
        catalog TEXT NOT NULL,
        product_id TEXT NOT NULL,

        name TEXT,
        sale_price_num REAL,
        original_price_num REAL,
        discount_pct REAL,

        xs_available INTEGER,
        s_available INTEGER,
        m_available INTEGER,
        l_available INTEGER,
        xl_available INTEGER,

        product_url TEXT,
        PRIMARY KEY (scrape_id, catalog, product_id)
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS uniqlo_events (
        event_time TEXT NOT NULL,
        catalog TEXT NOT NULL,
        event_type TEXT NOT NULL,
        product_id TEXT NOT NULL,
        event_value TEXT,
        PRIMARY KEY (event_time, catalog, event_type, product_id)
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS uniqlo_notifications (
        notified_at TEXT NOT NULL,
        chat_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        product_id TEXT NOT NULL,
        PRIMARY KEY (chat_id, event_type, product_id, notified_at)
    )
    """)

    conn.commit()