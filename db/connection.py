# src/db/connection.py
import sqlite3
from pathlib import Path

def get_conn():
    db_path = Path("db/uniqlo.sqlite")
    db_path.parent.mkdir(exist_ok=True)
    return sqlite3.connect(db_path)