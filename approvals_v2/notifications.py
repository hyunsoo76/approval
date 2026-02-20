from typing import List
from .models import TelegramRecipient


def get_active_recipients(role: str, *, name: str = "", department: str = "") -> List[TelegramRecipient]:
    """
    role 기준으로 DM 대상자를 찾는다.
    - 담당(drafter)은 department+name 우선, 없으면 name만 매칭
    - 총무/회장은 role + is_active 기준
    """
    qs = TelegramRecipient.objects.filter(role=role, is_active=True)

    if role == TelegramRecipient.ROLE_DRAFTER:
        # 운영 확정: drafter는 name만으로 매칭
        if name:
            return list(qs.filter(name=name))
        return []


    return list(qs)

def route_telegram_notifications(
    *,
    template_code: str,
    event: str,
    drafter_name: str,
    drafter_department: str,
    actor_role: str = "",
) -> dict:
    """
    알림을 '누구에게 보낼지'만 결정한다. (실제 발송 X)
    """

    ADMIN_FINAL = "ADMIN_FINAL"                 # 담당 -> 총무(전결)
    NORMAL = "NORMAL"                           # 담당 -> 총무 -> 회장
    ADMIN_TO_CHAIR = "ADMIN_TO_CHAIR"           # 총무 -> 회장
    ADMIN_TO_AUDITOR_CHAIR = "ADMIN_TO_AUDITOR_CHAIR"  # 총무 -> 감사 -> 회장

    # ✅ 요구사항: v2 모든 주요 이벤트를 "그룹방에도" 보내기
    FORCE_GROUP_EVENTS = {"submit", "approve", "reject"}

    def with_group(payload: dict) -> dict:
        if event in FORCE_GROUP_EVENTS:
            payload["group"] = True
        return payload

    if template_code == ADMIN_FINAL:
        if event == "submit":
            return with_group({"dm_roles": [TelegramRecipient.ROLE_ADMIN], "dm_drafter": False, "group": False})
        if event == "approve":
            return with_group({"dm_roles": [], "dm_drafter": True, "group": False})
        if event == "reject":
            return with_group({"dm_roles": [], "dm_drafter": True, "group": False})

    if template_code == NORMAL:
        if event == "submit":
            return with_group({"dm_roles": [TelegramRecipient.ROLE_ADMIN], "dm_drafter": False, "group": False})
        if event == "approve":
            # 기존엔 admin/chairman일 때만 group=True 였는데, 이제 항상 group=True
            return with_group({"dm_roles": [], "dm_drafter": False, "group": True})
        if event == "reject":
            # 기존 정책 유지하되, 그룹도 항상 보냄
            # (원하면 dm_drafter도 유지)
            if actor_role == TelegramRecipient.ROLE_CHAIRMAN:
                return with_group({"dm_roles": [], "dm_drafter": False, "group": True})
            return with_group({"dm_roles": [], "dm_drafter": True, "group": False})

    if template_code in (ADMIN_TO_CHAIR, ADMIN_TO_AUDITOR_CHAIR):
        if event == "submit":
            return with_group({"dm_roles": [], "dm_drafter": False, "group": True})
        if event == "approve":
            return with_group({"dm_roles": [], "dm_drafter": False, "group": True})
        if event == "reject":
            if actor_role == TelegramRecipient.ROLE_CHAIRMAN:
                return with_group({"dm_roles": [], "dm_drafter": False, "group": True})
            return with_group({"dm_roles": [], "dm_drafter": True, "group": False})

    return with_group({"dm_roles": [], "dm_drafter": False, "group": False})

from .telegram import send_dm, send_group


def dispatch_notifications(
    *,
    template_code: str,
    event: str,
    drafter_name: str,
    drafter_department: str,
    text: str,
    actor_role: str = "",
) -> dict:
    """
    라우터 결과를 기반으로 실제 발송(현재는 stub print)을 수행한다.
    return: 실행 결과 요약(dict)
    """
    routing = route_telegram_notifications(
        template_code=template_code,
        event=event,
        drafter_name=drafter_name,
        drafter_department=drafter_department,
        actor_role=actor_role,
    )

    sent = {"dm": [], "group": False, "routing": routing}

    # 1) role 기반 DM (총무/회장 등)
    for role in routing.get("dm_roles", []):
        recipients = get_active_recipients(role)
        for r in recipients:
            ok = send_dm(r.chat_id, text)
            sent["dm"].append({"role": role, "chat_id": r.chat_id, "ok": ok})

    # 2) 담당(기안자) DM
    if routing.get("dm_drafter"):
        drafters = get_active_recipients(
            TelegramRecipient.ROLE_DRAFTER,
            name=drafter_name,
            department=drafter_department,
        )
        for r in drafters:
            ok = send_dm(r.chat_id, text)
            sent["dm"].append({"role": "drafter", "chat_id": r.chat_id, "ok": ok})

    # 3) 단톡방
    if routing.get("group"):
        ok = send_group(text)
        sent["group"] = ok

    return sent

