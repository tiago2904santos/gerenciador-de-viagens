"""`DB-07`: `valor_15` e `valor_30` da tabela de diárias, positivos no banco.

Os dois são derivados de `valor_24h` pelo `save()` do modelo, e tinham a
positividade apenas como consequência. Derivado é justamente o que um `update()`
cru, uma migração de dados ou uma correção manual grava sem passar pelo `save()`.

**Limite 4 do `AGENTS.md` — rode antes do deploy:**

```sql
SELECT count(*) FROM cadastros_tabeladiaria WHERE valor_15 <= 0 OR valor_30 <= 0;
```

Zero linhas: a migração aplica sem tocar em dado. Qualquer linha: corrija-a antes
(o valor correto é `ROUND(valor_24h * 0.15, 2)` e `ROUND(valor_24h * 0.30, 2)`,
regra `ROUND_HALF_UP` do modelo), senão o `ALTER TABLE ... ADD CONSTRAINT` aborta.

**Volta:** `migrate cadastros 0027` remove as duas constraints. Nenhum dado muda.
"""


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0027_alter_configuracaosistema_options_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="tabeladiaria",
            constraint=models.CheckConstraint(
                condition=models.Q(("valor_15__gt", 0)),
                name="tabela_diaria_valor_15_positivo",
            ),
        ),
        migrations.AddConstraint(
            model_name="tabeladiaria",
            constraint=models.CheckConstraint(
                condition=models.Q(("valor_30__gt", 0)),
                name="tabela_diaria_valor_30_positivo",
            ),
        ),
    ]
