# src/notifications/rules.py
import os

USER_NOTIFICATION_RULES = {
    "burak": {
        "chat_id": os.getenv("TELEGRAM_CHAT_ID_BURAK"),
        "events": {
            "RARE_DEEP_DISCOUNT": {
                "men":   {"size": ["M"]},
            }
        }
    },
    "muge": {
        "chat_id": os.getenv("TELEGRAM_CHAT_ID_MUGE"),
        "events": {
            "RARE_DEEP_DISCOUNT": {
                "women": {"size": ["XS", "S"]},
            }
        }
    }
}