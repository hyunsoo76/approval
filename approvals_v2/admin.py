from django.contrib import admin
from .models import TelegramRecipient


@admin.register(TelegramRecipient)
class TelegramRecipientAdmin(admin.ModelAdmin):
    list_display = ("id", "role", "department", "name", "chat_id", "is_active", "updated_at")
    list_filter = ("role", "is_active")
    search_fields = ("name", "department", "chat_id")
    ordering = ("role", "department", "name", "-updated_at")
