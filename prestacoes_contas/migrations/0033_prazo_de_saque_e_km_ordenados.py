"""`DB-07`: prazo de saque depois da liberação, e km final depois do inicial.

O prazo limite é calculado a partir da data de liberação das diárias. Limite
anterior à liberação deixa o servidor com prazo negativo e o tira da aba de
pendentes sem nunca ter sido pago.

O km do diário de bordo é peça de prestação de contas de combustível: invertido,
dá rodagem negativa no documento assinado. `gte`, não `gt` — trecho sem
deslocamento tem os dois iguais.

**Limite 4 do `AGENTS.md` — rode antes do deploy:**

```sql
SELECT id FROM prestacoes_contas_prestacaoservidor
 WHERE data_liberacao_diarias IS NOT NULL AND prazo_limite_saque IS NOT NULL
   AND prazo_limite_saque < data_liberacao_diarias;

SELECT id FROM prestacoes_contas_diariobordotrecho
 WHERE km_inicial IS NOT NULL AND km_final IS NOT NULL AND km_final < km_inicial;
```

**Volta:** `migrate prestacoes_contas 0032`. Nenhum dado muda.

Nota sobre `prest_serv_diaria_recebida_positiva`, que aparece aqui como
`RemoveConstraint` + `AddConstraint`. Ela existia com o kwarg `check=`,
depreciado desde o Django 5.1 e removido no 6.0 — o import do modelo já emitia
`RemovedInDjango60Warning`. Passou a sair da fábrica `core.constraints.positivo`,
que **não** traz o ramo `campo IS NULL` que a versão antiga tinha. O
comportamento é idêntico (um `CHECK` que resulta em `NULL` passa em SQL, e o
`Q.check()` do `full_clean()` chega ao mesmo resultado — os dois foram medidos),
mas a condição textual muda, então o banco faz `DROP` e `ADD` da constraint.
Nenhuma linha é lida ou escrita nessa troca.
"""


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0028_tabela_diaria_derivados_positivos"),
        ("prestacoes_contas", "0032_prestacao_servidor_removida_em"),
        ("roteiros", "0009_alter_roteiro_options_alter_roteiro_managers"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="prestacaoservidor",
            name="prest_serv_diaria_recebida_positiva",
        ),
        migrations.AddConstraint(
            model_name="diariobordotrecho",
            constraint=models.CheckConstraint(
                condition=models.Q(("km_final__gte", models.F("km_inicial"))),
                name="diario_trecho_km_ordenado",
            ),
        ),
        migrations.AddConstraint(
            model_name="prestacaoservidor",
            constraint=models.CheckConstraint(
                condition=models.Q(("diaria_valor_override__gt", 0)),
                name="prest_serv_diaria_recebida_positiva",
            ),
        ),
        migrations.AddConstraint(
            model_name="prestacaoservidor",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("prazo_limite_saque__gte", models.F("data_liberacao_diarias"))
                ),
                name="prest_serv_prazo_apos_liberacao",
            ),
        ),
    ]
