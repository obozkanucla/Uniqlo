import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import date
from pathlib import Path
import os
from dotenv import load_dotenv


# Load .env from project root
load_dotenv()


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEND_TELEGRAM = True          # master switch
TOP_N = 5

if SEND_TELEGRAM and (not BOT_TOKEN or not CHAT_ID):
    raise RuntimeError("Telegram enabled but BOT_TOKEN or CHAT_ID missing")

CHAT_ID = int(CHAT_ID)

URL = "https://www.uniqlo.com/uk/en/feature/sale/men"
DRY_RUN = True
OUT_FILE = Path("uniqlo_sale_daily.csv")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html",
}

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

def medium_available(product_url):
    r = requests.get(product_url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")

    for btn in soup.select("button"):
        if btn.get_text(strip=True) == "M":
            return btn.get("aria-disabled") == "false"

    return False

print("Fetching page HTML…")
r = requests.get(URL, headers=HEADERS, timeout=15)
r.raise_for_status()

soup = BeautifulSoup(r.text, "html.parser")

tiles = soup.select("div.product-tile")
print(f"Product tiles found: {len(tiles)}")

rows = []

for t in tiles:
    try:
        # -----------------------
        # PRODUCT ID (from image)
        # -----------------------
        img = t.select_one("img[src*='imagesgoods']")
        if not img:
            continue

        m = re.search(r"imagesgoods/(\d+)/", img["src"])
        if not m:
            continue

        product_id = m.group(1)

        # -----------------------
        # PRODUCT NAME
        # -----------------------
        name_el = t.select("div[data-testid='ITOTypography']")
        name = name_el[1].get_text(strip=True) if len(name_el) >= 2 else None

        # -----------------------
        # PRICES
        # -----------------------
        sale_el = t.select_one(".ito-red500")
        original_el = t.select_one(".strikethrough")

        if not sale_el or not original_el:
            continue

        sale_price = sale_el.get_text(strip=True)
        original_price = original_el.get_text(strip=True)

        rows.append({
            "date_scraped": date.today().isoformat(),
            "product_id": product_id,
            "name": name,
            "sale_price": sale_price,
            "original_price": original_price,
            "product_url": f"https://www.uniqlo.com/uk/en/products/{product_id}"
        })

    except Exception:
        continue


df = pd.DataFrame(rows)

print("\nDataFrame shape:", df.shape)
print(df.head(5))

if df.empty:
    raise RuntimeError("❌ No sale products extracted")

# ------------------
# PRICE NORMALIZATION + DISCOUNT %
# ------------------
df["sale_price_num"] = (
    df["sale_price"]
    .str.replace(r"[^\d.]", "", regex=True)
    .astype(float)
)

df["original_price_num"] = (
    df["original_price"]
    .str.replace(r"[^\d.]", "", regex=True)
    .astype(float)
)

df["discount_pct"] = (
    (df["original_price_num"] - df["sale_price_num"])
    / df["original_price_num"]
    * 100
).round(2)

df = df.sort_values("discount_pct", ascending=False).reset_index(drop=True)


# ------------------
# New item detection
# ------------------
if OUT_FILE.exists() and OUT_FILE.stat().st_size > 0:
    try:
        prev = pd.read_csv(OUT_FILE, usecols=["product_id"])
        new_items = df[~df["product_id"].isin(prev["product_id"])]
        print(f"\nNew products today: {len(new_items)}")
    except Exception:
        print("\nExisting CSV unreadable — treating as first run")
        new_items = df
else:
    print("\nFirst run — all items are new")
    new_items = df

# ------------------
# MEDIUM SIZE AVAILABILITY
# ------------------
df["medium_available"] = df["product_url"].apply(medium_available)

# ------------------
# FINAL RESULT:
# Medium available, sorted by discount %
# ------------------
result = (
    df[df["medium_available"]]
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


# ------------------
# TELEGRAM BROADCAST
# ------------------
if SEND_TELEGRAM and not result.empty:
    message = format_message(result, TOP_N)
    print("\nTelegram message preview:\n")
    print(message)

    if DRY_RUN:
        send_telegram_message(message)
        print("\nTelegram message sent.")
    else:
        print("\nDRY RUN — Telegram message not sent.")

# ------------------
# Write
# ------------------
if DRY_RUN:
    print("\nDRY RUN — CSV not written")
else:
    df.to_csv(
        OUT_FILE,
        mode="a",
        header=not OUT_FILE.exists(),
        index=False
    )
    print(f"\nCSV written: {OUT_FILE.resolve()}")