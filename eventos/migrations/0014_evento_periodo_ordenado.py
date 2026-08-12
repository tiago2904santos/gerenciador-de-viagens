"""`DB-07`: fim do evento nunca antes do início.

O período do evento é copiado para ofício, termo, plano de trabalho e ordem de
serviço. Invertido aqui, sai invertido nos cinco documentos.

`gte`, não `gt`: evento de um dia tem fim igual ao início — é o caso comum, não a
exceção.

**Limite 4 do `AGENTS.md` — rode antes do deploy:**

```sql
SELECT id, data_inicio, data_fim FROM eventos_evento
 WHERE data_inicio IS NOT NULL AND data_fim IS NOT NULL AND data_fim < data_inicio;
```

**Volta:** `migrate eventos 0013`. Nenhum dado muda.
"""


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0028_tabela_diaria_derivados_positivos"),
        ("eventos", "0013_alter_evento_options_and_more"),
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="evento",
            constraint=models.CheckConstraint(
                condition=models.Q(("data_fim__gte", models.F("data_inicio"))),
                name="evento_periodo_ordenado",
            ),
        ),
    ]
