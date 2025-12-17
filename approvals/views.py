import base64
import uuid
import os

from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from .models import ApprovalRequest
from django.utils import timezone

import base64
import os
import uuid

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404

from .models import ApprovalRequest


def _save_signature_from_dataurl(data_url: str):
    """
    data:image/png;base64,... 형태의 문자열을 받아
    media/signatures/ 아래에 파일 저장하고,
    ImageField에 넣을 경로('signatures/파일명')를 리턴.
    """
    if not data_url or "," not in data_url:
        return None

    header, b64data = data_url.split(",", 1)

    # 확장자 추출 (기본 png)
    if "image/" in header:
        ext = header.split("image/")[1].split(";")[0]
    else:
        ext = "png"

    file_name = f"{uuid.uuid4()}.{ext}"
    save_dir = os.path.join(settings.MEDIA_ROOT, "signatures")
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, file_name)

    with open(save_path, "wb") as f:
        f.write(base64.b64decode(b64data))

    # ImageField에는 MEDIA_ROOT 기준 경로
    return f"signatures/{file_name}"



def approval_create(request):
    """
    1단계: 기안자가 작성 + 기안(담당) 서명.
    저장 후 /approval/<id>/ 로 리다이렉트 → 이 URL을 카톡으로 보내서 결재자가 서명.
    """
    if request.method == "POST":
        dept    = request.POST.get("department", "")
        name    = request.POST.get("name", "")
        title   = request.POST.get("title", "")
        content = request.POST.get("content", "")
        # doc_date 는 지금은 DB에 안 넣고, 나중에 필요하면 필드 추가

        manager_sig_data = request.POST.get("manager_signature", "")

        obj = ApprovalRequest(
            department=dept,
            name=name,
            title=title,
            content=content,
            submit_ip=request.META.get("REMOTE_ADDR"),
        )

        # 기안자 서명만 저장
        manager_path = _save_signature_from_dataurl(manager_sig_data)
        if manager_path:
            obj.manager_signature.name = manager_path

        obj.save()

        # ✅ 여기서 "완료 화면" 대신 상세페이지로 리다이렉트
        #    이 주소를 카톡으로 보내면 됨
        return redirect("approvals:detail", pk=obj.pk)

    # GET: 기존에 만들었던 form.html 그대로 사용
    return render(request, "approvals/form.html")

def _get_client_ip(request):
    """
    AWS/Nginx/ALB 뒤에서도 동작하도록 X-Forwarded-For 우선.
    (Nginx에서 proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; 필요)
    """
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        # "client, proxy1, proxy2" 형태 -> 첫번째가 원 IP일 가능성이 큼
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _summarize_device(user_agent: str) -> str:
    ua = (user_agent or "").lower()

    # 기기(대충)
    if "iphone" in ua:
        device = "iPhone"
    elif "ipad" in ua:
        device = "iPad"
    elif "android" in ua:
        device = "Android"
    else:
        device = "PC"

    # 브라우저(대충)
    # iOS 크롬도 UA에 CriOS가 들어가고, 사파리는 safari + (chrome/ crios/ fxios 없음)
    if "crios" in ua or "chrome" in ua:
        browser = "Chrome"
    elif "fxios" in ua or "firefox" in ua:
        browser = "Firefox"
    elif "safari" in ua and ("chrome" not in ua and "crios" not in ua and "fxios" not in ua):
        browser = "Safari"
    else:
        browser = "Browser"

    return f"{device} / {browser}"

def approval_detail(request, pk):
    approval = get_object_or_404(ApprovalRequest, pk=pk)

    if request.method == "POST":
        # ✅ 이미 결재 서명이 있다면 아무 것도 하지 않고 다시 상세로
        if approval.admin_signature:
            return redirect("approvals:detail", pk=approval.pk)

        admin_sig_data = request.POST.get("admin_signature", "")
        admin_path = _save_signature_from_dataurl(admin_sig_data)

        if admin_path:
            approval.admin_signature.name = admin_path

            # ✅ 여기 추가: 결재 정보 저장
            approval.approved_at = timezone.now()
            approval.approved_ip = _get_client_ip(request)
            approval.approved_device = _summarize_device(request.META.get("HTTP_USER_AGENT", ""))

            approval.save()

        return redirect("approvals:detail", pk=approval.pk)

    return render(request, "approvals/detail.html", {"approval": approval})


def approval_list(request):
    approvals = ApprovalRequest.objects.order_by('-id')  # 최근 문서가 위로
    return render(request, 'approvals/list.html', {
        'approvals': approvals,
    })


