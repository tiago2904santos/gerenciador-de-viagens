import django.db.models.deletion
from django.db import migrations, models

import eventos.models


class Migration(migrations.Migration):

    dependencies = [
        ("eventos", "0006_alter_evento_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="EventoDocumentoSolicitacao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "evento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documentos_solicitacao",
                        to="eventos.evento",
                    ),
                ),
                (
                    "arquivo",
                    models.FileField(upload_to=eventos.models.evento_solicitacao_upload_to),
                ),
                ("nome_original", models.CharField(blank=True, default="", max_length=255)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Documento de solicitação do evento",
                "verbose_name_plural": "Documentos de solicitação do evento",
                "ordering": ["criado_em"],
            },
        ),
    ]
