from django.db import models

class ApprovalRequest(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    department = models.CharField("소속", max_length=100, blank=True)
    name       = models.CharField("성명", max_length=50, blank=True)
    title      = models.CharField("제목", max_length=200, blank=True)
    content    = models.TextField("내용", blank=True)

    manager_signature = models.ImageField(
        "담당 서명", upload_to="signatures/", blank=True, null=True
    )
    admin_signature = models.ImageField(
        "총무 서명", upload_to="signatures/", blank=True, null=True
    )

    submit_ip = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d}] {self.title} - {self.name}"
    
    approved_at = models.DateTimeField(null=True, blank=True)     # 결재 시각
    approved_ip = models.GenericIPAddressField(null=True, blank=True)  # 결재 IP (IPv4/IPv6)
    approved_device = models.CharField(max_length=120, blank=True, default="")  # "iPhone / Safari"

