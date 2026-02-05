from playwright.sync_api import sync_playwright
from src._to_delete.availability_playwright import (
    fetch_size_availability_default_color)

TEST_PRODUCTS = [
    "478578",  # mixed availability
    "478730",  # XL-only example
    "480064",  # mostly unavailable
]

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # use False for first run
        page = browser.new_page()

        for pid in TEST_PRODUCTS:
            print(f"\nPRODUCT {pid}")
            rows = fetch_size_availability_default_color(page, pid)
            for r in rows:
                print(r)

        browser.close()

if __name__ == "__main__":
    main()