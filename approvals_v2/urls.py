from django.urls import path
from . import views
from django.conf import settings





app_name = "approvals_v2"

urlpatterns = [
    path("", views.v2_list, name="list"),
    path("new/", views.v2_new, name="new"),
    path("<int:pk>/approve/", views.v2_approve, name="approve"),
    path("<int:pk>/reject/", views.v2_reject, name="reject"),
    path("<int:pk>/", views.v2_detail, name="detail"),
]

# ✅ DEBUG에서만 테스트 엔드포인트 노출
if settings.DEBUG:
    urlpatterns += [
        path("test/<int:pk>/approve/", views.v2_test_approve_and_notify, name="test_approve"),
        path("test/create/", views.v2_test_create, name="test_create"),
        path("test/<int:pk>/reject/", views.v2_test_reject, name="test_reject"),
    ]

