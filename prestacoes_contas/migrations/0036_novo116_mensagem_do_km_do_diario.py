"""`NOVO-116`: a violação do km do diário passa a ter mensagem para o operador.

O `diario_trecho_km_ordenado` entrou na `0033` com a mensagem padrão do Django —
`Restrição "diario_trecho_km_ordenado" foi violada.` —, que serve para log e não
para a tela de quem digita o km. `violation_error_message` troca o texto no caminho
Python (`validate_constraints()`), usado agora pelo autosave do diário e pelo formset.

**Nada muda no banco.** Só o texto do erro faz parte do `deconstruct()`; a condição
`km_final >= km_inicial` é a mesma. Confirmado antes de versionar:

```
$ python manage.py sqlmigrate prestacoes_contas 0036
BEGIN;
-- Alter constraint diario_trecho_km_ordenado on diariobordotrecho
-- (no-op)
COMMIT;
```

**Limite 4 do `AGENTS.md`:** sem DDL e sem leitura de linha, não há dado a validar
nesta migração. A query da regra em si continua sendo a da `0033`, e continua valendo
antes do deploy, porque é lá que o `CHECK` de fato entra:

```sql
SELECT id FROM prestacoes_contas_diariobordotrecho
 WHERE km_inicial IS NOT NULL AND km_final IS NOT NULL AND km_final < km_inicial;
```

**Volta:** `migrate prestacoes_contas 0035`. Nenhum dado muda.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("prestacoes_contas", "0035_db08_diario_trecho_ordem_unica"),
        ("roteiros", "0015_db09_indice_da_ordenacao_da_lista"),
    ]

    operations = [
        migrations.AlterConstraint(
            model_name="diariobordotrecho",
            name="diario_trecho_km_ordenado",
            constraint=models.CheckConstraint(
                condition=models.Q(("km_final__gte", models.F("km_inicial"))),
                name="diario_trecho_km_ordenado",
                violation_error_message="O km final não pode ser menor que o km inicial.",
            ),
        ),
    ]
