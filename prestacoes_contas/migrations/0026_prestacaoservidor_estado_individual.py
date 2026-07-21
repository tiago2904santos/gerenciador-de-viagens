# Move status/arquivamento/finalização de PrestacaoContas para PrestacaoServidor,
# permitindo acompanhamento e abas individuais por servidor do mesmo ofício.

from django.db import migrations, models


def copiar_estado_para_servidores(apps, schema_editor):
    PrestacaoContas = apps.get_model("prestacoes_contas", "PrestacaoContas")
    PrestacaoServidor = apps.get_model("prestacoes_contas", "PrestacaoServidor")

    for prestacao in PrestacaoContas.objects.all().iterator():
        PrestacaoServidor.objects.filter(prestacao_id=prestacao.pk).update(
            status=prestacao.status or "pendente",
            arquivada=bool(prestacao.arquivada),
            arquivada_em=prestacao.arquivada_em,
            finalizada=bool(prestacao.finalizada),
            finalizada_em=prestacao.finalizada_em,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("prestacoes_contas", "0025_prestacaoservidor_data_liberacao_diarias"),
    ]

    operations = [
        migrations.AddField(
            model_name="prestacaoservidor",
            name="status",
            field=models.CharField(
                choices=[
                    ("pendente", "Pendente"),
                    ("em_preenchimento", "Em preenchimento"),
                    ("enviada", "Enviada"),
                    ("aprovada", "Aprovada"),
                    ("reprovada", "Reprovada"),
                ],
                default="pendente",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="prestacaoservidor",
            name="arquivada",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="prestacaoservidor",
            name="arquivada_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="prestacaoservidor",
            name="finalizada",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="prestacaoservidor",
            name="finalizada_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="prestacaoservidor",
            index=models.Index(
                fields=["arquivada", "finalizada", "data_liberacao_diarias"],
                name="prest_serv_aba_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="prestacaoservidor",
            index=models.Index(fields=["status"], name="prest_serv_status_idx"),
        ),
        migrations.RunPython(copiar_estado_para_servidores, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="prestacaocontas",
            name="status",
        ),
        migrations.RemoveField(
            model_name="prestacaocontas",
            name="arquivada",
        ),
        migrations.RemoveField(
            model_name="prestacaocontas",
            name="arquivada_em",
        ),
        migrations.RemoveField(
            model_name="prestacaocontas",
            name="finalizada",
        ),
        migrations.RemoveField(
            model_name="prestacaocontas",
            name="finalizada_em",
        ),
    ]
