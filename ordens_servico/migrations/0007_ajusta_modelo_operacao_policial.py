from django.db import migrations, models


def migrar_operacao_antecipada_para_posterior(apps, schema_editor):
    OrdemServico = apps.get_model("ordens_servico", "OrdemServico")
    OrdemServico.objects.filter(tipo_necessidade="OPERACAO_ANTECIPADA").update(
        tipo_necessidade="OPERACAO_RETORNO_POSTERIOR"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("ordens_servico", "0006_ordemservico_tipo_necessidade_funcoes"),
    ]

    operations = [
        migrations.RunPython(migrar_operacao_antecipada_para_posterior, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="ordemservico",
            name="tipo_necessidade",
            field=models.CharField(
                choices=[
                    ("PADRAO", "Padrão / texto livre"),
                    ("OPERACAO_RETORNO_POSTERIOR", "Operação policial - um dia posterior"),
                    ("CAMINHAO", "Caminhão - dois dias antes e depois"),
                    ("MICROONIBUS", "Micro-ônibus"),
                    ("CERIMONIAL_ANTECIPADO", "Cerimonial - ida antecipada"),
                ],
                default="PADRAO",
                max_length=40,
                verbose_name="Tipo de necessidade",
            ),
        ),
    ]
