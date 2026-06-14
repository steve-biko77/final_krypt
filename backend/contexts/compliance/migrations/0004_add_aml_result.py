import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compliance', '0003_add_new_statuses'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AMLResultModel',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('transfer_id', models.CharField(db_index=True, max_length=100)),
                ('xgboost_score', models.FloatField()),
                ('ofac_match', models.BooleanField(default=False)),
                ('ofac_details', models.JSONField(blank=True, null=True)),
                ('combined_decision', models.CharField(
                    choices=[
                        ('HARD_BLOCK', 'Blocage OFAC/EU'),
                        ('AUTO_APPROVED', 'Approuvé automatiquement'),
                        ('AUTO_BLOCKED', 'Bloqué automatiquement'),
                        ('PENDING_REVIEW', 'Révision admin requise'),
                        ('MANUALLY_APPROVED', 'Approuvé manuellement'),
                        ('MANUALLY_REJECTED', 'Rejeté manuellement'),
                    ],
                    max_length=20,
                )),
                ('review_decision', models.CharField(blank=True, max_length=20, null=True)),
                ('audit_hash', models.CharField(blank=True, max_length=64, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='aml_reviews',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='aml_results',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'compliance_aml_results',
                'ordering': ['-created_at'],
                'app_label': 'compliance',
            },
        ),
    ]
