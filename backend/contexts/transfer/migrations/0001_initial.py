import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TransactionModel',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('beneficiary_name', models.CharField(max_length=200)),
                ('beneficiary_country', models.CharField(max_length=2)),
                ('momo_number', models.CharField(max_length=30)),
                ('operator', models.CharField(
                    choices=[
                        ('MTN_MOMO', 'MTN Mobile Money'),
                        ('ORANGE_MONEY', 'Orange Money'),
                    ],
                    max_length=20,
                )),
                ('amount_eur', models.DecimalField(decimal_places=2, max_digits=10)),
                ('fees_eur', models.DecimalField(decimal_places=2, max_digits=10)),
                ('amount_xaf', models.DecimalField(decimal_places=2, max_digits=14)),
                ('status', models.CharField(
                    choices=[
                        ('DRAFT', 'Brouillon'),
                        ('PENDING_AML', 'En attente scoring AML'),
                        ('AML_BLOCKED', 'Bloqué par AML'),
                        ('AML_PENDING_REVIEW', 'Révision AML requise'),
                        ('PROCESSING', 'Paiement en cours'),
                        ('ESCROWED', 'Fonds sécurisés (escrow)'),
                        ('DELIVERED', 'Livré'),
                        ('PAYMENT_FAILED', 'Paiement échoué'),
                    ],
                    default='DRAFT',
                    max_length=24,
                )),
                ('aml_result_id', models.CharField(blank=True, max_length=100, null=True)),
                ('stripe_payment_intent_id', models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('sender', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='transactions',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'transfer_transactions',
                'ordering': ['-created_at'],
            },
        ),
    ]
