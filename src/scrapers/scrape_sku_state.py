from playwright.sync_api import sync_playwright
from datetime import datetime
import sqlite3
import time


# --------------------------------------------------
# DOM helpers
# --------------------------------------------------
def read_sku_path(page):
    return page.evaluate("""
        () => window.location.pathname
    """)

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
    Returns enabled color chips only.
    Guaranteed to exclude size chips.
    """
    return page.evaluate("""
        () => Array.from(
            document.querySelectorAll(
                "button[data-testid='ITOChip'] img[src*='/chip/goods_']"
            )
        ).map(img => {
            const btn = img.closest("button");
            if (!btn) return null;
            if (btn.getAttribute("aria-disabled") === "true") return null;

            return {
                id: btn.id,
                color_code: btn.getAttribute("value"), // e.g. "19"
                color_label: img.getAttribute("alt")   // e.g. "WINE"
            };
        }).filter(Boolean);
    """)

def select_color(page, color_id):
    page.evaluate("""
        (id) => {
            const btn = document.getElementById(id);
            if (!btn) return;
            btn.click();
        }
    """, color_id)

    page.wait_for_function("""
        () => document.querySelector('.fr-ec-price-text--color-promotional')
    """, timeout=3000)

def read_price(page):
    return page.evaluate("""
        () => {
            const saleEl = document.querySelector(
                ".fr-ec-price-text--color-promotional"
            );
            const origEl = document.querySelector(
                ".fr-ec-price__strike-through"
            );

            if (!saleEl || !origEl) return null;

            const clean = t =>
                parseFloat(t.replace(/[^0-9.]/g, ""));

            const sale = clean(saleEl.textContent);
            const original = clean(origEl.textContent);

            if (!sale || !original || sale >= original) return null;

            return {
                sale_price: sale,
                original_price: original,
                discount_pct: Math.round(
                    (original - sale) / original * 10000
                ) / 100
            };
        }
    """)

def read_sizes(page):
    return page.evaluate("""
        () => Array.from(document.querySelectorAll("div.size-chip-wrapper"))
            .map(w => {
                const btn = w.querySelector("button");
                if (!btn) return null;

                const sizeLabel = btn.innerText.trim();
                const sizeCode = btn.getAttribute("value"); // <-- FIX

                if (!sizeLabel || !sizeCode) return null;

                return {
                    size_label: sizeLabel,     // "M", "30inch"
                    size_code: sizeCode,       // "002", "027"
                    is_available: w.querySelector("div.strike") ? 0 : 1
                };
            })
            .filter(Boolean);
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
    log(conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall())
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
        browser = p.chromium.launch(headless=True) ##
        context = browser.new_context()
        page = context.new_page()

        for idx, (catalog, product_id, source_variant_id, url) in enumerate(variants, 1):
            log(f"[SKU] [{idx}/{len(variants)}] {source_variant_id}")
            start = time.time()

            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_selector(
                    "button[data-testid='ITOChip'] img",
                    timeout=8000
                )
                # html = page.evaluate("""
                #                      () => {
                #                          return Array.from(
                #                              document.querySelectorAll("[data-testid='ITOChip']")
                #                          ).map(el => ({
                #                              tag: el.tagName,
                #                              aria: el.getAttribute("aria-label"),
                #                              text: el.innerText,
                #                              role: el.getAttribute("role"),
                #                              disabled: el.getAttribute("aria-disabled")
                #                          }));
                #                      }
                #                      """)
                #
                # log(f"[DEBUG] CHIP DUMP {variant_id}: {html}")
                kill_overlays(page)

                try:
                    page.click("#onetrust-accept-btn-handler", timeout=3000)
                except:
                    pass
                page.wait_for_selector(
                    "button[data-testid='ITOChip'] img[src*='/chip/goods_']",
                    timeout=8000
                )
                colors = get_colors(page)

                if not colors:
                    log(f"[SKU] {source_variant_id}: no colors found")
                    continue

                for color in colors:
                    select_color(page, color["id"])
                    sku_path = read_sku_path(page)

                    if not sku_path or "/products/" not in sku_path:
                        log(f"[WARN] unresolved SKU for {source_variant_id}")
                        continue

                    price = read_price(page)
                    log(
                        f"[DEBUG] PRICE {source_variant_id} "
                        f"{color['color_label']} → {price}"
                    )
                    if not price:
                        continue  # HARD SKIP: no discounted price

                    sizes = read_sizes(page)
                    if not sizes:
                        continue

                    for s in sizes:
                        log(f"[DEBUG] INSERT → "
                            f"{source_variant_id} "
                            f"{color['color_label']} "
                            f"{s['size_label']} "
                            f"£{price}")
                        rows.append((
                            observed_at,
                            catalog,
                            product_id,
                            source_variant_id,
                            sku_path,
                            color["color_code"],
                            color["color_label"],
                            s["size_code"],
                            s["size_label"],
                            price["sale_price"],
                            price["original_price"],
                            price["discount_pct"],
                            s["is_available"],
                        ))

            except Exception as e:
                log(f"[WARN] {source_variant_id} failed: {e}")

            finally:
                elapsed = time.time() - start
                log(f"[SKU] {source_variant_id} elapsed {elapsed:.1f}s")
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
                source_variant_id,
                sku_path,
                color_code,
                color_label,
                size_code,
                size_label,
                sale_price,
                original_price,
                discount_pct,
                is_available
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    conn.commit()
    log("[SKU] SKU STATE scrape complete")