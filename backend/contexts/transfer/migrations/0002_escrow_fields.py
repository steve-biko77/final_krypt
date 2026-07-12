from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transfer', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='transactionmodel',
            name='escrow_tx_hash',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='transactionmodel',
            name='status',
            field=models.CharField(
                choices=[
                    ('DRAFT', 'Brouillon'),
                    ('PENDING_AML', 'En attente scoring AML'),
                    ('AML_BLOCKED', 'Bloqué par AML'),
                    ('AML_PENDING_REVIEW', 'Révision AML requise'),
                    ('PROCESSING', 'Paiement en cours'),
                    ('ESCROWED', 'Fonds sécurisés (escrow)'),
                    ('ESCROW_FAILED', 'Échec verrouillage escrow'),
                    ('DELIVERED', 'Livré'),
                    ('PAYMENT_FAILED', 'Paiement échoué'),
                ],
                default='DRAFT',
                max_length=24,
            ),
        ),
    ]
