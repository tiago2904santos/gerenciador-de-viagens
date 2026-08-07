"""`DB-02`, grupo operacional: `area` deixa de aceitar NULL.

Um dos oito `NOT NULL` do grupo 1 do enunciado reescrito pelo `NOVO-34`. O
registro operacional sem área era o "balde legado" que qualquer usuário sem
vínculo enxergava inteiro (`core/tenancy.py`), e a escrita fora de request
gravava órfão em silêncio — agora falha alto, no banco.

**Limite 4 do `AGENTS.md` — valide antes do deploy:**

```sql
SELECT count(*) FROM planos_trabalho_planotrabalho WHERE area_id IS NULL;
```

Tem de devolver 0. Não devolveu? `python manage.py backfill_legacy_areas
--area SIGLA --commit`, com backup antes. Os dois já estão na ordem certa no
`deploy.yml`: o backup roda antes do checkout e o `check --deploy` (`NOVO-12`)
aborta o deploy no `core.E001` enquanto houver órfão — esta migração nunca
encontra NULL em produção. `scripts/validar_not_null_db02.py` conta as oito
tabelas de uma vez.

**Volta:** `migrate planos_trabalho 0022_db08_colecoes_ordenadas`. Nenhum dado muda.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("planos_trabalho", "0022_db08_colecoes_ordenadas"),
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="planotrabalho",
            name="area",
            field=models.ForeignKey(
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="planos_trabalho",
                to="usuarios.areatrabalho",
                verbose_name="Area de trabalho",
            ),
        ),
    ]
