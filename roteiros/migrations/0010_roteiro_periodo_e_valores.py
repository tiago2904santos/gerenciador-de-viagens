"""`DB-07`: a cadeia de datas do roteiro e os valores não-negativos.

O roteiro tem quatro datetimes em cadeia — `saida_dt` → `chegada_dt` →
`retorno_saida_dt` → `retorno_chegada_dt`. Entram **dois** dos três elos
consecutivos e o limite externo (`saida_dt` ≤ `retorno_chegada_dt`): como cada
constraint tolera nulo, um `chegada_dt` vazio quebraria a transitividade, e o par
externo é justamente o que o motor de diárias usa para contar dia de viagem.

O terceiro elo, `saida_dt` ≤ `chegada_dt`, **ficou de fora** e é o `NOVO-36`. Ele
existiu nesta migração e reprovou código de produção: reordenar destinos preserva
os horários de cada trecho e deixa o roteiro com chegada antes da saída
(`roteiros/roteiro_logic.py:219`). Aplicá-lo antes de consertar o produtor trocaria
dado silenciosamente errado por erro 500 numa tela de uso diário.

Mais `valor_diarias` e as duas distâncias, não-negativos, no roteiro; e o par do
trecho com a distância dele.

**Limite 4 do `AGENTS.md` — rode antes do deploy:**

```sql
SELECT id FROM roteiros_roteiro
 WHERE (chegada_dt IS NOT NULL AND retorno_saida_dt IS NOT NULL
        AND retorno_saida_dt < chegada_dt)
    OR (retorno_saida_dt IS NOT NULL AND retorno_chegada_dt IS NOT NULL
        AND retorno_chegada_dt < retorno_saida_dt)
    OR (saida_dt IS NOT NULL AND retorno_chegada_dt IS NOT NULL
        AND retorno_chegada_dt < saida_dt)
    OR valor_diarias < 0 OR rota_distancia_calculada_km < 0
    OR rota_distancia_manual_km < 0;

SELECT id FROM roteiros_roteirotrecho
 WHERE (saida_dt IS NOT NULL AND chegada_dt IS NOT NULL AND chegada_dt < saida_dt)
    OR distancia_km < 0;
```

**Volta:** `migrate roteiros 0009`. Nenhum dado muda.
"""


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0028_tabela_diaria_derivados_positivos"),
        ("eventos", "0014_evento_periodo_ordenado"),
        ("roteiros", "0009_alter_roteiro_options_alter_roteiro_managers"),
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="roteiro",
            constraint=models.CheckConstraint(
                condition=models.Q(("retorno_saida_dt__gte", models.F("chegada_dt"))),
                name="roteiro_permanencia_ordenada",
            ),
        ),
        migrations.AddConstraint(
            model_name="roteiro",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("retorno_chegada_dt__gte", models.F("retorno_saida_dt"))
                ),
                name="roteiro_volta_ordenada",
            ),
        ),
        migrations.AddConstraint(
            model_name="roteiro",
            constraint=models.CheckConstraint(
                condition=models.Q(("retorno_chegada_dt__gte", models.F("saida_dt"))),
                name="roteiro_periodo_ordenado",
            ),
        ),
        migrations.AddConstraint(
            model_name="roteiro",
            constraint=models.CheckConstraint(
                condition=models.Q(("valor_diarias__gte", 0)),
                name="roteiro_valor_diarias_nao_negativo",
            ),
        ),
        migrations.AddConstraint(
            model_name="roteiro",
            constraint=models.CheckConstraint(
                condition=models.Q(("rota_distancia_calculada_km__gte", 0)),
                name="roteiro_distancia_calc_nao_negativa",
            ),
        ),
        migrations.AddConstraint(
            model_name="roteiro",
            constraint=models.CheckConstraint(
                condition=models.Q(("rota_distancia_manual_km__gte", 0)),
                name="roteiro_distancia_manual_nao_negativa",
            ),
        ),
        migrations.AddConstraint(
            model_name="roteirotrecho",
            constraint=models.CheckConstraint(
                condition=models.Q(("chegada_dt__gte", models.F("saida_dt"))),
                name="roteiro_trecho_ordenado",
            ),
        ),
        migrations.AddConstraint(
            model_name="roteirotrecho",
            constraint=models.CheckConstraint(
                condition=models.Q(("distancia_km__gte", 0)),
                name="roteiro_trecho_distancia_nao_negativa",
            ),
        ),
    ]
