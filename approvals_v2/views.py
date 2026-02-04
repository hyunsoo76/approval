from django.http import HttpResponse
from .notifications import dispatch_notifications
from approvals.models import ApprovalRequest
from approvals_v2.routes import approve_current_step
from approvals_v2.notifications import dispatch_notifications
from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from approvals_v2.routes import build_route_for_approval
from django.shortcuts import redirect
from approvals_v2.routes import approve_current_step, get_current_actor_role
from approvals_v2.routes import reject_current_step
from django.views.decorators.csrf import csrf_exempt

def v2_list(request):
    return HttpResponse("approval v2: list")


def v2_new(request):
    if request.method == "GET":
        return render(request, "approvals_v2/new.html")

    # POST
    template_code = (request.POST.get("template_code") or "").strip()
    department = (request.POST.get("department") or "").strip()
    name = (request.POST.get("name") or "").strip()
    title = (request.POST.get("title") or "").strip()
    content = (request.POST.get("content") or "").strip()

    if not all([template_code, department, name, title, content]):
        return HttpResponse("필수값 누락", status=400)

    # 1) ApprovalRequest 생성(v1 모델 재사용)
    approval = ApprovalRequest.objects.create(
        department=department,
        name=name,
        title=title,
        content=content,
        submit_ip=request.META.get("REMOTE_ADDR", ""),
    )

    # 2) route/steps 생성
    route = build_route_for_approval(approval=approval, template_code=template_code)

    # 3) 상신 알림(정책 적용)
    # - ADMIN_FINAL: 총무 DM만
    # - NORMAL: 총무 DM만
    # - ADMIN_TO_CHAIR: (일단) 단톡방/DM 정책은 라우터 기본값에 따름 (추후 확정)
    dispatch_notifications(
        template_code=route.template_code,
        event="submit",
        actor_role="",  # submit은 actor 구분 불필요
        drafter_name=approval.name,
        drafter_department=approval.department,
        text=f"(v2) 상신: [{approval.department}] {approval.title} (id={approval.id})",
    )

    return render(request, "approvals_v2/created.html", {"approval": approval, "route": route})





def v2_detail(request, pk: int):
    a = ApprovalRequest.objects.get(pk=pk)
    route = a.route_v2
    steps = list(route.steps.order_by("order").values("order", "role", "state", "reject_reason"))

    actor_role = get_current_actor_role(route)

    return render(
        request,
        "approvals_v2/detail.html",
        {"approval": a, "route": route, "steps": steps, "actor_role": actor_role},
    )


def v2_approve(request, pk: int):
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    a = ApprovalRequest.objects.get(pk=pk)
    route = a.route_v2

    # 승인 처리
    step = approve_current_step(
        route=route,
        acted_ip=request.META.get("REMOTE_ADDR", ""),
        acted_device=(request.META.get("HTTP_USER_AGENT", "")[:50]),
        acted_anon_id=request.COOKIES.get("anon_id", ""),
    )

        # 승인 알림: 정책상 '결재자' 승인 때만 보냄 (drafter 단계는 알림 없음)
    should_notify = False
    if route.template_code == "ADMIN_FINAL":
        should_notify = (step.role == "admin")  # 최종 승인만
    elif route.template_code in ("NORMAL", "ADMIN_TO_CHAIR"):
        should_notify = (step.role in ("admin", "chairman"))

    if should_notify:
        dispatch_notifications(
            template_code=route.template_code,
            event="approve",
            actor_role=step.role,
            drafter_name=a.name,
            drafter_department=a.department,
            text=f"(v2) 승인: [{a.department}] {a.title} (id={a.id}) actor={step.role}",
        )

def v2_reject(request, pk: int):
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    reason = (request.POST.get("reason") or "").strip()
    if not reason:
        return HttpResponse("반려 사유를 입력해주세요.", status=400)

    a = ApprovalRequest.objects.get(pk=pk)
    route = a.route_v2

    step = reject_current_step(
        route=route,
        reason=reason,
        acted_ip=request.META.get("REMOTE_ADDR", ""),
        acted_device=(request.META.get("HTTP_USER_AGENT", "")[:50]),
        acted_anon_id=request.COOKIES.get("anon_id", ""),
    )

    # 반려 알림 정책(일단 최소):
    # - ADMIN_FINAL: 반려는 총무에게 DM(진행 중인 결재자)
    # - NORMAL/ADMIN_TO_CHAIR: 반려는 단톡방 + 담당 DM(추후 확정 가능)
    dispatch_notifications(
        template_code=route.template_code,
        event="reject",
        actor_role=step.role,
        drafter_name=a.name,
        drafter_department=a.department,
        text=f"(v2) 반려: [{a.department}] {a.title} (id={a.id}) actor={step.role} 사유={reason}",
    )

    return redirect(f"/approval/v2/{a.id}/")



    return redirect(f"/approval/v2/{a.id}/")


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

@csrf_exempt
def v2_test_create(request):
    if not settings.DEBUG:
        raise Http404()
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    template_code = (request.POST.get("template_code") or "").strip()
    department = (request.POST.get("department") or "").strip()
    name = (request.POST.get("name") or "").strip()
    title = (request.POST.get("title") or "").strip()
    content = (request.POST.get("content") or "").strip()

    if not all([template_code, department, name, title, content]):
        return HttpResponse("필수값 누락", status=400)

    approval = ApprovalRequest.objects.create(
        department=department,
        name=name,
        title=title,
        content=content,
        submit_ip=request.META.get("REMOTE_ADDR", ""),
    )

    route = build_route_for_approval(approval=approval, template_code=template_code)

    dispatch_notifications(
        template_code=route.template_code,
        event="submit",
        actor_role="",
        drafter_name=approval.name,
        drafter_department=approval.department,
        text=f"(v2) 상신: [{approval.department}] {approval.title} (id={approval.id})",
    )

    return HttpResponse(str(approval.id))

@csrf_exempt
def v2_test_reject(request, pk: int):
    if not settings.DEBUG:
        raise Http404()
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    a = ApprovalRequest.objects.get(pk=pk)
    route = a.route_v2

    reason = (request.POST.get("reason") or "").strip() or "테스트"

    step = reject_current_step(
        route=route,
        reason=reason,
        acted_ip=request.META.get("REMOTE_ADDR", ""),
        acted_device=(request.META.get("HTTP_USER_AGENT", "")[:50]),
        acted_anon_id=request.COOKIES.get("anon_id", ""),
    )

    result = dispatch_notifications(
        template_code=route.template_code,
        event="reject",
        actor_role=step.role,
        drafter_name=a.name,
        drafter_department=a.department,
        text=f"(v2) 반려: [{a.department}] {a.title} (id={a.id}) actor={step.role} 사유={reason}",
    )

    return HttpResponse(f"rejected actor={step.role} dispatch={result}")
