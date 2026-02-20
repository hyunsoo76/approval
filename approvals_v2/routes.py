from django.utils import timezone
from django.db import transaction

from .models import ApprovalRouteInstance, ApprovalRouteStepInstance, TelegramRecipient


@transaction.atomic
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

    # 템플릿별 결재 단계 정의
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
    # ✅ 신규: 총무 → 감사 → 회장
    elif template_code == "ADMIN_TO_AUDITOR_CHAIR":
        steps = [
            (1, TelegramRecipient.ROLE_ADMIN),
            (2, TelegramRecipient.ROLE_AUDITOR),
            (3, TelegramRecipient.ROLE_CHAIRMAN),
        ]
    else:
        raise ValueError(f"unknown template_code: {template_code}")

    # 1) steps 생성
    for order, role in steps:
        ApprovalRouteStepInstance.objects.create(route=route, order=order, role=role)

    # 2) ✅ v2 정책: 상신 시점에 drafter 단계는 자동 승인 처리
    #    - drafter가 1번 단계일 때만
    #    - 이미 current_order가 2 이상이면 중복 적용 방지
    first = route.steps.filter(order=1).first()
    if (
        first
        and first.role == TelegramRecipient.ROLE_DRAFTER
        and first.state == ApprovalRouteStepInstance.STATE_PENDING
        and route.current_order == 1
    ):
        first.state = ApprovalRouteStepInstance.STATE_APPROVED
        first.acted_at = timezone.now()

        # ✅ drafter 도장 스냅샷 저장 (name 매칭)
        recipient = TelegramRecipient.objects.filter(
            role=TelegramRecipient.ROLE_DRAFTER,
            is_active=True,
            name=approval.name,
        ).first()
        if recipient and recipient.stamp_image:
            first.stamp_image = recipient.stamp_image

        first.save(update_fields=["state", "acted_at", "stamp_image"])

        # 다음 단계가 있으면 current_order=2로 이동
        if route.steps.filter(order=2).exists():
            route.current_order = 2
            route.save(update_fields=["current_order", "updated_at"])

    return route


def get_current_actor_role(route: ApprovalRouteInstance) -> str:
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

    # ✅ 결재자 도장 이미지 스냅샷 저장
    recipient_qs = TelegramRecipient.objects.filter(role=step.role, is_active=True)

    # drafter일 가능성까지 안전하게 처리
    if step.role == TelegramRecipient.ROLE_DRAFTER:
        drafter_name = getattr(route.approval, "name", "") or ""
        if drafter_name:
            recipient_qs = recipient_qs.filter(name=drafter_name)

    recipient = recipient_qs.first()
    if recipient and recipient.stamp_image:
        step.stamp_image.name = recipient.stamp_image.name

    step.save(update_fields=[
        "state", "acted_at", "acted_ip", "acted_device", "acted_anon_id", "stamp_image"
    ])

    # 다음 단계 처리
    has_next = route.steps.filter(order=route.current_order + 1).exists()
    if has_next:
        route.current_order = route.current_order + 1
        route.save(update_fields=["current_order", "updated_at"])
    else:
        route.status = ApprovalRouteInstance.STATUS_COMPLETED
        route.completed_at = timezone.now()
        route.save(update_fields=["status", "completed_at", "updated_at"])

    return step


@transaction.atomic
def reject_current_step(
    *,
    route: ApprovalRouteInstance,
    reason: str,
    acted_ip: str = "",
    acted_device: str = "",
    acted_anon_id: str = "",
) -> ApprovalRouteStepInstance:
    """
    현재 단계(route.current_order)를 반려 처리하고 route를 rejected로 만든다.
    """
    step = route.steps.select_for_update().get(order=route.current_order)

    if step.state != ApprovalRouteStepInstance.STATE_PENDING:
        return step

    step.state = ApprovalRouteStepInstance.STATE_REJECTED
    step.reject_reason = reason or ""
    step.acted_at = timezone.now()
    step.acted_ip = acted_ip or None
    step.acted_device = acted_device
    step.acted_anon_id = acted_anon_id
    step.save(update_fields=[
        "state", "reject_reason", "acted_at", "acted_ip", "acted_device", "acted_anon_id"
    ])

    route.status = ApprovalRouteInstance.STATUS_REJECTED
    route.rejected_at = timezone.now()
    route.save(update_fields=["status", "rejected_at", "updated_at"])

    return step
