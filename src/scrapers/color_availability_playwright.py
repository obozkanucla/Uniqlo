from datetime import datetime
import sqlite3
from playwright.sync_api import sync_playwright


# --------------------------------------------------
# Helpers
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
    return page.evaluate("""
        () => Array.from(
            document.querySelectorAll(
                "ul.collection-list-horizontal button[data-testid='ITOChip']"
            )
        )
        .filter(b => b.getAttribute("aria-disabled") !== "true")
        .filter(b => typeof b.id === "string" && b.id.includes("-"))
        .map(b => {
            const label = b.id.split("-")[0].trim();
            if (!label) return null;
            return {
                id: b.id,
                value: b.getAttribute("value"),
                label
            };
        })
        .filter(Boolean)
    """)


def select_color(page, color_id):
    page.evaluate("""
        (id) => {
            const btn = document.getElementById(id);
            if (!btn) return;
            btn.scrollIntoView({ block: "center" });
            btn.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
            btn.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
            btn.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        }
    """, color_id)


def wait_for_size_refresh(page):
    page.wait_for_function("""
        () => {
            const sizes = document.querySelectorAll("div.size-chip-wrapper");
            return sizes.length > 0 &&
                   Array.from(sizes).every(
                     s => s.querySelector("[data-testid='ITOTypography']")
                   );
        }
    """, timeout=5000)


def read_sizes(page):
    return page.evaluate("""
        () => Array.from(
            document.querySelectorAll("div.size-chip-wrapper")
        ).map(w => ({
            size: w.querySelector("[data-testid='ITOTypography']").innerText.trim(),
            is_available: w.querySelector("div.strike") ? 0 : 1
        }))
    """)


# --------------------------------------------------
# Main extractor
# --------------------------------------------------

def fetch_sku_availability_with_colors(page, product_id: str):
    url = f"https://www.uniqlo.com/uk/en/products/E{product_id}"

    # Hard navigation bound
    page.goto(url, timeout=30000, wait_until="domcontentloaded")

    kill_overlays(page)

    # Accept cookies if present (best-effort)
    try:
        page.click("#onetrust-accept-btn-handler", timeout=3000)
    except:
        pass

    # If size chips never appear, product is non-standard → skip safely
    try:
        page.wait_for_selector("div.size-chip-wrapper", timeout=7000)
    except:
        return []

    observed_at = datetime.utcnow().isoformat()
    results = []

    colors = get_colors(page)

    # Fallback: sizes without colors (rare but real)
    if not colors:
        sizes = read_sizes(page)
        for s in sizes:
            results.append({
                "observed_at": observed_at,
                "product_id": product_id,
                "color": "DEFAULT",
                "size": s["size"],
                "is_available": s["is_available"],
            })
        return results

    for color in colors:
        try:
            select_color(page, color["id"])
            wait_for_size_refresh(page)
            sizes = read_sizes(page)
        except:
            continue

        for s in sizes:
            results.append({
                "observed_at": observed_at,
                "product_id": product_id,
                "color": color["label"],
                "size": s["size"],
                "is_available": s["is_available"],
            })

    return results


# --------------------------------------------------
# Test runner
# --------------------------------------------------

def main():
    product_ids = [
        "478578",
        "478730",
        "479764",
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        for pid in product_ids:
            print(f"\nPRODUCT {pid}")
            rows = fetch_sku_availability_with_colors(page, pid)
            for r in rows:
                print(r)

        browser.close()


# --------------------------------------------------
# Orchestrated DB scraper
# --------------------------------------------------

def scrape_sku_availability(conn: sqlite3.Connection, log, max_products: int | None = None):
    product_ids = [
        r[0] for r in conn.execute("""
            SELECT DISTINCT product_id
            FROM uniqlo_sale_observations
        """).fetchall()
    ]

    if max_products:
        product_ids = product_ids[:max_products]

    log(f"SKU scrape start — products: {len(product_ids)}")

    if not product_ids:
        log("No products found for SKU availability scrape")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        rows_to_insert = []

        for idx, pid in enumerate(product_ids, 1):
            log(f"[{idx}/{len(product_ids)}] SKU START {pid}")
            start = datetime.utcnow()

            try:
                rows = fetch_sku_availability_with_colors(page, pid)
                log(f"[{pid}] rows fetched: {len(rows)}")

                for r in rows:
                    if not r["color"]:
                        continue

                    rows_to_insert.append((
                        r["observed_at"],
                        r["product_id"],
                        r["color"],
                        r["size"],
                        r["is_available"],
                    ))

                log(f"[{pid}] rows staged")

            except Exception as e:
                log(f"[WARN] SKU scrape failed for {pid}: {e}")

            finally:
                elapsed = (datetime.utcnow() - start).total_seconds()
                log(f"[{pid}] elapsed {elapsed:.1f}s")
                page.goto("about:blank")

        browser.close()

    if rows_to_insert:
        log(f"Persisting {len(rows_to_insert)} SKU rows")
        conn.executemany("""
            INSERT OR REPLACE INTO uniqlo_sku_availability
            (observed_at, product_id, color, size, is_available)
            VALUES (?, ?, ?, ?, ?)
        """, rows_to_insert)
        conn.commit()

    log("SKU scrape end")


if __name__ == "__main__":
    main()