from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("google_drive", "0002_drive_credenciais"),
    ]

    operations = [
        migrations.AddField(
            model_name="drivecredenciais",
            name="pasta_raiz_id",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="drivecredenciais",
            name="pasta_raiz_nome",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
