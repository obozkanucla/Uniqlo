import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
import os
import sqlite3
from dotenv import load_dotenv
import uuid

SCRAPE_ID = uuid.uuid4().hex
SCRAPED_AT = datetime.utcnow().isoformat()
# --------------------------------------------------
# ENV
# --------------------------------------------------
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEND_TELEGRAM = True
WRITE_SQLITE = True
WRITE_CSV = False
DRY_RUN = False        # preview mode (no persistence)

TOP_N = 5

if SEND_TELEGRAM and (not BOT_TOKEN or not CHAT_ID):
    raise RuntimeError("Telegram enabled but BOT_TOKEN or CHAT_ID missing")

CHAT_ID = int(CHAT_ID)

# --------------------------------------------------
# PATHS
# --------------------------------------------------
CATALOGS = {
    "men": {
        "url": "https://www.uniqlo.com/uk/en/feature/sale/men",
        "target_size": "M",
    },
    "women": {
        "url": "https://www.uniqlo.com/uk/en/feature/sale/women",
        "target_size": "S",
    },
}

SIZE_COLUMN = {
    "XS": "xs_available",
    "S":  "s_available",
    "M":  "m_available",
    "L":  "l_available",
    "XL": "xl_available",
}

OUT_FILE = Path("uniqlo_sale_daily.csv")

BASE_DIR = Path(__file__).resolve().parents[1]   # project root
DB_PATH = BASE_DIR / "db" / "uniqlo.sqlite"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html",
}

# --------------------------------------------------
# SQLITE
# --------------------------------------------------
conn = sqlite3.connect(DB_PATH)
conn.execute("""
CREATE TABLE IF NOT EXISTS uniqlo_sale_observations (
    scrape_id TEXT NOT NULL,
    scraped_at TEXT NOT NULL,
    catalog TEXT NOT NULL,      -- men / women / etc
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
    PRIMARY KEY (scrape_id, catalog, product_id))
""")
conn.commit()

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def size_availability(product_url):
    r = requests.get(product_url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")

    sizes = {"XS": 0, "S": 0, "M": 0, "L": 0, "XL": 0}

    for btn in soup.select("button"):
        label = btn.get_text(strip=True)
        if label in sizes:
            sizes[label] = int(btn.get("aria-disabled") == "false")

    return sizes


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()


def format_message(df, catalog: str, size: str, top_n=5):
    lines = [f"UNIQLO UK SALE — {catalog.upper()} — Size {size}\n"]

    for i, row in enumerate(df.head(top_n).itertuples(), start=1):
        lines.append(
            f"{i}. [{row.catalog.upper()}] {row.name}\n"
            f"   {row.discount_pct}% off "
            f"({row.original_price} → {row.sale_price})\n"
            f"   {row.product_url}\n"
        )

    return "\n".join(lines)

# --------------------------------------------------
# SCRAPE
# --------------------------------------------------
all_results = []

for catalog, cfg in CATALOGS.items():
    url = cfg["url"]

    print(f"\n=== Scraping catalog: {catalog} ===")

    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    tiles = soup.select("div.product-tile")
    print(f"{catalog}: product tiles found: {len(tiles)}")

    rows = []

    for t in tiles:
        try:
            img = t.select_one("img[src*='imagesgoods']")
            if not img:
                continue

            m = re.search(r"imagesgoods/(\d+)/", img["src"])
            if not m:
                continue

            product_id = m.group(1)

            name_el = t.select("div[data-testid='ITOTypography']")
            name = name_el[1].get_text(strip=True) if len(name_el) >= 2 else None

            sale_el = t.select_one(".ito-red500")
            original_el = t.select_one(".strikethrough")
            if not sale_el or not original_el:
                continue

            rows.append({
                "catalog": catalog,
                "product_id": product_id,
                "name": name,
                "sale_price": sale_el.get_text(strip=True),
                "original_price": original_el.get_text(strip=True),
                "product_url": f"https://www.uniqlo.com/uk/en/products/{product_id}"
            })

        except Exception:
            continue

    df = pd.DataFrame(rows)

    if df.empty:
        print(f"{catalog}: no products extracted")
        continue

    df = df.drop_duplicates(subset=["product_id"]).reset_index(drop=True)

    # ---- prices
    df["sale_price_num"] = df["sale_price"].str.replace(r"[^\d.]", "", regex=True).astype(float)
    df["original_price_num"] = df["original_price"].str.replace(r"[^\d.]", "", regex=True).astype(float)
    df["discount_pct"] = (
        (df["original_price_num"] - df["sale_price_num"])
        / df["original_price_num"]
        * 100
    ).round(2)

    # ---- sizes
    sizes = df["product_url"].apply(size_availability)
    df["xs_available"] = sizes.apply(lambda x: x["XS"])
    df["s_available"]  = sizes.apply(lambda x: x["S"])
    df["m_available"]  = sizes.apply(lambda x: x["M"])
    df["l_available"]  = sizes.apply(lambda x: x["L"])
    df["xl_available"] = sizes.apply(lambda x: x["XL"])

    df["scrape_id"] = SCRAPE_ID
    df["scraped_at"] = SCRAPED_AT

    all_results.append(df)
# --------------------------------------------------
# SQLITE WRITE
# --------------------------------------------------
if not all_results:
    raise RuntimeError("No catalogs produced data")

final_df = pd.concat(all_results, ignore_index=True)

if WRITE_SQLITE and not DRY_RUN:
    final_df[[
        "scrape_id",
        "scraped_at",
        "catalog",
        "product_id",
        "name",
        "sale_price_num",
        "original_price_num",
        "discount_pct",
        "xs_available",
        "s_available",
        "m_available",
        "l_available",
        "xl_available",
        "product_url"
    ]].to_sql(
        "uniqlo_sale_observations",
        conn,
        if_exists="append",
        index=False
    )
else:
    print("DRY RUN — SQLite not written")

# --------------------------------------------------
# RESULT VIEW (per catalog)
# --------------------------------------------------
for catalog, cfg in CATALOGS.items():
    size = cfg["target_size"]
    size_col = SIZE_COLUMN[size]

    subset = (
        final_df[
            (final_df["catalog"] == catalog) &
            (final_df[size_col] == 1)
        ]
        .sort_values("discount_pct", ascending=False)
        .loc[:, [
            "catalog",
            "product_id",
            "name",
            "discount_pct",
            "sale_price",
            "original_price",
            "product_url"
        ]]
    )

    print(f"\nTop discounted items — {catalog.upper()} — Size {size}:")
    print(subset.head(10))

# --------------------------------------------------
# TELEGRAM
# --------------------------------------------------
if SEND_TELEGRAM:
    for catalog, cfg in CATALOGS.items():
        size = cfg["target_size"]
        size_col = SIZE_COLUMN[size]

        subset = final_df[
            (final_df["catalog"] == catalog) &
            (final_df[size_col] == 1)
            ].sort_values("discount_pct", ascending=False)

        if subset.empty:
            continue

        message = format_message(subset, catalog, size, TOP_N)

        if not DRY_RUN:
            send_telegram_message(message)
            print(f"\nTelegram message sent — {catalog.upper()}.")
        else:
            send_telegram_message(message)
            print(f"\nDRY RUN — Telegram not sent — {catalog.upper()}.")

conn.close()