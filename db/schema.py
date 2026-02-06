# src/db/schema.py

def init_db(conn):
    """
    Initialize Uniqlo SQLite schema.

    Canonical truths:
    - Sale catalog exposes VARIANTS (not products)
    - Price is per (variant, color)
    - Availability is per (variant, color, size)
    - uniqlo_sku_state is the single source of truth
    """

    # --------------------------------------------------
    # 1. Sale catalog (variant discovery only)
    # --------------------------------------------------
    conn.execute("""
        CREATE TABLE IF NOT EXISTS uniqlo_sale_variants (
            scrape_id TEXT NOT NULL,
            scraped_at TEXT NOT NULL,
            catalog TEXT NOT NULL,
    
            product_id TEXT NOT NULL,      -- e.g. 450195
            variant_id TEXT NOT NULL,      -- e.g. E450195-000-02
            variant_url TEXT NOT NULL,
    
            name TEXT,
    
            PRIMARY KEY (catalog, variant_id)
        )
        """)

    # --------------------------------------------------
    # 2. Canonical SKU truth table
    # --------------------------------------------------
    conn.execute("""
    CREATE TABLE IF NOT EXISTS uniqlo_sku_state (
        observed_at TEXT NOT NULL,
        catalog TEXT NOT NULL,

        product_id TEXT NOT NULL,
        variant_id TEXT NOT NULL,
        color_code TEXT NOT NULL,
        size TEXT NOT NULL,

        sale_price REAL,
        original_price REAL,
        discount_pct REAL,

        is_available INTEGER NOT NULL,

        PRIMARY KEY (variant_id, color_code, size)
    )
    """)

    # --------------------------------------------------
    # 3. Deduplicated SKU-level events
    # --------------------------------------------------
    conn.execute("""
    CREATE TABLE IF NOT EXISTS uniqlo_events (
        event_time TEXT NOT NULL,
        catalog TEXT NOT NULL,
        event_type TEXT NOT NULL,

        product_id TEXT NOT NULL,
        variant_id TEXT NOT NULL,
        color TEXT NOT NULL,
        size TEXT NOT NULL,

        event_value TEXT,

        PRIMARY KEY (event_type, variant_id, color, size)
    )
    """)

    # --------------------------------------------------
    # 4. Notification delivery log
    # --------------------------------------------------
    conn.execute("""
    CREATE TABLE IF NOT EXISTS uniqlo_notifications (
        notified_at TEXT NOT NULL,
        chat_id TEXT NOT NULL,
        event_type TEXT NOT NULL,

        variant_id TEXT NOT NULL,
        color TEXT NOT NULL,
        size TEXT NOT NULL,

        PRIMARY KEY (chat_id, event_type, variant_id, color, size)
    )
    """)

    conn.commit()


def reset_events_table(conn):
    """
    Hard reset event table (safe for testing).
    Does NOT touch SKU truth or sale catalog.
    """
    conn.execute("DROP TABLE IF EXISTS uniqlo_events")
    conn.execute("""
    CREATE TABLE uniqlo_events (
        event_time TEXT NOT NULL,
        catalog TEXT NOT NULL,
        event_type TEXT NOT NULL,

        product_id TEXT NOT NULL,
        variant_id TEXT NOT NULL,
        color TEXT NOT NULL,
        size TEXT NOT NULL,

        event_value TEXT,

        PRIMARY KEY (event_type, variant_id, color, size)
    )
    """)
    conn.commit()