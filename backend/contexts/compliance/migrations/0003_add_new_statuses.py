from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compliance', '0002_add_analysis_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='kycdocumentmodel',
            name='status',
            field=models.CharField(
                choices=[
                    ('SUBMITTED', 'Soumis'),
                    ('ANALYZING', 'En analyse IA'),
                    ('APPROVED', 'Validé (IA)'),
                    ('PENDING_REVIEW', 'Validation manuelle requise'),
                    ('APPROVED_MANUAL', 'Validé manuellement'),
                    ('COMPLEMENT_REQUESTED', 'Complément demandé'),
                    ('REJECTED', 'Rejeté'),
                ],
                default='ANALYZING',
                max_length=24,
            ),
        ),
    ]
