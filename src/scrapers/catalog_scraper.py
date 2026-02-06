from playwright.sync_api import sync_playwright
from datetime import datetime
import uuid
from urllib.parse import urljoin, urlparse
import re

CATALOG_URLS = {
    "men": "https://www.uniqlo.com/uk/en/feature/sale/men",
    "women": "https://www.uniqlo.com/uk/en/feature/sale/women",
}

VARIANT_ID_RE = re.compile(r"(E\d{6}-\d{3})")


def scrape_catalog(conn, log=print):
    scrape_id = uuid.uuid4().hex
    scraped_at = datetime.utcnow().isoformat()

    rows = []
    seen_variants = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for catalog, url in CATALOG_URLS.items():
            log(f"[CATALOG] Loading {catalog}")
            page.goto(url, timeout=30000, wait_until="domcontentloaded")

            # ------------------------------------------------
            # Infinite scroll until tile count stabilises
            # ------------------------------------------------
            last_count = 0
            stable_rounds = 0

            while stable_rounds < 3:
                page.mouse.wheel(0, 5000)
                page.wait_for_timeout(1500)

                links = page.query_selector_all(
                    'a[href^="/uk/en/products/E"]'
                )
                count = len(links)

                if count == last_count:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                    last_count = count

            log(f"[CATALOG] {catalog}: {last_count} product links")

            # ------------------------------------------------
            # Extract canonical variant URLs
            # ------------------------------------------------
            for a in page.query_selector_all(
                'a[href^="/uk/en/products/E"]'
            ):
                href = a.get_attribute("href")
                if not href:
                    continue

                m = VARIANT_ID_RE.search(href)
                if not m:
                    continue

                variant_id = m.group(1)
                full_url = urljoin("https://www.uniqlo.com", href.split("?")[0])

                key = (catalog, variant_id)
                if key in seen_variants:
                    continue
                seen_variants.add(key)

                rows.append((
                    scrape_id,
                    scraped_at,
                    catalog,
                    variant_id,
                    full_url,
                ))

        browser.close()

    if not rows:
        log("[CATALOG] No variants found")
        return

    conn.executemany(
        """
        INSERT OR IGNORE INTO uniqlo_sale_variants (
            scrape_id,
            scraped_at,
            catalog,
            variant_id,
            variant_url
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        rows,
    )

    conn.commit()
    log(conn.execute("""
                     SELECT catalog, COUNT (*)
                     FROM uniqlo_sale_observations
                     GROUP BY catalog
                     """).fetchall())