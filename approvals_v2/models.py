from django.db import models


class TelegramRecipient(models.Model):
    ROLE_DRAFTER = "drafter"
    ROLE_ADMIN = "admin"
    ROLE_CHAIRMAN = "chairman"

    ROLE_CHOICES = [
        (ROLE_DRAFTER, "담당(기안자)"),
        (ROLE_ADMIN, "총무"),
        (ROLE_CHAIRMAN, "회장"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    name = models.CharField(max_length=50, blank=True, default="")
    department = models.CharField(max_length=50, blank=True, default="")
    chat_id = models.CharField(max_length=50)  # 텔레그램 chat_id (숫자/문자 모두 대비)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["role", "is_active"]),
            models.Index(fields=["role", "department", "name"]),
        ]

    def __str__(self) -> str:
        parts = [self.get_role_display()]
        if self.department:
            parts.append(self.department)
        if self.name:
            parts.append(self.name)
        parts.append(self.chat_id)
        return " / ".join(parts)
