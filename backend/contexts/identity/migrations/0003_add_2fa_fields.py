import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0002_add_is_staff"),
    ]

    operations = [
        migrations.AddField(
            model_name="usermodel",
            name="is_2fa_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="usermodel",
            name="totp_secret",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.CreateModel(
            name="TOTPRecoveryCodeModel",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("code_hash", models.CharField(max_length=128)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="totp_recovery_codes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "identity_totp_recovery_codes",
                "app_label": "identity",
            },
        ),
    ]
