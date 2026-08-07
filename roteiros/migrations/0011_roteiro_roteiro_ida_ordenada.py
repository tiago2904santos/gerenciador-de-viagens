"""`NOVO-36`: o elo que faltava da cadeia de datas do roteiro.

`saida_dt <= chegada_dt` ficou de fora do `DB-07` porque reprovava código de
produção: `_atualizar_datas_roteiro_apos_salvar_trechos` derivava o cabeçalho
POSICIONALMENTE, e ao reordenar destinos gravava chegada antes da saída. O
produtor foi corrigido no mesmo PR desta migração para derivar cronologicamente;
sem essa correção, esta constraint troca dado errado por HTTP 500.

**Limite 4 do `AGENTS.md` — rode antes do deploy:**

```sql
SELECT id, saida_dt, chegada_dt FROM roteiros_roteiro
 WHERE saida_dt IS NOT NULL AND chegada_dt IS NOT NULL AND chegada_dt < saida_dt;
```

Esta é a única das 24 constraints do `DB-07` que pode encontrar dado sujo em
produção — as outras 23 vigiam campos que nenhum caminho de código corrompia, e
esta vigia justamente o que o defeito corrompia. Se a query devolver linhas, elas
são roteiros reordenados antes desta correção. Conserto sugerido, que aplica a
regra nova ao dado velho sem tocar nos trechos:

```sql
UPDATE roteiros_roteiro r
   SET chegada_dt = sub.max_chegada
  FROM (SELECT roteiro_id, max(chegada_dt) AS max_chegada
          FROM roteiros_roteirotrecho
         WHERE tipo <> 'RETORNO' AND chegada_dt IS NOT NULL
         GROUP BY roteiro_id) sub
 WHERE r.id = sub.roteiro_id
   AND r.saida_dt IS NOT NULL AND r.chegada_dt IS NOT NULL
   AND r.chegada_dt < r.saida_dt;
```

`scripts/validar_constraints_db07.py` conta as linhas afetadas antes e depois.

**Volta:** `migrate roteiros 0010`. Nenhum dado muda.
"""


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0028_tabela_diaria_derivados_positivos"),
        ("eventos", "0014_evento_periodo_ordenado"),
        ("roteiros", "0010_roteiro_periodo_e_valores"),
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="roteiro",
            constraint=models.CheckConstraint(
                condition=models.Q(("chegada_dt__gte", models.F("saida_dt"))),
                name="roteiro_ida_ordenada",
            ),
        ),
    ]
