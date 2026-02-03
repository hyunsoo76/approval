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
        if department and name:
            exact = qs.filter(department=department, name=name)
            if exact.exists():
                return list(exact)

        if name:
            by_name = qs.filter(name=name)
            if by_name.exists():
                return list(by_name)

        return []

    return list(qs)

def route_telegram_notifications(
    *,
    template_code: str,
    event: str,
    drafter_name: str,
    drafter_department: str,
) -> dict:
    """
    알림을 '누구에게 보낼지'만 결정한다. (실제 발송 X)
    return 예시:
      {
        "dm_roles": ["admin"],              # DM 보낼 대상 role 목록
        "dm_drafter": True/False,           # 담당(기안자)에게 DM 보낼지
        "group": True/False,                # 단톡방 알림 보낼지
      }

    정책(확정):
    - 총무전결(ADMIN_FINAL):
        submit: 총무 DM, 단톡방 X
        approve(총무 승인=최종): 담당 DM, 단톡방 X
    - 일반품의(NORMAL):
        submit: 총무 DM, 단톡방 X
        approve(총무 승인 후 다음=회장 단계): 단톡방 O
        approve(회장 최종): 단톡방 O
      * 여기서는 event 수준만 결정하고, "현재 결재자가 누구인지"는 다음 단계에서 연결할 때 구분한다.
    """
    # 템플릿 코드(우리가 정한 명칭)
    ADMIN_FINAL = "ADMIN_FINAL"   # 담당 -> 총무(전결)
    NORMAL = "NORMAL"             # 담당 -> 총무 -> 회장
    ADMIN_TO_CHAIR = "ADMIN_TO_CHAIR"  # 총무 -> 회장 (필요시)

    if template_code == ADMIN_FINAL:
        if event == "submit":
            return {"dm_roles": [TelegramRecipient.ROLE_ADMIN], "dm_drafter": False, "group": False}
        if event == "approve":
            # 총무전결의 approve는 "최종 완료"이므로 담당에게만 DM
            return {"dm_roles": [], "dm_drafter": True, "group": False}
        if event == "reject":
            # 반려도 담당에게만 DM (원하면 admin도 같이 보낼 수 있음)
            return {"dm_roles": [], "dm_drafter": True, "group": False}

    if template_code == NORMAL:
        if event == "submit":
            return {"dm_roles": [TelegramRecipient.ROLE_ADMIN], "dm_drafter": False, "group": False}
        if event == "approve":
            # NORMAL에서 approve는 단계에 따라 group이 나뉘지만,
            # 다음 단계 연결에서 "총무 승인"인지 "회장 승인"인지 판단 후 group=True로 보낸다.
            return {"dm_roles": [], "dm_drafter": False, "group": True}
        if event == "reject":
            return {"dm_roles": [], "dm_drafter": True, "group": False}

    if template_code == ADMIN_TO_CHAIR:
        if event == "submit":
            return {"dm_roles": [], "dm_drafter": False, "group": True}
        if event == "approve":
            return {"dm_roles": [], "dm_drafter": False, "group": True}
        if event == "reject":
            return {"dm_roles": [], "dm_drafter": True, "group": False}

    # 기본값: 조용히(로그만) — 운영 정책에 맞춰 조정 가능
    return {"dm_roles": [], "dm_drafter": False, "group": False}
