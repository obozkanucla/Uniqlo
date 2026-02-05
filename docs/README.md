# Uniqlo Sale Monitor

A fully automated system that:
- scrapes Uniqlo UK sale pages
- stores historical snapshots
- detects meaningful changes
- notifies users based on personal preferences

Designed to run unattended via GitHub Actions.

---

## Architecture Overview
Scraper → Observations → Detectors → Events → Notifier → Users
Each stage has a **single responsibility**.

---

## 1. Scraper (`uniqlo_scraper.py`)

**Purpose**
- Collects raw sale data from Uniqlo
- One row per product, per scrape, per catalog (men / women)

**Stores**
- product_id
- prices
- discount %
- size availability
- catalog
- scrape_id + scraped_at

**Table**
```sql
uniqlo_sale_observations

2. Detectors (src/events/*)

Purpose
	•	Turn raw observations into objective events

Examples:
	•	ITEM_COUNT_INCREASE
	•	RARE_DEEP_DISCOUNT

Detectors:
	•	do NOT know about users
	•	do NOT send messages
	•	only write to uniqlo_events

Table