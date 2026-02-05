import re
import time
import json
import uuid
import sqlite3
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# --------------------------------------------------
# CONSTANTS
# --------------------------------------------------
CATALOGS = {
    "men": "https://www.uniqlo.com/uk/en/feature/sale/men",
    "women": "https://www.uniqlo.com/uk/en/feature/sale/women",
}

SIZES = ["XS", "S", "M", "L", "XL"]

HEADERS_HTML = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html",
}

HEADERS_CATALOG = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html",
}

# --------------------------------------------------
# ENV
# --------------------------------------------------
load_dotenv()

WRITE_SQLITE = True
DRY_RUN = False

# --------------------------------------------------
# PATHS
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "db" / "uniqlo.sqlite"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def normalize_product_id(raw_id: str) -> str | None:
    """
    Extract canonical 6-digit Uniqlo product ID.
    Examples:
      481006002 -> 481006
      480064    -> 480064
    """
    m = re.match(r"(\d{6})", raw_id)
    return m.group(1) if m else None


def fetch_product_availability(product_id: str) -> bool:
    """
    True  = orderable online
    False = out of stock (Notify Me)
    """

    import requests
    from bs4 import BeautifulSoup

    url = f"https://www.uniqlo.com/uk/en/products/E{product_id}"

    r = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    # Definitive signals
    if soup.find("button", string=lambda x: x and "ADD TO CART" in x.upper()):
        return True

    if soup.find("button", string=lambda x: x and "NOTIFY ME" in x.upper()):
        return False

    # Conservative default
    return False

# --------------------------------------------------
# DB
# --------------------------------------------------
def init_db(conn: sqlite3.Connection):
    conn.execute(
        """
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
        """
    )
    conn.commit()


# --------------------------------------------------
# SCRAPER
# --------------------------------------------------
def main():
    scrape_id = uuid.uuid4().hex
    scraped_at = datetime.utcnow().isoformat()

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    all_results = []

    for catalog, url in CATALOGS.items():
        print(f"\n=== Scraping catalog: {catalog} ===")

        r = requests.get(url, headers=HEADERS_CATALOG, timeout=15)
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

                product_id = normalize_product_id(m.group(1))
                if not product_id:
                    continue

                name_el = t.select("div[data-testid='ITOTypography']")
                name = name_el[1].get_text(strip=True) if len(name_el) >= 2 else None

                sale_el = t.select_one(".ito-red500")
                original_el = t.select_one(".strikethrough")
                if not sale_el or not original_el:
                    continue

                rows.append(
                    {
                        "catalog": catalog,
                        "product_id": product_id,
                        "name": name,
                        "sale_price": sale_el.get_text(strip=True),
                        "original_price": original_el.get_text(strip=True),
                        "product_url": f"https://www.uniqlo.com/uk/en/products/E{product_id}",
                    }
                )

            except Exception:
                continue

        df = pd.DataFrame(rows)
        if df.empty:
            continue

        df = df.drop_duplicates(subset=["product_id"]).reset_index(drop=True)

        # ---- prices
        df["sale_price_num"] = (
            df["sale_price"].str.replace(r"[^\d.]", "", regex=True).astype(float)
        )
        df["original_price_num"] = (
            df["original_price"].str.replace(r"[^\d.]", "", regex=True).astype(float)
        )
        df["discount_pct"] = (
            (df["original_price_num"] - df["sale_price_num"])
            / df["original_price_num"]
            * 100
        ).round(2)

        # ---- availability
        availability_rows = []
        for pid in df["product_id"]:
            availability_rows.append(fetch_size_availability(pid))
            time.sleep(0.15)

        availability_df = pd.DataFrame(availability_rows)
        df = pd.concat([df, availability_df], axis=1)

        df["scrape_id"] = scrape_id
        df["scraped_at"] = scraped_at

        all_results.append(df)

    if not all_results:
        print("No data scraped.")
        return

    final_df = pd.concat(all_results, ignore_index=True)

    if WRITE_SQLITE and not DRY_RUN:
        final_df.rename(
            columns={
                "XS": "xs_available",
                "S": "s_available",
                "M": "m_available",
                "L": "l_available",
                "XL": "xl_available",
            }
        ).to_sql(
            "uniqlo_sale_observations",
            conn,
            if_exists="append",
            index=False,
        )

    conn.close()


# --------------------------------------------------
# ENTRY POINT
# --------------------------------------------------
if __name__ == "__main__":
    main()