import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
import os
import sqlite3
from dotenv import load_dotenv

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
URL = "https://www.uniqlo.com/uk/en/feature/sale/men"
OUT_FILE = Path("uniqlo_sale_daily.csv")

DB_PATH = Path("db/uniqlo.sqlite")
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
    scraped_at TEXT NOT NULL,
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
    PRIMARY KEY (scraped_at, product_id)
)
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


def format_message(df, top_n=5):
    lines = ["UNIQLO UK — Deepest Discounts (Medium available)\n"]

    for i, row in enumerate(df.head(top_n).itertuples(), start=1):
        lines.append(
            f"{i}. {row.name}\n"
            f"   {row.discount_pct}% off "
            f"({row.original_price} → {row.sale_price})\n"
            f"   {row.product_url}\n"
        )

    return "\n".join(lines)

# --------------------------------------------------
# SCRAPE
# --------------------------------------------------
print("Fetching page HTML…")
r = requests.get(URL, headers=HEADERS, timeout=15)
r.raise_for_status()

soup = BeautifulSoup(r.text, "html.parser")
tiles = soup.select("div.product-tile")
print(f"Product tiles found: {len(tiles)}")

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
    raise RuntimeError("❌ No sale products extracted")

# --------------------------------------------------
# PRICES
# --------------------------------------------------
df["sale_price_num"] = df["sale_price"].str.replace(r"[^\d.]", "", regex=True).astype(float)
df["original_price_num"] = df["original_price"].str.replace(r"[^\d.]", "", regex=True).astype(float)

df["discount_pct"] = (
    (df["original_price_num"] - df["sale_price_num"])
    / df["original_price_num"]
    * 100
).round(2)

# --------------------------------------------------
# SIZE AVAILABILITY
# --------------------------------------------------
sizes = df["product_url"].apply(size_availability)

df["xs_available"] = sizes.apply(lambda x: x["XS"])
df["s_available"]  = sizes.apply(lambda x: x["S"])
df["m_available"]  = sizes.apply(lambda x: x["M"])
df["l_available"]  = sizes.apply(lambda x: x["L"])
df["xl_available"] = sizes.apply(lambda x: x["XL"])

# --------------------------------------------------
# SQLITE WRITE
# --------------------------------------------------
if WRITE_SQLITE and not DRY_RUN:
    df_to_store = df.copy()
    df_to_store["scraped_at"] = datetime.utcnow().isoformat()

    df_to_store[[
        "scraped_at",
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
# RESULT VIEW
# --------------------------------------------------
result = (
    df[df["m_available"] == 1]
    .sort_values("discount_pct", ascending=False)
    .loc[:, [
        "product_id",
        "name",
        "discount_pct",
        "sale_price",
        "original_price",
        "product_url"
    ]]
)

print("\nTop discounted items with Medium available:")
print(result.head(10))

# --------------------------------------------------
# TELEGRAM
# --------------------------------------------------
if SEND_TELEGRAM and not result.empty:
    message = format_message(result, TOP_N)
    print("\nTelegram message preview:\n")
    print(message)

    if not DRY_RUN:
        send_telegram_message(message)
        print("\nTelegram message sent.")
    else:
        send_telegram_message(message)
        print("\nDRY RUN — Telegram not sent")

# --------------------------------------------------
# CSV
# --------------------------------------------------
if WRITE_CSV and not DRY_RUN:
    df.to_csv(
        OUT_FILE,
        mode="a",
        header=not OUT_FILE.exists(),
        index=False
    )
    print(f"\nCSV written: {OUT_FILE.resolve()}")
else:
    print("DRY RUN — CSV not written")

conn.close()