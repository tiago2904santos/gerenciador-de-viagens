"""`DB-07`: fim do evento do termo nunca antes do início.

Estas duas datas viram o período impresso no termo de autorização assinado — o
documento que autoriza o afastamento.

**Limite 4 do `AGENTS.md` — rode antes do deploy:**

```sql
SELECT id, data_evento_inicio, data_evento_fim FROM termos_termoautorizacao
 WHERE data_evento_inicio IS NOT NULL AND data_evento_fim IS NOT NULL
   AND data_evento_fim < data_evento_inicio;
```

**Volta:** `migrate termos 0008`. Nenhum dado muda.
"""


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0028_tabela_diaria_derivados_positivos"),
        ("eventos", "0014_evento_periodo_ordenado"),
        ("oficios", "0018_alter_configuracaonumeracaooficio_options_and_more"),
        ("termos", "0008_alter_termoautorizacao_options_and_more"),
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="termoautorizacao",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("data_evento_fim__gte", models.F("data_evento_inicio"))
                ),
                name="termo_periodo_ordenado",
            ),
        ),
    ]
