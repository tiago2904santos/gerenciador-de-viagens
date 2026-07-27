from django.db import migrations
from django.db import models
from django.db.models import Q
import django.db.models.deletion


def criar_piso_2026(apps, schema_editor):
    Configuracao = apps.get_model("oficios", "ConfiguracaoNumeracaoOficio")
    Configuracao.objects.get_or_create(
        area=None,
        ano=2026,
        defaults={"numero_inicial": 75},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("oficios", "0016_modelomotivooficio_area_and_more"),
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfiguracaoNumeracaoOficio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ano", models.PositiveIntegerField()),
                ("numero_inicial", models.PositiveIntegerField(default=1)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "area",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="configuracoes_numeracao_oficio",
                        to="usuarios.areatrabalho",
                    ),
                ),
            ],
            options={"ordering": ["-ano", "area_id"]},
        ),
        migrations.AddConstraint(
            model_name="configuracaonumeracaooficio",
            constraint=models.UniqueConstraint(
                fields=("ano",),
                condition=Q(area__isnull=True),
                name="oficios_numeracao_global_ano_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="configuracaonumeracaooficio",
            constraint=models.UniqueConstraint(
                fields=("area", "ano"),
                condition=Q(area__isnull=False),
                name="oficios_numeracao_area_ano_unique",
            ),
        ),
        migrations.RunPython(criar_piso_2026, migrations.RunPython.noop),
    ]
