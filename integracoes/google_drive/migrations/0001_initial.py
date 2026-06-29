import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("documentos", "0004_drop_assinaturas_tables"),
    ]

    operations = [
        migrations.CreateModel(
            name="DriveArquivo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "artefato",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="drive_arquivo",
                        to="documentos.documentoartefato",
                    ),
                ),
                ("file_id", models.CharField(max_length=200)),
                ("url", models.URLField(blank=True, max_length=500)),
                ("nome", models.CharField(blank=True, max_length=255)),
                ("mime_type", models.CharField(blank=True, max_length=64)),
                ("mock", models.BooleanField(default=False)),
                ("enviado_em", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Arquivo no Drive",
                "verbose_name_plural": "Arquivos no Drive",
                "ordering": ["-enviado_em"],
            },
        ),
    ]
