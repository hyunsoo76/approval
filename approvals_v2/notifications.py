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
