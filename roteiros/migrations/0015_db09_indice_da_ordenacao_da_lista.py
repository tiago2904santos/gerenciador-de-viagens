"""`DB-09`: índice de ordenação da lista de roteiros, que só paga depois do `Exists`.

Entra no mesmo PR que troca `Count` + `.exclude(...=0)` por `~Exists(...)` em
`roteiros/selectors.py`, e os dois são uma unidade: separados, um dá 2,9× e o
outro dá **1,0×**.

Medido com 20.000 roteiros distribuídos em três áreas (semeadura do
`scripts/medir_desempenho.py`), mediana de 7 execuções de `EXPLAIN (ANALYZE,
BUFFERS)`, tudo no mesmo banco:

    Count + exclude (hoje)              78,99 ms   7.817 buffers
    Exists                              26,99 ms     659 buffers   2,9x
    Exists + este índice                 8,86 ms     449 buffers   8,9x
    Count + exclude + este índice       78,18 ms   7.776 buffers   1,0x  ← controle

A última linha é o controle e é ela que justifica o índice estar **aqui** e não
no `DB-10`. Naquela fatia eu medi este mesmo índice e ele deu 0,9×; a razão é a
linha de controle: enquanto o `GroupAggregate` varre as duas tabelas filhas
inteiras, ele domina o custo e o `Sort` é troco. Tirada a agregação, o `Limit`
passa a parar na 15ª linha pelo índice.

**Limite 4 do `AGENTS.md`.** `CREATE INDEX` sem `CONCURRENTLY` toma `SHARE` na
tabela e bloqueia escrita enquanto constrói:

```sql
SELECT COUNT(*) FROM roteiros_roteiro;
```

Se a contagem surpreender, criar à mão com `CREATE INDEX CONCURRENTLY
roteiro_area_updated_idx ON roteiros_roteiro (area_id, updated_at DESC);` e
aplicar a migração com `--fake`.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("roteiros", "0014_db08_trecho_ordem_unica"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="roteiro",
            index=models.Index(
                fields=["area", "-updated_at"], name="roteiro_area_updated_idx"
            ),
        ),
    ]
