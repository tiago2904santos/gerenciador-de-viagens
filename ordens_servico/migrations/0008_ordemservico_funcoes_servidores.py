from django.db import migrations, models


def migrar_funcoes_legadas(apps, schema_editor):
    OrdemServico = apps.get_model("ordens_servico", "OrdemServico")
    for ordem in OrdemServico.objects.filter(tipo_necessidade="CAMINHAO").iterator():
        funcoes = dict(ordem.funcoes_servidores or {})
        if ordem.motorista_equipe_id:
            funcoes[str(ordem.motorista_equipe_id)] = "CONDUCAO"
        if ordem.tecnico_equipe_id:
            funcoes[str(ordem.tecnico_equipe_id)] = "TECNICO"
        for servidor_id in (ordem.apoio_montagem_id, ordem.apoio_escolta_id):
            if servidor_id:
                funcoes[str(servidor_id)] = "APOIO"
        if funcoes != (ordem.funcoes_servidores or {}):
            ordem.funcoes_servidores = funcoes
            ordem.save(update_fields=["funcoes_servidores"])


class Migration(migrations.Migration):

    dependencies = [
        ("ordens_servico", "0007_ajusta_modelo_operacao_policial"),
    ]

    operations = [
        migrations.AddField(
            model_name="ordemservico",
            name="funcoes_servidores",
            field=models.JSONField(blank=True, default=dict, verbose_name="Funções dos servidores"),
        ),
        migrations.RunPython(migrar_funcoes_legadas, migrations.RunPython.noop),
    ]
