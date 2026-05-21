# Generated manually for v2 payment account rows.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("approvals", "0003_alter_approvalrequest_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="approvalrequest",
            name="payment_accounts",
            field=models.JSONField(blank=True, default=list, verbose_name="결제 계좌 정보"),
        ),
    ]
