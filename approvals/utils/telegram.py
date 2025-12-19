import os
import requests

def send_telegram(text: str) -> None:
    token = os.environ.get("6817288295:AAH5EugUOcgdOMIkRnYG7mVE2TlUEfHFqBE")
    chat_id = os.environ.get("6954609314")

    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=5,
    )
