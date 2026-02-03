from django.db import models
from django.conf import settings

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

class ApprovalRouteInstance(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_REJECTED = "rejected"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "작성중"),
        (STATUS_IN_PROGRESS, "진행중"),
        (STATUS_REJECTED, "반려"),
        (STATUS_COMPLETED, "완료"),
    ]

    TEMPLATE_ADMIN_FINAL = "ADMIN_FINAL"      # 담당 -> 총무(전결)
    TEMPLATE_NORMAL = "NORMAL"                # 담당 -> 총무 -> 회장
    TEMPLATE_ADMIN_TO_CHAIR = "ADMIN_TO_CHAIR"  # 총무 -> 회장

    approval = models.OneToOneField(
        "approvals.ApprovalRequest",
        on_delete=models.CASCADE,
        related_name="route_v2",
    )

    template_code = models.CharField(max_length=30)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    current_order = models.PositiveIntegerField(default=1)  # 현재 결재 단계(order)

    submitted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Route({self.template_code}) for approval_id={self.approval_id}"


class ApprovalRouteStepInstance(models.Model):
    STATE_PENDING = "pending"
    STATE_APPROVED = "approved"
    STATE_REJECTED = "rejected"

    STATE_CHOICES = [
        (STATE_PENDING, "대기"),
        (STATE_APPROVED, "승인"),
        (STATE_REJECTED, "반려"),
    ]

    route = models.ForeignKey(
        ApprovalRouteInstance,
        on_delete=models.CASCADE,
        related_name="steps",
    )

    order = models.PositiveIntegerField()
    role = models.CharField(max_length=20)  # drafter/admin/chairman/auditor 등
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default=STATE_PENDING)

    acted_at = models.DateTimeField(null=True, blank=True)
    acted_ip = models.GenericIPAddressField(null=True, blank=True)
    acted_device = models.CharField(max_length=50, blank=True, default="")
    acted_anon_id = models.CharField(max_length=50, blank=True, default="")

    class Meta:
        unique_together = [("route", "order")]
        indexes = [
            models.Index(fields=["route", "order"]),
            models.Index(fields=["role", "state"]),
        ]

    def __str__(self) -> str:
        return f"Step(order={self.order}, role={self.role}, state={self.state})"
