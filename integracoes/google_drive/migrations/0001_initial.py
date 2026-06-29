from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GoogleDriveToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.TextField(verbose_name="Access token")),
                ("refresh_token", models.TextField(blank=True, verbose_name="Refresh token")),
                ("token_uri", models.CharField(max_length=512, verbose_name="Token URI")),
                ("client_id", models.CharField(max_length=512)),
                ("client_secret", models.CharField(max_length=512)),
                ("scopes", models.TextField(verbose_name="Escopos (JSON)")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "usuario",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="google_drive_token",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Usuário",
                    ),
                ),
            ],
            options={
                "verbose_name": "Token Google Drive",
                "verbose_name_plural": "Tokens Google Drive",
            },
        ),
    ]
