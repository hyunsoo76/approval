# approvals/urls.py
from django.urls import path
from . import views

app_name = 'approvals'   # ✨ 이게 있어야 'approvals:new' 같은 이름을 쓸 수 있음

urlpatterns = [
    path('', views.approval_list, name='list'),       # /approval/
    path('new/', views.approval_create, name='new'),     # /approval/new/
    path('<int:pk>/', views.approval_detail, name='detail'),  # /approval/7/
]

