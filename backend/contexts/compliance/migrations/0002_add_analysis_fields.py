import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compliance', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='kycdocumentmodel',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING', 'En attente'),
                    ('ANALYZING', 'En analyse IA'),
                    ('APPROVED', 'Approuvé'),
                    ('REJECTED', 'Rejeté'),
                    ('PENDING_REVIEW', 'Révision manuelle requise'),
                ],
                default='ANALYZING',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='kycdocumentmodel',
            name='analysis_score',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='kycdocumentmodel',
            name='analysis_details',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='kycdocumentmodel',
            name='reviewed_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reviewed_kyc_documents',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='kycdocumentmodel',
            name='review_comment',
            field=models.TextField(blank=True, null=True),
        ),
    ]
