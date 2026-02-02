import requests

BOT_TOKEN = "8321047692:AAEJveuMgZNOl_8h_XpeS4OPJMsIAdWxG-Y"
CHAT_ID = 1146931365

r = requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    json={
        "chat_id": CHAT_ID,
        "text": "Automation test OK",
        "disable_web_page_preview": True
    }
)

print(r.status_code)
print(r.text)