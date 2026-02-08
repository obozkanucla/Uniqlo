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
    conn.execute("DROP TABLE IF EXISTS uniqlo_events")
    conn.execute("DROP TABLE IF EXISTS uniqlo_notifications")
    # --------------------------------------------------
    # 1. Sale catalog (variant discovery only)
    # --------------------------------------------------
    conn.execute("""
        CREATE TABLE IF NOT EXISTS uniqlo_sale_variants (
            scrape_id TEXT NOT NULL,
            scraped_at TEXT NOT NULL,
            catalog TEXT NOT NULL,
        
            product_id TEXT NOT NULL,
            variant_id TEXT NOT NULL,
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
                observed_at       TEXT    NOT NULL,
                catalog           TEXT    NOT NULL,
                product_id        TEXT    NOT NULL,
                source_variant_id        TEXT    NOT NULL,    -- from uniqlo_sale_variants
                product_name    TEXT NOT NULL,
                sku_path          TEXT    NOT NULL,   -- /uk/en/products/E450251-000/00
            
                color_code        TEXT    NOT NULL,
                color_label       TEXT    NOT NULL,
                size_code         TEXT    NOT NULL,
                size_label        TEXT    NOT NULL,
            
                sale_price        REAL    NOT NULL,
                original_price    REAL    NOT NULL,
                discount_pct      REAL    NOT NULL,
                is_available      INTEGER NOT NULL
            )
    """)

    # --------------------------------------------------
    # 3. Deduplicated SKU-level events
    # --------------------------------------------------
    conn.execute("""
            CREATE TABLE uniqlo_events (
                event_time TEXT,
                catalog TEXT,
                event_type TEXT,
                product_id TEXT,
                sku_path TEXT,
                source_variant_id TEXT,
                color_code TEXT,
                color_label TEXT,
                size_code TEXT,
                size_label TEXT,
                event_value TEXT
            )
    """)

    # --------------------------------------------------
    # 4. Notification delivery log
    # --------------------------------------------------
    conn.execute("""
        CREATE TABLE uniqlo_notifications (
            notified_at     TEXT    NOT NULL,
            chat_id         TEXT    NOT NULL,
            event_type      TEXT    NOT NULL,
        
            sku_path        TEXT    NOT NULL,
            size_code       TEXT    NOT NULL
        )
    """)

    conn.commit()

def assert_schema(conn):
    cols = [c[1] for c in conn.execute("PRAGMA table_info(uniqlo_sku_state)")]
    expected = {
        "observed_at",
        "catalog",
        "product_id",
        "source_variant_id",
        "product_name",
        "sku_path",
        "color_code",
        "color_label",
        "size_code",
        "size_label",
        "sale_price",
        "original_price",
        "discount_pct",
        "is_available",
    }
    if set(cols) != expected:
        raise RuntimeError(f"Schema mismatch: {cols}")

def reset_events_table(conn):
    conn.execute("DROP TABLE IF EXISTS uniqlo_events")
    conn.execute("""
            CREATE TABLE IF NOT EXISTS uniqlo_events (
                event_time TEXT,
                catalog TEXT,
                event_type TEXT,
                product_id TEXT,
                sku_path TEXT,
                source_variant_id TEXT,
                color_code TEXT,
                color_label TEXT,
                size_code TEXT,
                size_label TEXT,
                event_value TEXT
        )
    """)
    conn.commit()