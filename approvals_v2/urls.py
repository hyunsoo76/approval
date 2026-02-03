from django.urls import path
from . import views

app_name = "approvals_v2"

urlpatterns = [
    path("", views.v2_list, name="list"),
    path("new/", views.v2_new, name="new"),
    path("<int:pk>/", views.v2_detail, name="detail"),
    path("test/<int:pk>/approve/", views.v2_test_approve_and_notify, name="test_approve"),

]
