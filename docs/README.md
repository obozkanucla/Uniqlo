You’re right — that one wasn’t copy-pastable. Here it is clean, plain Markdown, ready to paste into README.md with zero edits.

⸻


# Uniqlo Sale Monitor

Automated monitoring of Uniqlo UK sale pages with event detection and user-specific Telegram alerts.

---

## Overview

This project continuously scrapes Uniqlo UK sale pages (men & women), stores every snapshot in SQLite, detects meaningful events, and notifies users based on **their own preferences**.

The system is designed to be:
- fully automated
- restart-safe
- idempotent
- extensible without refactors

---

## Architecture

Scraper → Observations → Event Detectors → Events → Notifier → Users

Each stage has a single responsibility.

---

## Scraper

**File:** `src/uniqlo_scraper.py`

Responsibilities:
- Scrape men and women sale pages
- Capture *all* items (not just interesting ones)
- Record:
  - prices
  - discount %
  - size availability
  - catalog (men / women)
- Persist snapshots to SQLite

Table created automatically:

uniqlo_sale_observations

Each run is uniquely identified by:
- `scrape_id`
- `scraped_at`

This allows historical analysis and change detection.

---

## Event Detection

**Directory:** `src/events/`

Detectors are **objective**.  
They do **not** know about users or notifications.

Example detectors:
- `ITEM_COUNT_INCREASE`
- `RARE_DEEP_DISCOUNT`

Each detector:
- reads from `uniqlo_sale_observations`
- emits factual events
- writes to `uniqlo_events`

Table created automatically:

uniqlo_events

---

## Rare Deep Discount Event

**Event type:** `RARE_DEEP_DISCOUNT`

Definition:
- Sale price < £10
- Discount ≥ 50%
- Size available
  - Men: M
  - Women: XS or S
- Evaluated on latest scrape only

Detected events are written once per scrape and catalog.

---

## Notification Rules

**File:** `src/notifications/rules.py`

Maps users to:
- Telegram chat IDs
- Event types
- Catalogs
- Size preferences

Example:

```python
USER_NOTIFICATION_RULES = {
    "burak": {
        "chat_id": "...",
        "events": {
            "RARE_DEEP_DISCOUNT": {
                "men": {"size": ["M"]},
            }
        }
    },
    "muge": {
        "chat_id": "...",
        "events": {
            "RARE_DEEP_DISCOUNT": {
                "women": {"size": ["XS", "S"]},
            }
        }
    }
}

Detectors do not apply these rules — the notifier does.

⸻

Notifier

File: src/notify_events.py

Responsibilities:
	•	Read recent events
	•	Apply user rules
	•	Enforce cooldowns (default: 24h per product per user)
	•	Send Telegram messages
	•	Persist sent notifications

Cooldown is enforced via:

uniqlo_notifications

This prevents repeated alerts for the same deal.

⸻

GitHub Actions

Workflow runs every 30 minutes.

Steps:
	1.	Restore SQLite DB from GitHub Release
	2.	Run scraper
	3.	Detect events
	4.	Notify users
	5.	Publish updated SQLite snapshot

SQLite is the canonical state of the system.

⸻

Design Principles
	•	Facts first: detection is objective
	•	Preferences later: notification is personal
	•	No manual SQL: schema created in Python
	•	Idempotent: safe to rerun anytime
	•	Extensible: new events or users require no rewrites

⸻

Status

Production-ready.

Next possible extensions:
	•	Per-user cooldown tuning
	•	Price-drop events
	•	Daily digests
	•	Friend-specific catalogs and sizes

---

If you want next:
- tighten the deep-discount logic further
- add a daily “summary mode”
- or visualize historical sale timing patterns