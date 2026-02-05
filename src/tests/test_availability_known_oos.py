from src._to_delete.uniqlo_scraper import fetch_size_availability

def test_known_out_of_stock():
    # PUFFERTECH Parka – confirmed OOS in UI
    sizes = fetch_size_availability("480064")

    assert sizes == {
        "XS": 0,
        "S": 0,
        "M": 0,
        "L": 0,
        "XL": 0,
    }