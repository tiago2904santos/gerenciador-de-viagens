import django.db.models.deletion
from django.db import migrations, models


def _upload_to(instance, filename):
    return f"oficios/{instance.oficio_id or 'novo'}/solicitacoes/{filename}"


class Migration(migrations.Migration):

    dependencies = [
        ("oficios", "0008_oficio_evento"),
    ]

    operations = [
        migrations.CreateModel(
            name="OficioSolicitacaoAnexo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "oficio",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="solicitacao_anexos",
                        to="oficios.oficio",
                    ),
                ),
                (
                    "arquivo",
                    models.FileField(upload_to=_upload_to),
                ),
                ("nome_original", models.CharField(blank=True, default="", max_length=255)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Anexo de solicitação do ofício",
                "verbose_name_plural": "Anexos de solicitação do ofício",
                "ordering": ["criado_em"],
            },
        ),
    ]
