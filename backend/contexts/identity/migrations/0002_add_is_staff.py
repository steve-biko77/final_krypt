from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="usermodel",
            name="is_staff",
            field=models.BooleanField(default=False),
        ),
    ]
