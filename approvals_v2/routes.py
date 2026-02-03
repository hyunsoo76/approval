from django.utils import timezone
from .models import ApprovalRouteInstance, ApprovalRouteStepInstance, TelegramRecipient
from django.db import transaction

def build_route_for_approval(*, approval, template_code: str) -> ApprovalRouteInstance:
    """
    approval(기존 approvals.ApprovalRequest)에 대해 v2 결재라인 인스턴스를 생성한다.
    상신 후 수정 불가 원칙을 위해, 이미 route가 있으면 예외로 막는다.
    """
    if hasattr(approval, "route_v2"):
        raise ValueError("route already exists for this approval")

    route = ApprovalRouteInstance.objects.create(
        approval=approval,
        template_code=template_code,
        status=ApprovalRouteInstance.STATUS_IN_PROGRESS,
        current_order=1,
        submitted_at=timezone.now(),
    )

    # 템플릿별 결재 단계 정의(확정안 반영)
    if template_code == ApprovalRouteInstance.TEMPLATE_ADMIN_FINAL:
        steps = [
            (1, TelegramRecipient.ROLE_DRAFTER),
            (2, TelegramRecipient.ROLE_ADMIN),
        ]
    elif template_code == ApprovalRouteInstance.TEMPLATE_NORMAL:
        steps = [
            (1, TelegramRecipient.ROLE_DRAFTER),
            (2, TelegramRecipient.ROLE_ADMIN),
            (3, TelegramRecipient.ROLE_CHAIRMAN),
        ]
    elif template_code == ApprovalRouteInstance.TEMPLATE_ADMIN_TO_CHAIR:
        steps = [
            (1, TelegramRecipient.ROLE_ADMIN),
            (2, TelegramRecipient.ROLE_CHAIRMAN),
        ]
    else:
        raise ValueError(f"unknown template_code: {template_code}")

    for order, role in steps:
        ApprovalRouteStepInstance.objects.create(route=route, order=order, role=role)

    return route

def get_current_actor_role(route: ApprovalRouteInstance) -> str:
    """
    route.current_order에 해당하는 step의 role을 반환한다.
    """
    step = route.steps.filter(order=route.current_order).first()
    return step.role if step else ""

@transaction.atomic
def approve_current_step(
    *,
    route: ApprovalRouteInstance,
    acted_ip: str = "",
    acted_device: str = "",
    acted_anon_id: str = "",
) -> ApprovalRouteStepInstance:
    """
    현재 단계(route.current_order)를 승인 처리하고 다음 단계로 이동한다.
    마지막 단계 승인 시 route를 completed로 만든다.
    """
    step = route.steps.select_for_update().get(order=route.current_order)

    # 이미 처리된 단계면 그대로 반환(중복 클릭 방지)
    if step.state != ApprovalRouteStepInstance.STATE_PENDING:
        return step

    step.state = ApprovalRouteStepInstance.STATE_APPROVED
    step.acted_at = timezone.now()
    step.acted_ip = acted_ip or None
    step.acted_device = acted_device
    step.acted_anon_id = acted_anon_id
    step.save(update_fields=["state", "acted_at", "acted_ip", "acted_device", "acted_anon_id"])

    # 다음 단계가 있으면 current_order 증가
    has_next = route.steps.filter(order=route.current_order + 1).exists()
    if has_next:
        route.current_order = route.current_order + 1
        route.save(update_fields=["current_order", "updated_at"])
    else:
        route.status = ApprovalRouteInstance.STATUS_COMPLETED
        route.completed_at = timezone.now()
        route.save(update_fields=["status", "completed_at", "updated_at"])

    return step
