# src/db/reset.py
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "db" / "uniqlo.sqlite"

if DB_PATH.exists():
    DB_PATH.unlink()
    print("SQLite database deleted.")
else:
    print("No database found.")