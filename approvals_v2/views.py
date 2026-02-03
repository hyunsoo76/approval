from django.http import HttpResponse
from .notifications import dispatch_notifications
from approvals.models import ApprovalRequest
from approvals_v2.routes import approve_current_step
from approvals_v2.notifications import dispatch_notifications
from django.conf import settings
from django.http import Http404


def v2_list(request):
    return HttpResponse("approval v2: list")


def v2_new(request):
    cases = [
        ("NORMAL", "approve", ""),  # actor_role 없으면 group False 기대
        ("NORMAL", "approve", "admin"),
        ("NORMAL", "approve", "chairman"),
    ]

    lines = []
    for template_code, event, actor_role in cases:
        result = dispatch_notifications(
            template_code=template_code,
            event=event,
            actor_role=actor_role,
            drafter_name="정현수",
            drafter_department="(주)대진산업",
            text=f"(테스트) NORMAL approve actor_role={actor_role or 'EMPTY'}",
        )
        print("✅", template_code, event, actor_role, result)
        lines.append(f"{template_code}/{event}/{actor_role or 'EMPTY'} -> {result}")

    return HttpResponse("<br>".join(lines))



def v2_detail(request, pk: int):
    return HttpResponse(f"approval v2: detail {pk}")


def v2_test_approve_and_notify(request, pk: int):
    """
    테스트: pk ApprovalRequest의 route_v2 현재 단계를 승인 처리하고,
    승인한 역할(role)을 actor_role로 넣어 알림 dispatch.
    """
    if not settings.DEBUG:
        raise Http404()

    a = ApprovalRequest.objects.get(pk=pk)
    route = a.route_v2

    step = approve_current_step(route=route)

    # 승인한 주체(방금 승인된 step의 role)
    actor_role = step.role

    # 템플릿 코드에 맞춰 알림 dispatch (stub print)
    result = dispatch_notifications(
        template_code=route.template_code,
        event="approve",
        actor_role=actor_role,
        drafter_name=a.name,
        drafter_department=a.department,
        text=f"(테스트) 승인 처리: approval_id={a.id}, actor_role={actor_role}",
    )

    route.refresh_from_db()
    return HttpResponse(
        f"approved step order={step.order} role={step.role}<br>"
        f"route current_order={route.current_order} status={route.status}<br>"
        f"dispatch={result}"
    )
