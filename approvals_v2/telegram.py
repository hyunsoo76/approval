import os
from typing import Optional


def send_dm(chat_id: str, text: str) -> bool:
    """
    v2 전용 DM 발송 래퍼.
    아직 실제 텔레그램 전송은 연결하지 않고, 호출 형태만 고정한다.
    다음 단계에서 approvals(v1)의 send_telegram() 또는 requests 호출로 연결한다.
    """
    # 임시: 콘솔 확인용
    print(f"📩 [DM] to={chat_id} text={text}")

    # TODO: 실제 전송 연결 (다음 단계)
    return True


def send_group(text: str) -> bool:
    """
    v2 전용 단톡방 발송 래퍼.
    """
    group_chat_id = os.environ.get("TELEGRAM_GROUP_CHAT_ID", "").strip()
    # 임시: 콘솔 확인용
    print(f"📣 [GROUP] to={group_chat_id or '(missing TELEGRAM_GROUP_CHAT_ID)'} text={text}")

    # TODO: 실제 전송 연결 (다음 단계)
    return True
