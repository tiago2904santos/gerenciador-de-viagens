"""`DB-08` fatia 2: duas linhas do diário de bordo na mesma posição.

O diário de bordo é peça de prestação de contas de combustível e vai assinado.
Posição repetida torna a planilha não determinística entre duas gerações do
mesmo documento — e o que muda de lugar é KM inicial/final.

Irmã da `roteiros/0013`: aqui também o escritor (`sincronizar_trechos`)
reaproveita a linha por `id`, para preservar o KM e o abastecimento que o
usuário digitou. A constraint entra junto com a conversão daquele escritor para
dois passos.

**Limite 4 do `AGENTS.md` — rode antes do deploy:**

```sql
SELECT diario_id, ordem, COUNT(*)
  FROM prestacoes_contas_diariobordotrecho
 GROUP BY diario_id, ordem HAVING COUNT(*) > 1;
```

**A medição do desenvolvimento não vale como evidência aqui:** a tabela tem
**0 linhas** naquele banco, e `prestacoes_contas_diariobordo` também. "0 grupos
duplicados" ali é instrumento cego. A consulta é para produção.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("prestacoes_contas", "0033_prazo_de_saque_e_km_ordenados"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="diariobordotrecho",
            constraint=models.UniqueConstraint(
                fields=("diario", "ordem"), name="diario_trecho_ordem_unique"
            ),
        ),
    ]
