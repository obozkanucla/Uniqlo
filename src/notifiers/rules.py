import os
from dotenv import load_dotenv
load_dotenv()

USER_NOTIFICATION_RULES = {
    "burak": {
        "chat_id": os.getenv("TELEGRAM_CHAT_ID_BURAK"),
        "events": {
            "RARE_DEEP_DISCOUNT": {
                # "women": {
                #     "sizes": None, #["M", "32inch", "33inch"],
                #     "colors": None
                # },
                "men": {
                    "sizes": ["M", "32inch", "33inch"],
                    "colors": None
                }
            }
        }
    },
    # "muge": {
    #     "chat_id": os.getenv("TELEGRAM_CHAT_ID_MUGE"),
    #     "events": {
    #         "RARE_DEEP_DISCOUNT": {
    #             "women": {
    #                 "sizes": ["XS", "S"],
    #                 "colors": None #["BLACK", "NAVY"]
    #             }
    #         }
    #     }
    # }
}
