"""`DB-10`: índice composto para a ordenação que a lista de OS realmente usa.

`ordens_servico/selectors.py` recorta por área e ordena por `(-ano, -numero)`.
Sem um índice nessa ordem, o PostgreSQL usa o índice da FK de área, lê **a área
inteira**, ordena em memória e descarta tudo menos os 20 da página.

Medido com 20.000 OS distribuídas em três áreas (`scripts/medir_desempenho.py`
como semeador), mediana de 7 execuções de `EXPLAIN (ANALYZE, BUFFERS)` dos dois
lados, no mesmo banco:

    sem o índice   9,231 ms   136 buffers   Index Scan (FK) rows=6666 → top-N heapsort → Limit 20
    com o índice   0,144 ms     4 buffers   Index Scan (este) → Limit 20

**A constraint única parcial que já existe não serve para isto.** Ela é
`(area, ano, numero) WHERE ano IS NOT NULL AND numero IS NOT NULL`: por ser
parcial o planner não a usa nesta consulta, e a ordem dela é ascendente.

**Este índice é o único desta família que a medição sustenta.** As outras quatro
listas que ordenavam em memória foram medidas com o índice análogo e não ganham:

    oficios            143,2 → 120,9 ms   (1,2×)  o Sort some, o tempo não anda
    planos_trabalho    125,9 → 126,8 ms   (1,0×)
    justificativas      24,4 →  21,3 ms   (1,1×)  e os buffers pioram muito
    roteiros           555,7 → 611,7 ms   (0,9×)  continua ordenando

Nelas o gargalo é outro — agregação antes do `LIMIT` em `roteiros` (o `DB-09`) e
`select_native` resolvido por `Nested Loop` com `Join Filter` em `oficios` e
`planos_trabalho`. Índice de ordenação ali seria custo de escrita sem ganho de
leitura.

**Limite 4 do `AGENTS.md`.** `CREATE INDEX` sem `CONCURRENTLY` toma `SHARE` na
tabela e bloqueia escrita enquanto constrói. Para conferir o tamanho antes do
deploy:

```sql
SELECT COUNT(*) FROM ordens_servico_ordemservico;
```

Em tabela desta ordem de grandeza a construção é de segundos. Se a contagem
surpreender, criar à mão com `CREATE INDEX CONCURRENTLY os_area_ano_numero_idx
ON ordens_servico_ordemservico (area_id, ano DESC, numero DESC);` e aplicar a
migração com `--fake`.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ordens_servico", "0012_area_obrigatoria"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="ordemservico",
            index=models.Index(
                fields=["area", "-ano", "-numero"], name="os_area_ano_numero_idx"
            ),
        ),
    ]
