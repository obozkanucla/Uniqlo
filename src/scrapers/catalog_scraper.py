from playwright.sync_api import sync_playwright
from datetime import datetime
import uuid
from urllib.parse import urljoin
import re

CATALOG_URLS = {
    "men": "https://www.uniqlo.com/uk/en/feature/sale/men",
    "women": "https://www.uniqlo.com/uk/en/feature/sale/women",
}

VARIANT_ID_RE = re.compile(r"(E\d{6}-\d{3})")
def extract_product_name_from_tile(a):
    return a.evaluate("""
        (a) => {
            const tile = a.closest('[class*="product-tile"]');
            if (!tile) return null;

            const nodes = Array.from(
                tile.querySelectorAll(
                    '.product-tile__content-area [data-testid="ITOTypography"]'
                )
            );

            // product name is the SECOND typography node
            if (nodes.length < 2) return null;

            const name = nodes[1].textContent.trim();
            return name || null;
        }
    """, a)


def scrape_catalog(conn, log=print):
    conn.execute("DELETE FROM uniqlo_sale_variants")
    conn.commit()

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

                tiles = page.query_selector_all('a[href^="/uk/en/products/E"]')
                count = len(tiles)

                if count == last_count:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                    last_count = count

            log(f"[CATALOG] {catalog}: {last_count} product links")

            # ------------------------------------------------
            # Extract variant + deterministic product name
            # ------------------------------------------------
            for a in page.query_selector_all('a[href^="/uk/en/products/E"]'):
                href = a.get_attribute("href")
                if not href:
                    continue

                m = VARIANT_ID_RE.search(href)
                if not m:
                    continue

                variant_id = m.group(1)
                product_id = variant_id[1:7]

                key = (catalog, variant_id)
                if key in seen_variants:
                    continue
                seen_variants.add(key)

                # 🔑 deterministic product name from tile
                name_el = a.query_selector('[data-testid="ITOTypography"]')
                product_name = (
                    name_el.inner_text().strip()
                    if name_el else None
                )
                product_name = extract_product_name_from_tile(a)
                # print(product_name)
                if not product_name:
                    log(f"[CATALOG][SKIP] no product name for {variant_id}")
                    continue

                rows.append((
                    scrape_id,
                    scraped_at,
                    catalog,
                    product_id,
                    variant_id,
                    urljoin("https://www.uniqlo.com", href.split("?")[0]),
                    product_name,
                ))

        browser.close()

    if not rows:
        log("[CATALOG] No variants found")
        return

    conn.executemany("""
        INSERT INTO uniqlo_sale_variants (
            scrape_id,
            scraped_at,
            catalog,
            product_id,
            variant_id,
            variant_url,
            name
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, rows)

    conn.commit()

    log(
        conn.execute("""
            SELECT catalog, COUNT(*)
            FROM uniqlo_sale_variants
            GROUP BY catalog
        """).fetchall()
    )