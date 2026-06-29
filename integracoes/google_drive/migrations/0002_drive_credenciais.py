from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("google_drive", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DriveCredenciais",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("access_token", models.TextField()),
                ("refresh_token", models.TextField()),
                ("token_expiry", models.DateTimeField(blank=True, null=True)),
                ("scope", models.TextField(blank=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Credencial Google Drive",
                "verbose_name_plural": "Credenciais Google Drive",
            },
        ),
    ]
