"""`diaria_valor_override`: de texto livre para dinheiro validado (NOVO-10).

O campo guardava o valor que o servidor recebeu como `CharField(max_length=255)`
sem validador nenhum. `"abc"`, `"-90"` e `"350,00,00"` persistiam e chegavam ao
relatório técnico assinado.

A conversão não pode ser um `AlterField` direto: no PostgreSQL isso vira
`ALTER COLUMN ... TYPE numeric`, que aborta a migração inteira no primeiro
valor que não for número. Por isso o caminho longo — coluna nova, conversão em
Python, troca de nome.

**O que acontece com cada valor existente:**

* `"R$80,00 (saque)"` → `80.00` + observação `"(saque)"`. O documento continua
  imprimindo exatamente `"R$80,00 (saque)"`; nada muda para quem lê.
* `"R$80,00"` → `80.00`, sem observação.
* `"abc"` → valor nulo e o texto original preservado na observação. Não invento
  um número que ninguém digitou, e não jogo fora o que a pessoa escreveu: o RT
  volta a mostrar o valor padrão e a anotação fica visível para alguém corrigir.

A migração imprime as linhas que não puderam virar número, para que a conversão
não seja silenciosa.
"""

from django.db import migrations
from django.db import models

from core.utils.dinheiro import converter_valor_legado


def converter_para_dinheiro(apps, schema_editor):
    PrestacaoServidor = apps.get_model("prestacoes_contas", "PrestacaoServidor")
    nao_convertidos = []

    campos = ["diaria_valor_recebido_tmp", "diaria_valor_override_observacao"]
    for ps in PrestacaoServidor.objects.exclude(diaria_valor_override="").iterator():
        original = ps.diaria_valor_override or ""
        valor, anotacao = converter_valor_legado(original)
        if valor is None and original.strip():
            nao_convertidos.append((ps.pk, original))
        ps.diaria_valor_recebido_tmp = valor
        ps.diaria_valor_override_observacao = anotacao
        ps.save(update_fields=campos)

    if nao_convertidos:
        print(
            f"\n  [NOVO-10] {len(nao_convertidos)} valor(es) de diária não eram "
            "números e viraram observação, sem valor:"
        )
        for pk, texto in nao_convertidos:
            print(f"    PrestacaoServidor #{pk}: {texto!r}")


def reverter_para_texto(apps, schema_editor):
    """Remonta o texto original a partir do número e da anotação."""
    from documentos.services.formatters import format_currency_br

    PrestacaoServidor = apps.get_model("prestacoes_contas", "PrestacaoServidor")
    for ps in PrestacaoServidor.objects.iterator():
        valor = ps.diaria_valor_recebido_tmp
        anotacao = ps.diaria_valor_override_observacao or ""
        partes = [format_currency_br(valor) if valor is not None else "", anotacao]
        ps.diaria_valor_override = " ".join(p for p in partes if p).strip()
        ps.save(update_fields=["diaria_valor_override"])


class Migration(migrations.Migration):

    dependencies = [
        ("prestacoes_contas", "0029_alter_prestacaodocumentoanexo_tipo"),
    ]

    operations = [
        migrations.AddField(
            model_name="prestacaoservidor",
            name="diaria_valor_override_observacao",
            field=models.CharField(
                blank=True,
                default="",
                max_length=255,
                verbose_name="Observação sobre o valor recebido",
            ),
        ),
        migrations.AddField(
            model_name="prestacaoservidor",
            name="diaria_valor_recebido_tmp",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True
            ),
        ),
        migrations.RunPython(converter_para_dinheiro, reverter_para_texto),
        migrations.RemoveField(
            model_name="prestacaoservidor",
            name="diaria_valor_override",
        ),
        migrations.RenameField(
            model_name="prestacaoservidor",
            old_name="diaria_valor_recebido_tmp",
            new_name="diaria_valor_override",
        ),
        migrations.AlterField(
            model_name="prestacaoservidor",
            name="diaria_valor_override",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
                verbose_name="Diária recebida por este servidor",
            ),
        ),
        migrations.AddConstraint(
            model_name="prestacaoservidor",
            constraint=models.CheckConstraint(
                check=models.Q(diaria_valor_override__isnull=True)
                | models.Q(diaria_valor_override__gt=0),
                name="prest_serv_diaria_recebida_positiva",
            ),
        ),
    ]
