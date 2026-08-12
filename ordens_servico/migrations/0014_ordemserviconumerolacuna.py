"""BE-15: registra apenas números de OS realmente liberados por exclusão.

A tabela nasce vazia, portanto não há dado legado a validar nem backfill que possa
inventar a origem de uma lacuna. A constraint atua somente sobre linhas novas.

Validação antes do deploy:

    SELECT COUNT(*) FROM ordens_servico_ordemservico
    WHERE area_id IS NULL;

O resultado canônico deve continuar zero (`DB-02`). Backup antes da migração:

    pg_dump --format=custom --file=antes_be15.dump "$DATABASE_URL"

Volta: `migrate ordens_servico 0013_db10_indice_da_ordenacao_real`; a tabela de
lacunas é removida, sem alterar nenhuma Ordem de Serviço emitida.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ordens_servico", "0013_db10_indice_da_ordenacao_real"),
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrdemServicoNumeroLacuna",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("ano", models.PositiveIntegerField(db_index=True)),
                ("numero", models.PositiveIntegerField()),
                ("liberado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "area",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ordens_servico_lacunas",
                        to="usuarios.areatrabalho",
                        verbose_name="Area de trabalho",
                    ),
                ),
            ],
            options={
                "verbose_name": "Número de Ordem de Serviço liberado",
                "verbose_name_plural": "Números de Ordem de Serviço liberados",
                "ordering": ["ano", "numero"],
                "default_manager_name": "all_objects",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("area", "ano", "numero"),
                        name="os_lacuna_area_ano_numero_unique",
                    ),
                ],
            },
            managers=[("all_objects", models.Manager())],
        ),
    ]
