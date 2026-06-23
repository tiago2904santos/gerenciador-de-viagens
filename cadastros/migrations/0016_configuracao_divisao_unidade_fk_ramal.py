from django.db import migrations, models


def _match_unidade(unidade_model, valor):
    valor = (valor or "").strip()
    if not valor:
        return None
    upper = valor.upper()
    return (
        unidade_model.objects.filter(sigla__iexact=upper).first()
        or unidade_model.objects.filter(nome__iexact=upper).first()
    )


def _backfill_fks(apps, schema_editor):
    Configuracao = apps.get_model("cadastros", "ConfiguracaoSistema")
    Unidade = apps.get_model("cadastros", "Unidade")
    for cfg in Configuracao.objects.all():
        divisao_unidade = _match_unidade(Unidade, cfg.divisao_legacy)
        unidade_unidade = _match_unidade(Unidade, cfg.unidade_legacy)
        cfg.divisao = divisao_unidade
        cfg.unidade = unidade_unidade
        cfg.save(update_fields=["divisao", "unidade"])


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0015_configuracaosistema_pt_sufixo_numero"),
    ]

    operations = [
        migrations.RenameField(
            model_name="configuracaosistema",
            old_name="divisao",
            new_name="divisao_legacy",
        ),
        migrations.RenameField(
            model_name="configuracaosistema",
            old_name="unidade",
            new_name="unidade_legacy",
        ),
        migrations.AddField(
            model_name="configuracaosistema",
            name="divisao",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="+",
                to="cadastros.unidade",
                verbose_name="Divisão",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosistema",
            name="unidade",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="+",
                to="cadastros.unidade",
                verbose_name="Unidade",
            ),
        ),
        migrations.AddField(
            model_name="configuracaosistema",
            name="ramal",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.RunPython(_backfill_fks, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="configuracaosistema",
            name="divisao_legacy",
        ),
        migrations.RemoveField(
            model_name="configuracaosistema",
            name="unidade_legacy",
        ),
    ]
