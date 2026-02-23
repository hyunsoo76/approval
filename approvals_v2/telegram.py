import os
from typing import Optional

import requests


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _send_message(*, chat_id: str, text: str) -> bool:
    """
    텔레그램 sendMessage 호출.
    실패해도 예외로 서비스가 죽지 않게 하고 False 반환.
    """
    token = _env("TELEGRAM_BOT_TOKEN")
    if not token:
        print("⚠️ [TG] missing TELEGRAM_BOT_TOKEN")
        return False
    if not chat_id:
        print("⚠️ [TG] missing chat_id")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(
            url,
            data={"chat_id": chat_id, "text": text},
            timeout=5,
        )
        print(f"🔥 TG_HTTP status={r.status_code} body={r.text[:300]}")
        if r.status_code != 200:
            print(f"⚠️ [TG] sendMessage HTTP {r.status_code}: {r.text[:200]}")
            return False
        data = r.json()
        if not data.get("ok"):
            print(f"⚠️ [TG] sendMessage not ok: {str(data)[:200]}")
            return False
        return True
    except Exception as e:
        print(f"⚠️ [TG] sendMessage exception: {e}")
        return False


def send_dm(chat_id: str, text: str) -> bool:
    """
    v2 전용 DM 발송.
    """
    print("🔥 TG_RUNTIME_ENV:",
      "BOT=", bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
      "GRP=", bool(os.environ.get("TELEGRAM_GROUP_CHAT_ID")),
      "CHAT=", bool(os.environ.get("TELEGRAM_CHAT_ID")))
    
    print(f"📩 [DM] to={chat_id} text={text}")
    ok = _send_message(chat_id=str(chat_id).strip(), text=text)
    return ok


def send_group(text: str) -> bool:
    """
    v2 전용 단톡방 발송.
    """
    print("🔥 TG_RUNTIME_ENV:",
      "BOT=", bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
      "GRP=", bool(os.environ.get("TELEGRAM_GROUP_CHAT_ID")),
      "CHAT=", bool(os.environ.get("TELEGRAM_CHAT_ID")))
    
    group_chat_id = _env("TELEGRAM_GROUP_CHAT_ID")
    print(f"📣 [GROUP] to={group_chat_id or '(missing TELEGRAM_GROUP_CHAT_ID)'} text={text}")
    ok = _send_message(chat_id=group_chat_id, text=text)
    return ok