from django.http import HttpResponse
from .notifications import dispatch_notifications


def v2_list(request):
    return HttpResponse("approval v2: list")


def v2_new(request):
    result = dispatch_notifications(
        template_code="ADMIN_FINAL",
        event="submit",
        drafter_name="홍길동",
        drafter_department="영업팀",
        text="(테스트) 총무전결 상신 알림",
    )

    print("✅ dispatch result:", result)
    return HttpResponse("dispatch test done (check server console)")




def v2_detail(request, pk: int):
    return HttpResponse(f"approval v2: detail {pk}")
