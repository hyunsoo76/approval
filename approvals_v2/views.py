from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from approvals_v2.models import ApprovalAttachment
from approvals.models import ApprovalRequest
from approvals_v2.models import TelegramRecipient
from approvals_v2.routes import (
    build_route_for_approval,
    approve_current_step,
    get_current_actor_role,
    reject_current_step,
)
from approvals_v2.notifications import dispatch_notifications


def v2_list(request):
    """
    v2 문서 리스트
    - 상태 필터: all / in_progress / completed / rejected
    - 검색: 제목/부서/기안자(name)
    """
    status = (request.GET.get("status") or "all").strip()
    q = (request.GET.get("q") or "").strip()

    qs = ApprovalRequest.objects.select_related("route_v2").order_by("-id")

    if status in {"in_progress", "completed", "rejected"}:
        qs = qs.filter(route_v2__status=status)

    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(title__icontains=q) |
            Q(department__icontains=q) |
            Q(name__icontains=q)
        )

    approvals = qs[:200]

    role_label = {
        "drafter": "담당",
        "admin": "총무",
        "chairman": "회장",
        "auditor": "감사",
    }

    approvals_ctx = []
    for a in approvals:
        route = getattr(a, "route_v2", None)
        current_role = ""
        current_role_kr = ""
        current_step_label = ""

        if route:
            step = route.steps.filter(order=route.current_order).first()
            if step:
                current_role = step.role
                current_role_kr = role_label.get(current_role, current_role)
                if route.status == "completed":
                    current_step_label = "완료"
                elif route.status == "rejected":
                    current_step_label = "반려"
                else:
                    current_step_label = f"{current_role_kr} 결재 대기"

        approvals_ctx.append(
            {
                "a": a,
                "route": route,
                "current_role": current_role,
                "current_role_kr": current_role_kr,
                "current_step_label": current_step_label,
            }
        )

    return render(
        request,
        "approvals_v2/list.html",
        {"approvals_ctx": approvals_ctx, "status": status, "q": q},
    )


def v2_new(request):
    # 총무(단일) 이름 확보
    admin_rec = TelegramRecipient.objects.filter(
        is_active=True, role=TelegramRecipient.ROLE_ADMIN
    ).order_by("name").first()
    admin_name = admin_rec.name if admin_rec else ""

    if request.method == "GET":
        # ✅ 담당 목록(드롭다운 기본용)
        drafters = list(
            TelegramRecipient.objects.filter(
                is_active=True,
                role=TelegramRecipient.ROLE_DRAFTER,
            ).order_by("name").values("role", "name")
        )

        # ✅ 총무 목록(보통 1명)
        admins = list(
            TelegramRecipient.objects.filter(
                is_active=True,
                role=TelegramRecipient.ROLE_ADMIN,
            ).order_by("name").values("role", "name")
        )

        return render(
            request,
            "approvals_v2/new.html",
            {
                "drafters": drafters,
                "admins": admins,
                "admin_name": admin_name,
            }
        )

    # POST (여기는 네가 이미 수정한 로직 유지)
    template_code = (request.POST.get("template_code") or "").strip()
    department = (request.POST.get("department") or "").strip()
    name = (request.POST.get("name") or "").strip()
    title = (request.POST.get("title") or "").strip()
    content = (request.POST.get("content") or "").strip()

    if not all([template_code, department, title, content]):
        return HttpResponse("필수값 누락", status=400)

    if template_code == "ADMIN_TO_CHAIR":
        if not admin_name:
            return HttpResponse("총무 계정이 설정되어 있지 않습니다.", status=400)
        name = admin_name
        department = "(주)새진"  # ✅ 소속도 강제 고정
    else:
        if admin_name and name == admin_name:
            return HttpResponse("담당부터 시작하는 결재라인에서는 총무를 성명으로 선택할 수 없습니다.", status=400)
        if not name:
            return HttpResponse("필수값 누락", status=400)

    approval = ApprovalRequest.objects.create(
        department=department,
        name=name,
        title=title,
        content=content,
        submit_ip=request.META.get("REMOTE_ADDR", ""),
    )

    files = request.FILES.getlist("attachments")
    print("FILES:", len(files), [f.name for f in files])
    for f in files:
        ApprovalAttachment.objects.create(
            approval=approval,
            file=f,
            original_name=getattr(f, "name", "")[:255],
        )

    route = build_route_for_approval(approval=approval, template_code=template_code)

    # ✅ ADMIN_TO_CHAIR 상신 즉시 총무 자동승인
    if route.template_code == "ADMIN_TO_CHAIR":
        current_role = get_current_actor_role(route)
        if current_role == "admin":
            approve_current_step(
                route=route,
                acted_ip=request.META.get("REMOTE_ADDR", ""),
                acted_device=(request.META.get("HTTP_USER_AGENT", "")[:50]),
                acted_anon_id=request.COOKIES.get("anon_id", ""),
            )
            route.refresh_from_db()

    dispatch_notifications(
        template_code=route.template_code,
        event="submit",
        actor_role="",
        drafter_name=approval.name,
        drafter_department=approval.department,
        text=f"(v2) 상신: [{approval.department}] {approval.title} (id={approval.id})",
    )

    return redirect(f"/approval/v2/{approval.id}/")



def v2_detail(request, pk: int):
    a = ApprovalRequest.objects.get(pk=pk)
    route = a.route_v2
    steps = route.steps.order_by("order")
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

    step = approve_current_step(
        route=route,
        acted_ip=request.META.get("REMOTE_ADDR", ""),
        acted_device=(request.META.get("HTTP_USER_AGENT", "")[:50]),
        acted_anon_id=request.COOKIES.get("anon_id", ""),
    )

    # 승인 알림
    should_notify = False
    if route.template_code == "ADMIN_FINAL":
        should_notify = (step.role == "admin")
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
    return redirect(f"/approval/v2/{a.id}/")


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

    dispatch_notifications(
        template_code=route.template_code,
        event="reject",
        actor_role=step.role,
        drafter_name=a.name,
        drafter_department=a.department,
        text=f"(v2) 반려: [{a.department}] {a.title} (id={a.id}) actor={step.role} 사유={reason}",
    )

    return redirect(f"/approval/v2/{a.id}/")


def v2_test_approve_and_notify(request, pk: int):
    if not settings.DEBUG:
        raise Http404()

    a = ApprovalRequest.objects.get(pk=pk)
    route = a.route_v2

    step = approve_current_step(route=route)
    actor_role = step.role

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

    # ✅ test도 동일하게 ADMIN_TO_CHAIR auto-approve 반영
    if route.template_code == "ADMIN_TO_CHAIR":
        current_role = get_current_actor_role(route)
        if current_role == "admin":
            approve_current_step(route=route)
            route.refresh_from_db()

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
