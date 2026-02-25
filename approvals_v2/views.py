from django.conf import settings
from django.core.files.storage import default_storage
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from approvals.models import ApprovalRequest
from approvals_v2.models import ApprovalAttachment, TelegramRecipient
from approvals_v2.notifications import dispatch_notifications
from approvals_v2.routes import (
    build_route_for_approval,
    approve_current_step,
    get_current_actor_role,
    reject_current_step,
)
from django.shortcuts import get_object_or_404

# =========================
# ✅ 텔레그램 메시지 포맷
# =========================
ROLE_KR = {
    "drafter": "담당",
    "admin": "총무",
    "auditor": "감사",
    "chairman": "회장",
}

def get_client_ip(request) -> str:
    xff = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if xff:
        return xff.split(",")[0].strip()

    xri = (request.META.get("HTTP_X_REAL_IP") or "").strip()
    if xri:
        return xri

    return (request.META.get("REMOTE_ADDR") or "").strip()


def role_kr(role: str) -> str:
    return ROLE_KR.get(role or "", role or "")


def fmt_submit_date(dt):
    dt = timezone.localtime(dt)
    return f"{dt.year}년 {dt.month}월 {dt.day}일"


def drafter_role_kr_by_template(template_code: str) -> str:
    """
    기안자는 '이름'이 아니라 '역할'로만 표시
    - 총무 시작 템플릿: 총무
    - 그 외: 담당
    """
    admin_start = {"ADMIN_TO_CHAIR", "ADMIN_TO_AUDITOR_CHAIR"}
    return "총무" if template_code in admin_start else "담당"


def drafter_role_code_by_template(template_code: str) -> str:
    """
    ✅ 기안자를 role 코드로 반환
    - 총무 시작 템플릿: admin (총무가 기안자)
    - 그 외: drafter (담당이 기안자)
    """
    admin_start = {"ADMIN_TO_CHAIR", "ADMIN_TO_AUDITOR_CHAIR"}
    return "admin" if template_code in admin_start else "drafter"


def get_approver_roles(route, template_code: str):
    """
    ✅ '기안자 역할'을 제외한 결재자 role들을 order 순서로 반환
    예)
      - NORMAL(담당 기안): [admin, chairman] / [admin, auditor, chairman]
      - ADMIN_TO_CHAIR(총무 기안): [chairman]
      - ADMIN_TO_AUDITOR_CHAIR(총무 기안): [auditor, chairman]
    """
    if not route:
        return []
    drafter_code = drafter_role_code_by_template(template_code)
    return list(
        route.steps.exclude(role=drafter_code).order_by("order").values_list("role", flat=True)
    )


def get_step_state_by_role(route):
    """
    role -> state 매핑
    """
    if not route:
        return {}
    return {s.role: s.state for s in route.steps.all()}


def build_tg_text(*, kind: str, approval, route, template_code: str, actor_role: str, actor_action_kr: str, request):
    """
    kind: submit / approve / reject
    actor_action_kr: 승인/반려 (approve/reject일 때만 사용)
    규칙:
    - (v2) 제거
    - 기안자: 역할만
    - 2명 라인: 기안자 + 최종결재자
    - 3명 라인: 기안자 + 중간결재자 + 최종결재자 (누적)
    - 마지막 줄: 바로가기 URL
    """
    base_url = request.build_absolute_uri(f"/approval/v2/{approval.id}/")

    # ✅ route 최신상태 기준으로 계산(중요)
    approver_roles = get_approver_roles(route, template_code)  # ✅ 기안자 역할 제외
    state_by_role = get_step_state_by_role(route)

    lines = []
    lines.append("내쇼날새천년 전자결재")
    lines.append(f"상신일 : {fmt_submit_date(approval.created_at)}")
    lines.append(f"제목 : {approval.title}")
    lines.append(f"기안자 : {drafter_role_kr_by_template(template_code)}")

    if kind in {"approve", "reject"}:
        # 결재자가 0명인 예외 방어
        if not approver_roles:
            lines.append(f"처리자 : {role_kr(actor_role)}[{actor_action_kr}]")
        else:
            # ✅ 2명 라인 = (기안자 제외 결재자) 1명 => 최종결재자만
            if len(approver_roles) == 1:
                final_role = approver_roles[-1]
                lines.append(f"최종결재자 : {role_kr(final_role)}[{actor_action_kr}]")

            # ✅ 3명 라인 = (기안자 제외 결재자) 2명 => 중간 + 최종
            else:
                middle_role = approver_roles[0]
                final_role = approver_roles[-1]
                middle_state = state_by_role.get(middle_role, "")

                if actor_role == middle_role:
                    # ✅ 중간 결재자 처리 알림: 중간 1줄만
                    lines.append(f"중간결재자 : {role_kr(middle_role)}[{actor_action_kr}]")

                elif actor_role == final_role:
                    # ✅ 최종 결재자 처리 알림: 중간이 이미 처리된 경우만 누적 표시
                    if middle_state == "approved":
                        lines.append(f"중간결재자 : {role_kr(middle_role)}[승인]")
                    elif middle_state == "rejected":
                        lines.append(f"중간결재자 : {role_kr(middle_role)}[반려]")

                    lines.append(f"최종결재자 : {role_kr(final_role)}[{actor_action_kr}]")

                else:
                    # ✅ 4명 이상으로 늘어나는 경우 대비
                    lines.append(f"승인자 : {role_kr(actor_role)}[{actor_action_kr}]")

    lines.append(f"바로가기 : {base_url}")
    return "\n".join(lines)


# =========================
# v2 list
# =========================
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


# =========================
# v2 new
# =========================
def v2_new(request):
    # ✅ 총무(ADMIN) 1명 기준
    admin_obj = TelegramRecipient.objects.filter(
        is_active=True,
        role=TelegramRecipient.ROLE_ADMIN,
    ).order_by("id").first()
    admin_name = admin_obj.name if admin_obj else ""

    if request.method == "GET":
        drafters = list(
            TelegramRecipient.objects.filter(
                is_active=True,
                role=TelegramRecipient.ROLE_DRAFTER,
            )
            .order_by("name")
            .values("role", "name", "department")
        )

        admins = list(
            TelegramRecipient.objects.filter(
                is_active=True,
                role=TelegramRecipient.ROLE_ADMIN,
            )
            .order_by("name")
            .values("role", "name", "department")
        )

        admin_name_ui = admins[0]["name"] if admins else ""

        return render(
            request,
            "approvals_v2/new.html",
            {
                "drafters": drafters,
                "admins": admins,
                "admin_name": admin_name_ui,
            }
        )

    template_code = (request.POST.get("template_code") or "").strip()
    department = (request.POST.get("department") or "").strip()
    name = (request.POST.get("name") or "").strip()
    title = (request.POST.get("title") or "").strip()
    content = (request.POST.get("content") or "").strip()

    if not all([template_code, department, title, content]):
        return HttpResponse("필수값 누락", status=400)

    ADMIN_START_TEMPLATES = {"ADMIN_TO_CHAIR", "ADMIN_TO_AUDITOR_CHAIR"}

    if template_code in ADMIN_START_TEMPLATES:
        if not admin_name:
            return HttpResponse("총무 계정이 설정되어 있지 않습니다.", status=400)
        name = admin_name
        department = "(주)새진"
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
        submit_ip=get_client_ip(request),
    )

    files = request.FILES.getlist("attachments")
    for f in files:
        ApprovalAttachment.objects.create(
            approval=approval,
            file=f,
            original_name=getattr(f, "name", "")[:255],
        )

    route = build_route_for_approval(approval=approval, template_code=template_code)

    if route.template_code in ("ADMIN_TO_CHAIR", "ADMIN_TO_AUDITOR_CHAIR"):
        current_role = get_current_actor_role(route)
        if current_role == "admin":
            approve_current_step(
                route=route,
                acted_ip=get_client_ip(request),
                acted_device=(request.META.get("HTTP_USER_AGENT", "")[:50]),
                acted_anon_id=request.COOKIES.get("anon_id", ""),
            )
            route.refresh_from_db()

    # ✅ 상신 알림
    dispatch_notifications(
        template_code=route.template_code,
        event="submit",
        actor_role="",
        drafter_name=approval.name,
        drafter_department=approval.department,
        text=build_tg_text(
            kind="submit",
            approval=approval,
            route=route,
            template_code=route.template_code,
            actor_role="",
            actor_action_kr="",
            request=request,
        ),
    )

    return redirect(f"/approval/v2/{approval.id}/")


# =========================
# v2 detail
# =========================
def v2_detail(request, pk: int):
    a = get_object_or_404(ApprovalRequest, pk=pk)
    route = a.route_v2
    steps = route.steps.order_by("order")
    actor_role = get_current_actor_role(route)

    return render(
        request,
        "approvals_v2/detail.html",
        {"approval": a, "route": route, "steps": steps, "actor_role": actor_role},
    )


# =========================
# approve
# =========================
def v2_approve(request, pk: int):
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    a = ApprovalRequest.objects.get(pk=pk)
    route = a.route_v2

    step = approve_current_step(
        route=route,
        acted_ip=get_client_ip(request),
        acted_device=(request.META.get("HTTP_USER_AGENT", "")[:50]),
        acted_anon_id=request.COOKIES.get("anon_id", ""),
    )

    # ✅ 상태 반영
    route.refresh_from_db()

    should_notify = False
    if route.template_code == "ADMIN_FINAL":
        should_notify = (step.role == "admin")
    elif route.template_code in ("NORMAL", "ADMIN_TO_CHAIR"):
        should_notify = (step.role in ("admin", "chairman"))
    elif route.template_code == "ADMIN_TO_AUDITOR_CHAIR":
        should_notify = (step.role in ("auditor", "chairman"))

    if should_notify:
        dispatch_notifications(
            template_code=route.template_code,
            event="approve",
            actor_role=step.role,
            drafter_name=a.name,
            drafter_department=a.department,
            text=build_tg_text(
                kind="approve",
                approval=a,
                route=route,
                template_code=route.template_code,
                actor_role=step.role,
                actor_action_kr="승인",
                request=request,
            ),
        )

    return redirect(f"/approval/v2/{a.id}/")


# =========================
# reject
# =========================
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
        acted_ip=get_client_ip(request),
        acted_device=(request.META.get("HTTP_USER_AGENT", "")[:50]),
        acted_anon_id=request.COOKIES.get("anon_id", ""),
    )

    # ✅ 상태 반영
    route.refresh_from_db()

    dispatch_notifications(
        template_code=route.template_code,
        event="reject",
        actor_role=step.role,
        drafter_name=a.name,
        drafter_department=a.department,
        text=build_tg_text(
            kind="reject",
            approval=a,
            route=route,
            template_code=route.template_code,
            actor_role=step.role,
            actor_action_kr="반려",
            request=request,
        ),
    )

    return redirect(f"/approval/v2/{a.id}/")


# =========================
# DEBUG test endpoints
# =========================
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
        submit_ip=get_client_ip(request),
    )

    route = build_route_for_approval(approval=approval, template_code=template_code)

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
        text="(테스트) 상신",
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
        acted_ip=get_client_ip(request),
        acted_device=(request.META.get("HTTP_USER_AGENT", "")[:50]),
        acted_anon_id=request.COOKIES.get("anon_id", ""),
    )

    return HttpResponse(f"rejected actor={step.role} reason={reason}")


# =========================
# mobile upload (기존 유지)
# =========================
MOBILE_UPLOAD_STORE = {}  # token -> {"image_url": "...", "ts": ...}


@csrf_exempt
def mobile_upload_page(request, token: str):
    if request.method == "GET":
        return render(request, "approvals_v2/mobile_upload.html", {"token": token})

    f = request.FILES.get("image")
    if not f:
        return JsonResponse({"ok": False, "error": "no file"}, status=400)

    path = default_storage.save(f"mobile_upload/{token}/{f.name}", f)
    url = default_storage.url(path)

    MOBILE_UPLOAD_STORE[token] = {"image_url": url, "ts": timezone.now().isoformat()}
    return JsonResponse({"ok": True, "image_url": url})


def mobile_upload_poll(request, token: str):
    data = MOBILE_UPLOAD_STORE.get(token) or {}
    return JsonResponse({"image_url": data.get("image_url", "")})


# =========================
# pdf (그대로 유지)
# =========================
def approval_pdf(request, pk):
    """
    v2 PDF 출력
    - content 내부 <html>, <body>, <style>, <script> 제거
    - 첨부파일 안전 전달
    - route/steps 안전 처리
    """
    from weasyprint import HTML
    import re

    try:
        approval = ApprovalRequest.objects.select_related("route_v2").get(pk=pk)
    except ApprovalRequest.DoesNotExist:
        raise Http404()

    route = getattr(approval, "route_v2", None)
    steps = route.steps.all().order_by("order") if route else []

    raw = approval.content or ""
    raw = re.sub(r"(?is)<style.*?>.*?</style>", "", raw)
    raw = re.sub(r"(?is)<script.*?>.*?</script>", "", raw)
    raw = re.sub(r"(?is)<link[^>]*>", "", raw)
    raw = re.sub(r"(?is)</?(html|body|head)[^>]*>", "", raw)
    content_html = raw

    attachments = []
    if hasattr(approval, "v2_attachments"):
        attachments = list(approval.v2_attachments.all())

    html_string = render_to_string(
        "approvals_v2/pdf_template.html",
        {
            "approval": approval,
            "route": route,
            "steps": steps,
            "content_html": content_html,
            "attachments": attachments,
        },
        request=request,
    )

    pdf_bytes = HTML(
        string=html_string,
        base_url=request.build_absolute_uri("/"),
    ).write_pdf()

    filename = f"approval_{approval.id}.pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")

    download = request.GET.get("download") == "1"
    disposition = "attachment" if download else "inline"
    response["Content-Disposition"] = f'{disposition}; filename="{filename}"'

    return response