from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('approval/', include('approvals.urls')),  # approvals/urls.py의 ''가 루트가 됨
]

# 개발용. 운영에서는 nginx가 media/static 처리
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

