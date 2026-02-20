from django.contrib import admin

from .models import (
    TelegramRecipient,
    ApprovalRouteInstance,
    ApprovalRouteStepInstance,
    ApprovalAttachment,
    TempUploadImage,
)


@admin.register(TelegramRecipient)
class TelegramRecipientAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "role",
        "department",
        "name",
        "chat_id",
        "stamp_image",
        "is_active",
        "updated_at",
    )
    list_filter = ("role", "is_active")
    search_fields = ("name", "department", "chat_id")
    ordering = ("role", "department", "name", "-updated_at")
    list_editable = ("is_active",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ApprovalRouteInstance)
class ApprovalRouteInstanceAdmin(admin.ModelAdmin):
    list_display = ("id", "approval_id", "template_code", "status", "current_order", "updated_at")
    list_filter = ("template_code", "status")
    search_fields = ("approval_id",)
    ordering = ("-updated_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ApprovalRouteStepInstance)
class ApprovalRouteStepInstanceAdmin(admin.ModelAdmin):
    list_display = ("id", "route_id", "order", "role", "state", "acted_at")
    list_filter = ("role", "state")
    search_fields = ("route_id",)
    ordering = ("route_id", "order")


@admin.register(ApprovalAttachment)
class ApprovalAttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "approval_id", "original_name", "created_at")
    search_fields = ("original_name", "approval_id")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)


@admin.register(TempUploadImage)
class TempUploadImageAdmin(admin.ModelAdmin):
    list_display = ("id", "token", "created_at")
    search_fields = ("token",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
