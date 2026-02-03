from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static



urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('approvals.urls')),  # approvals/urls.py의 ''가 루트가 됨
    path("approval/v2/", include("approvals_v2.urls")),
]

# 개발용. 운영에서는 nginx가 media/static 처리
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

