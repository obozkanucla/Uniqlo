import re, requests, pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import uuid

HEADERS = {"User-Agent": "Mozilla/5.0"}

CATALOGS = {
    "men": "https://www.uniqlo.com/uk/en/feature/sale/men",
    "women": "https://www.uniqlo.com/uk/en/feature/sale/women",
}

import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime

HEADERS = {"User-Agent": "Mozilla/5.0"}

CATALOGS = {
    "men": "https://www.uniqlo.com/uk/en/feature/sale/men",
    "women": "https://www.uniqlo.com/uk/en/feature/sale/women",
}

def scrape_catalog() -> pd.DataFrame:
    scraped_at = datetime.utcnow().isoformat()
    rows: list[dict] = []

    seen: set[tuple[str, str]] = set()   # ← ADD THIS

    for catalog, url in CATALOGS.items():
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        for tile in soup.select("div.product-tile"):
            img = tile.select_one("img[src*='imagesgoods']")
            if not img:
                continue

            m = re.search(r"imagesgoods/(\d{6})", img["src"])
            if not m:
                continue

            product_id = m.group(1)
            key = (catalog, product_id)

            if key in seen:              # ← DEDUPE HERE
                continue
            seen.add(key)

            sale_el = tile.select_one(".ito-red500")
            orig_el = tile.select_one(".strikethrough")
            if not sale_el or not orig_el:
                continue

            try:
                sale = float(re.sub(r"[^\d.]", "", sale_el.text))
                orig = float(re.sub(r"[^\d.]", "", orig_el.text))
            except ValueError:
                continue

            rows.append({
                "scraped_at": scraped_at,
                "catalog": catalog,
                "product_id": product_id,
                "name": tile.get_text(strip=True)[:200],
                "sale_price_num": sale,
                "original_price_num": orig,
                "discount_pct": round((orig - sale) / orig * 100, 2),
                "product_url": f"https://www.uniqlo.com/uk/en/products/E{product_id}",
            })

    return pd.DataFrame(rows)