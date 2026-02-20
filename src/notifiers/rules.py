import os
from dotenv import load_dotenv
load_dotenv()

USER_NOTIFICATION_RULES = {
    "burak": {
        "chat_id": os.getenv("TELEGRAM_CHAT_ID_BURAK"),
        "events": {
            "RARE_DEEP_DISCOUNT": {
                "women": {
                    "sizes": ["S", "XS"], #
                    "colors": None
                },
                "men": {
                    "sizes": ["M", "L"],# "XL", "32inch", "33inch"],
                    "colors": None
                }
            }
        }
    },
    "beste": {
        "chat_id": os.getenv("TELEGRAM_CHAT_ID_BESTE"),
        "events": {
            "RARE_DEEP_DISCOUNT": {
                "women": {
                    "sizes": ["S", "XS"],
                    "colors": None
                },
                "men": {
                    "sizes": ["XL", "XXL"],  #"32inch", "33inch"],
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
                    "colors": None #["BLACK", "NAVY"]
                },
                "men": {
                    "sizes": ["XL", "XXL"],  # "32inch", "33inch"],
                    "colors": None
                }
            }
        }
    }
}
