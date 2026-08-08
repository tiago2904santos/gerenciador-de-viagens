"""`DB-12`: o índice de área cruzada com período na trilha de auditoria.

`AuditEvent` já tinha 10 índices, com coluna única tanto em `area_id` (auto da FK)
quanto em `created_at` (`db_index=True`). O que faltava era o **composto**, para a
consulta que cruza os dois eixos — que é a do admin do Django, o **único** leitor
da trilha (`core/admin.py`; não há view, selector nem relatório que a consulte).

**A medição não justifica este índice na escala de hoje, e está registrado assim
de propósito.** Com 60.000 eventos, o planner só passa a escolhê-lo quando a área
fica seletiva o bastante:

    áreas   sem       com       ganho   plano
        3   0,30 ms   0,26 ms    1,1x   Index Scan Backward por `created_at` — ignora este
       20   0,49 ms   0,47 ms    1,0x   idem
      100   1,51 ms   0,08 ms   18,4x   Index Scan using core_audit_area_periodo_idx

Com poucas áreas, uma varredura para trás pelo índice de `created_at` acha as 100
linhas da página quase de imediato, e o filtro por área sai de graça.

Entrou por decisão do usuário em 08/08/2026, como folga de crescimento: o número
de áreas em produção não é observável a partir do ambiente de desenvolvimento (que
tem 3, e as três são artefato de teste). Se a trilha ficar cara de **escrever**
antes de as áreas crescerem — ela recebe uma linha por save auditado, em 11 apps —
a remoção é uma migração de uma linha.

**Limite 4 do `AGENTS.md`.** `CREATE INDEX` sem `CONCURRENTLY` toma `SHARE` e
bloqueia escrita enquanto constrói. Numa trilha de auditoria isso pode ser grande:

```sql
SELECT COUNT(*) FROM core_auditevent;
SELECT COUNT(DISTINCT area_id) FROM core_auditevent;
```

A segunda consulta é a que diz se este índice vale alguma coisa hoje. Se a tabela
for grande, criar à mão com `CREATE INDEX CONCURRENTLY core_audit_area_periodo_idx
ON core_auditevent (area_id, created_at DESC, id DESC);` e aplicar com `--fake`.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_alter_auditevent_options_alter_auditevent_managers"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(
                fields=["area", "-created_at", "-id"], name="core_audit_area_periodo_idx"
            ),
        ),
    ]
