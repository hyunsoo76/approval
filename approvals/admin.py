from django.contrib import admin
from .models import ApprovalRequest


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'name', 'department', 'created_at')
    list_filter = ('department', 'created_at')
    search_fields = ('title', 'name', 'department', 'content')
