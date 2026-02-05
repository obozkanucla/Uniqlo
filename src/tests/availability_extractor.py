from playwright.sync_api import sync_playwright

def fetch_size_availability(product_id: str) -> dict:
    url = f"https://www.uniqlo.com/uk/en/products/E{product_id}"

    availability = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(url, timeout=30000)

        # wait for size chips to render
        page.wait_for_selector("div.size-chip-wrapper", timeout=15000)

        chips = page.query_selector_all("div.size-chip-wrapper")

        for chip in chips:
            # size label
            label_el = chip.query_selector("button div[data-testid='ITOTypography']")
            if not label_el:
                continue

            size = label_el.inner_text().strip()

            # strike indicates unavailable
            strike_el = chip.query_selector("div.strike")
            is_available = 0 if strike_el else 1

            availability[size] = is_available

        browser.close()

    if not availability:
        raise RuntimeError(f"No size chips parsed for {product_id}")

    return availability

if __name__ == "__main__":
    # manual test
    # pid = "478730"
    pid_list = ["478578", "478730", "479764"]
    for pid in pid_list:
        print(fetch_size_availability(pid))