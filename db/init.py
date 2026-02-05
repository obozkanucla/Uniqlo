# src/db/init.py  (or inline in notifier)
def ensure_notification_table(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS uniqlo_notified (
        user_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        last_sent_at TEXT NOT NULL,
        PRIMARY KEY (user_id, product_id, event_type)
    )
    """)
    conn.commit()