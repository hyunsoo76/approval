from django.urls import path
from . import views
from django.conf import settings
from . import mobile_upload_views




app_name = "approvals_v2"

urlpatterns = [
    path("", views.v2_list, name="list"),
    path("new/", views.v2_new, name="new"),
    path("<int:pk>/approve/", views.v2_approve, name="approve"),
    path("<int:pk>/reject/", views.v2_reject, name="reject"),
    path("<int:pk>/", views.v2_detail, name="detail"),
    path("mobile-upload/<str:token>/", views.mobile_upload_page, name="v2_mobile_upload_page"),
    path("mobile-upload/<str:token>/poll/", views.mobile_upload_poll, name="v2_mobile_upload_poll"),
    path("<int:pk>/pdf/", views.approval_pdf, name="approval_pdf"),
]

# ✅ DEBUG에서만 테스트 엔드포인트 노출
if settings.DEBUG:
    urlpatterns += [
        path("test/<int:pk>/approve/", views.v2_test_approve_and_notify, name="test_approve"),
        path("test/create/", views.v2_test_create, name="test_create"),
        path("test/<int:pk>/reject/", views.v2_test_reject, name="test_reject"),
    ]

urlpatterns += [
    path("mobile-upload/<uuid:token>/", mobile_upload_views.mobile_upload_page, name="mobile_upload"),
    path("mobile-upload/<uuid:token>/upload/", mobile_upload_views.mobile_upload_api, name="mobile_upload_api"),
    path("mobile-upload/<uuid:token>/poll/", mobile_upload_views.mobile_upload_poll, name="mobile_upload_poll"),
]