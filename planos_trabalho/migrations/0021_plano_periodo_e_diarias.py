"""`DB-07`: período e valores de diária do plano de trabalho, defendidos pelo banco.

Sete constraints: o par de datas em `PlanoTrabalho` e em `EventoPlano` (no modo
multi-evento é o segundo que carrega o período de cada evento, e a `Meta.ordering`
ordena por ele), mais os seis valores de diária — unitário, total e a variante
combinada. Os valores são **calculados** e gravados; zero é legítimo (plano sem
diária), negativo só sai de conta errada e daqui vai direto para o documento.

**Limite 4 do `AGENTS.md` — rode antes do deploy:**

```sql
SELECT id FROM planos_trabalho_planotrabalho
 WHERE (data_evento_inicio IS NOT NULL AND data_evento_fim IS NOT NULL
        AND data_evento_fim < data_evento_inicio)
    OR diarias_valor_unitario < 0 OR diarias_valor_total < 0
    OR diarias_combinada_valor_unitario < 0 OR diarias_combinada_valor_total < 0;

SELECT id FROM planos_trabalho_eventoplano
 WHERE (data_evento_inicio IS NOT NULL AND data_evento_fim IS NOT NULL
        AND data_evento_fim < data_evento_inicio)
    OR diarias_valor_unitario < 0 OR diarias_valor_total < 0;
```

**Volta:** `migrate planos_trabalho 0020`. Nenhum dado muda.
"""


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0028_tabela_diaria_derivados_positivos"),
        ("eventos", "0014_evento_periodo_ordenado"),
        ("planos_trabalho", "0020_alter_atividadeplanotrabalho_options_and_more"),
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="eventoplano",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("data_evento_fim__gte", models.F("data_evento_inicio"))
                ),
                name="evento_plano_periodo_ordenado",
            ),
        ),
        migrations.AddConstraint(
            model_name="eventoplano",
            constraint=models.CheckConstraint(
                condition=models.Q(("diarias_valor_unitario__gte", 0)),
                name="evento_plano_diaria_unitaria_nao_negativa",
            ),
        ),
        migrations.AddConstraint(
            model_name="eventoplano",
            constraint=models.CheckConstraint(
                condition=models.Q(("diarias_valor_total__gte", 0)),
                name="evento_plano_diaria_total_nao_negativa",
            ),
        ),
        migrations.AddConstraint(
            model_name="planotrabalho",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("data_evento_fim__gte", models.F("data_evento_inicio"))
                ),
                name="plano_periodo_ordenado",
            ),
        ),
        migrations.AddConstraint(
            model_name="planotrabalho",
            constraint=models.CheckConstraint(
                condition=models.Q(("diarias_valor_unitario__gte", 0)),
                name="plano_diaria_unitaria_nao_negativa",
            ),
        ),
        migrations.AddConstraint(
            model_name="planotrabalho",
            constraint=models.CheckConstraint(
                condition=models.Q(("diarias_valor_total__gte", 0)),
                name="plano_diaria_total_nao_negativa",
            ),
        ),
        migrations.AddConstraint(
            model_name="planotrabalho",
            constraint=models.CheckConstraint(
                condition=models.Q(("diarias_combinada_valor_unitario__gte", 0)),
                name="plano_diaria_comb_unitaria_nao_negativa",
            ),
        ),
        migrations.AddConstraint(
            model_name="planotrabalho",
            constraint=models.CheckConstraint(
                condition=models.Q(("diarias_combinada_valor_total__gte", 0)),
                name="plano_diaria_comb_total_nao_negativa",
            ),
        ),
    ]
