"""`DB-08` fatia 2: dois trechos na mesma posição do mesmo roteiro.

A posição é a sequência do itinerário impresso. Repetida, a ordem passa a
depender do desempate por `pk` e o mesmo roteiro gera dois documentos
diferentes em duas visualizações.

Ao contrário do `RoteiroDestino` da fatia 1, aqui o escritor **não** apaga antes
de recriar: `_salvar_roteiro_avulso_from_roteiro_state` reaproveita a linha por
`id` para preservar campo manual (KM, tempo adicional, fonte da rota). Por isso
esta constraint entra no mesmo commit que converte aquele escritor para dois
passos — o `UPDATE` que empurra as posições para um bloco livre antes de gravar
as finais. Sem os dois passos, uma troca de posição colide no meio do laço.

**Limite 4 do `AGENTS.md` — rode antes do deploy:**

```sql
SELECT roteiro_id, ordem, COUNT(*)
  FROM roteiros_roteirotrecho
 GROUP BY roteiro_id, ordem HAVING COUNT(*) > 1;
```

E, se a consulta acima devolver linha, para ver o que colide:

```sql
SELECT id, roteiro_id, ordem, tipo, origem_cidade_id, destino_cidade_id
  FROM roteiros_roteirotrecho
 WHERE (roteiro_id, ordem) IN (
         SELECT roteiro_id, ordem FROM roteiros_roteirotrecho
          GROUP BY roteiro_id, ordem HAVING COUNT(*) > 1)
 ORDER BY roteiro_id, ordem, id;
```

**A medição do desenvolvimento não vale como evidência aqui.** A tabela
`roteiros_roteirotrecho` tem **0 linhas** no banco de desenvolvimento (os 60
roteiros de lá só têm destino), então "0 grupos duplicados" é o instrumento
cego, não o dado limpo. A consulta acima é o que decide, e é em produção que
ela precisa rodar.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("roteiros", "0012_db08_colecoes_ordenadas"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="roteirotrecho",
            constraint=models.UniqueConstraint(
                fields=("roteiro", "ordem"), name="roteiro_trecho_ordem_unique"
            ),
        ),
    ]
