import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0022_cargo_area_combustivel_area_unidade_area_and_more"),
        ("ordens_servico", "0005_ordemservico_area"),
    ]

    operations = [
        migrations.AddField(
            model_name="ordemservico",
            name="tipo_necessidade",
            field=models.CharField(
                choices=[
                    ("PADRAO", "Padrão / texto livre"),
                    ("OPERACAO_ANTECIPADA", "Operação policial - ida antecipada"),
                    ("OPERACAO_RETORNO_POSTERIOR", "Operação policial - retorno posterior"),
                    ("CAMINHAO", "Caminhão - dois dias antes e depois"),
                    ("MICROONIBUS", "Micro-ônibus"),
                    ("CERIMONIAL_ANTECIPADO", "Cerimonial - ida antecipada"),
                ],
                default="PADRAO",
                max_length=40,
                verbose_name="Tipo de necessidade",
            ),
        ),
        migrations.AddField(
            model_name="ordemservico",
            name="motorista_equipe",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="cadastros.servidor",
                verbose_name="Motorista",
            ),
        ),
        migrations.AddField(
            model_name="ordemservico",
            name="tecnico_equipe",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="cadastros.servidor",
                verbose_name="Técnico",
            ),
        ),
        migrations.AddField(
            model_name="ordemservico",
            name="apoio_montagem",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="cadastros.servidor",
                verbose_name="Apoio de montagem",
            ),
        ),
        migrations.AddField(
            model_name="ordemservico",
            name="apoio_escolta",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="cadastros.servidor",
                verbose_name="Apoio de escolta",
            ),
        ),
        migrations.AddField(
            model_name="ordemservico",
            name="coordenador_cerimonial",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="cadastros.servidor",
                verbose_name="Coordenação de cerimonial",
            ),
        ),
        migrations.AddField(
            model_name="ordemservico",
            name="apoio_cerimonial",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="cadastros.servidor",
                verbose_name="Apoio de cerimonial",
            ),
        ),
        migrations.AddField(
            model_name="ordemservico",
            name="apoio_preparacao",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="cadastros.servidor",
                verbose_name="Apoio de preparação",
            ),
        ),
    ]
