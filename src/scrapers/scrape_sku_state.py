from playwright.sync_api import sync_playwright
from datetime import datetime
import sqlite3
import time


# --------------------------------------------------
# DOM helpers
# --------------------------------------------------

def kill_overlays(page):
    page.add_style_tag(content="""
        #onetrust-consent-sdk,
        .template-base-sticky-container,
        #attentive_overlay,
        iframe {
            display: none !important;
            visibility: hidden !important;
            pointer-events: none !important;
        }
    """)


def get_colors(page):
    """
    Returns enabled color chips on a variant page.
    """
    return page.evaluate("""
        () => Array.from(
            document.querySelectorAll("button[data-testid='ITOChip']")
        )
        .filter(b => b.getAttribute("aria-disabled") !== "true")
        .map(b => ({
            id: b.id,
            label: b.getAttribute("value") || b.innerText.trim()
        }))
        .filter(c => c.id && c.label)
    """)


def select_color(page, color_id):
    page.evaluate("""
        (id) => {
            const btn = document.getElementById(id);
            if (!btn) return;
            btn.scrollIntoView({ block: "center" });
            btn.click();
        }
    """, color_id)


def wait_for_refresh(page):
    page.wait_for_timeout(800)


def read_price(page):
    """
    Reads price ONCE per color.
    Returns None if price is not discounted / not visible.
    """
    return page.evaluate("""
        () => {
            const sale = document.querySelector(".ito-red500");
            const orig = document.querySelector(".strikethrough");

            if (!sale || !orig) return null;

            const clean = t => parseFloat(t.replace(/[^\d.]/g, ""));

            const sale_p = clean(sale.innerText);
            const orig_p = clean(orig.innerText);

            if (!sale_p || !orig_p) return null;

            return {
                sale_price: sale_p,
                original_price: orig_p,
                discount_pct: Math.round((orig_p - sale_p) / orig_p * 10000) / 100
            };
        }
    """)


def read_sizes(page):
    """
    Reads size availability.
    """
    return page.evaluate("""
        () => Array.from(
            document.querySelectorAll("div.size-chip-wrapper")
        ).map(w => ({
            size: w.innerText.trim(),
            is_available: w.querySelector("div.strike") ? 0 : 1
        }))
    """)


# --------------------------------------------------
# Core scraper
# --------------------------------------------------

def scrape_sku_state(conn: sqlite3.Connection, log=print, max_variants=None):
    """
    Canonical SKU truth scraper.

    Populates uniqlo_sku_state with:
    - price per (variant, color)
    - availability per (variant, color, size)
    """

    variants = conn.execute("""
        SELECT catalog, product_id, variant_id, variant_url
        FROM uniqlo_sale_variants
        ORDER BY catalog, variant_id
    """).fetchall()

    if max_variants:
        variants = variants[:max_variants]

    if not variants:
        log("[SKU] No variants to scrape")
        return

    log(f"[SKU] Starting SKU STATE scrape — variants: {len(variants)}")

    rows = []
    observed_at = datetime.utcnow().isoformat()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        for idx, (catalog, product_id, variant_id, url) in enumerate(variants, 1):
            log(f"[SKU] [{idx}/{len(variants)}] {variant_id}")
            start = time.time()

            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                kill_overlays(page)

                try:
                    page.click("#onetrust-accept-btn-handler", timeout=3000)
                except:
                    pass

                colors = get_colors(page)

                if not colors:
                    log(f"[SKU] {variant_id}: no colors found")
                    continue

                for color in colors:
                    select_color(page, color["id"])
                    wait_for_refresh(page)

                    price = read_price(page)
                    if not price:
                        continue  # HARD SKIP: no discounted price

                    sizes = read_sizes(page)
                    if not sizes:
                        continue

                    for s in sizes:
                        rows.append((
                            observed_at,
                            catalog,
                            product_id,
                            variant_id,
                            color["label"],
                            s["size"],
                            price["sale_price"],
                            price["original_price"],
                            price["discount_pct"],
                            s["is_available"],
                        ))

            except Exception as e:
                log(f"[WARN] {variant_id} failed: {e}")

            finally:
                elapsed = time.time() - start
                log(f"[SKU] {variant_id} elapsed {elapsed:.1f}s")
                page.goto("about:blank")

        browser.close()

    if not rows:
        log("[SKU] No SKU rows collected")
        return

    log(f"[SKU] Persisting {len(rows)} SKU rows")

    conn.executemany("""
        INSERT OR REPLACE INTO uniqlo_sku_state (
            observed_at,
            catalog,
            product_id,
            variant_id,
            color_code,
            size,
            sale_price,
            original_price,
            discount_pct,
            is_available
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    conn.commit()
    log("[SKU] SKU STATE scrape complete")