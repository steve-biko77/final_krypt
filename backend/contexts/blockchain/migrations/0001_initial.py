import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='PendingAuditHash',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('transaction_id', models.CharField(db_index=True, max_length=100)),
                ('leaf_hash', models.CharField(max_length=66)),
                ('batched', models.BooleanField(db_index=True, default=False)),
                ('batch_id', models.IntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'blockchain_pending_audit_hashes',
                'ordering': ['created_at'],
            },
        ),
    ]
