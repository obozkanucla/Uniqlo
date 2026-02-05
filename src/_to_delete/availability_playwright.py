from playwright.sync_api import sync_playwright
from datetime import datetime

def fetch_size_availability(product_id: str) -> dict:
    url = f"https://www.uniqlo.com/uk/en/products/E{product_id}"
    sizes = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=30000)
        page.wait_for_selector("div.size-chip-wrapper")

        for chip in page.query_selector_all("div.size-chip-wrapper"):
            label = chip.inner_text().strip()
            strike = chip.query_selector("div.strike")
            sizes[label] = 0 if strike else 1

        browser.close()

    return {
        "observed_at": datetime.utcnow().isoformat(),
        "product_id": product_id,
        "color": "default",
        "sizes": sizes
    }

from datetime import datetime

def fetch_sku_availability_with_colors(page, product_id: str):
    url = f"https://www.uniqlo.com/uk/en/products/E{product_id}"
    page.goto(url, timeout=60000)

    # Accept cookies if present
    try:
        page.wait_for_selector("#onetrust-accept-btn-handler", timeout=5000)
        page.click("#onetrust-accept-btn-handler")
    except:
        pass

    # Kill ALL known blocking overlays
    page.add_style_tag(content="""
    #onetrust-consent-sdk,
    .template-base-sticky-container,
    #attentive_overlay,
    iframe#attentive_creative {
        pointer-events: none !important;
        display: none !important;
        visibility: hidden !important;
    }
    """)

    page.wait_for_selector("ul.collection-list-horizontal", timeout=20000)

    results = []
    observed_at = datetime.utcnow().isoformat()

    color_chips = page.locator(
        "ul.collection-list-horizontal button[data-testid='ITOChip']"
    )

    for i in range(color_chips.count()):
        color_chip = color_chips.nth(i)

        if color_chip.get_attribute("aria-disabled") == "true":
            continue

        color_id = color_chip.get_attribute("id")
        if not color_id:
            continue

        color = color_id.split("-")[0]

        # Force click to bypass any residual overlays
        # Force horizontal scroll so the chip is centered
        chip_handle = color_chip.element_handle()
        if not chip_handle:
            continue
        page.evaluate(
            """(chip) => {
                const container = chip.closest('ul');
                const chipRect = chip.getBoundingClientRect();
                const contRect = container.getBoundingClientRect();
                container.scrollLeft += (chipRect.left - contRect.left) - contRect.width / 2;
            }""",
            color_chip,
        )

        page.wait_for_timeout(100)
        color_chip.click(force=True)
        page.wait_for_timeout(300)
        page.wait_for_selector("div.size-chip-wrapper", timeout=5000)

        size_wrappers = page.locator("div.size-chip-wrapper")

        for j in range(size_wrappers.count()):
            wrapper = size_wrappers.nth(j)

            size = wrapper.locator(
                "div[data-testid='ITOTypography']"
            ).inner_text()

            has_strike = wrapper.locator("div.strike").count() > 0

            results.append({
                "observed_at": observed_at,
                "product_id": product_id,
                "color": color,
                "size": size,
                "is_available": 0 if has_strike else 1,
            })

    return results

from datetime import datetime

def fetch_size_availability_default_color(page, product_id: str):
    url = f"https://www.uniqlo.com/uk/en/products/E{product_id}"
    page.goto(url, timeout=60000)

    # Kill overlays deterministically
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

    # Accept cookies if present
    try:
        page.wait_for_selector("#onetrust-accept-btn-handler", timeout=3000)
        page.click("#onetrust-accept-btn-handler")
    except:
        pass

    page.wait_for_selector("div.size-chip-wrapper", timeout=20000)

    observed_at = datetime.utcnow().isoformat()
    results = []

    size_wrappers = page.locator("div.size-chip-wrapper")

    for i in range(size_wrappers.count()):
        wrapper = size_wrappers.nth(i)

        size = wrapper.locator(
            "div[data-testid='ITOTypography']"
        ).inner_text().strip()

        has_strike = wrapper.locator("div.strike").count() > 0

        results.append({
            "observed_at": observed_at,
            "product_id": product_id,
            "size": size,
            "is_available": 0 if has_strike else 1,
        })

    return results