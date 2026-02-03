from django.contrib import admin
from .models import TelegramRecipient
from .models import ApprovalRouteInstance, ApprovalRouteStepInstance

@admin.register(TelegramRecipient)
class TelegramRecipientAdmin(admin.ModelAdmin):
    list_display = ("id", "role", "department", "name", "chat_id", "is_active", "updated_at")
    list_filter = ("role", "is_active")
    search_fields = ("name", "department", "chat_id")
    ordering = ("role", "department", "name", "-updated_at")

@admin.register(ApprovalRouteInstance)
class ApprovalRouteInstanceAdmin(admin.ModelAdmin):
    list_display = ("id", "approval_id", "template_code", "status", "current_order", "updated_at")
    list_filter = ("template_code", "status")
    search_fields = ("approval_id",)
    ordering = ("-updated_at",)


@admin.register(ApprovalRouteStepInstance)
class ApprovalRouteStepInstanceAdmin(admin.ModelAdmin):
    list_display = ("id", "route_id", "order", "role", "state", "acted_at")
    list_filter = ("role", "state")
    search_fields = ("route_id",)
    ordering = ("route_id", "order")
