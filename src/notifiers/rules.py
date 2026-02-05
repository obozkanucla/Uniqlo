import os

USER_NOTIFICATION_RULES = {
    "burak": {
        "chat_id": os.getenv("TELEGRAM_CHAT_ID_BURAK"),
        "events": {
            "RARE_DEEP_DISCOUNT": {
                "men": {
                    "sizes": ["M", "32inch", "33inch"],
                    "colors": None
                }
            }
        }
    },
    "muge": {
        "chat_id": os.getenv("TELEGRAM_CHAT_ID_MUGE"),
        "events": {
            "RARE_DEEP_DISCOUNT": {
                "women": {
                    "sizes": ["XS", "S"],
                    "colors": ["BLACK", "NAVY"]
                }
            }
        }
    }
}
