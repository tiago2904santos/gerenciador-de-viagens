"""`DB-06`: marca de saída da equipe, no lugar do `DELETE` em cascata.

Coluna anulável, sem constraint e sem índice novo: não existe dado existente
capaz de violá-la, e por isso não há query de validação a rodar antes (limite 4
do `AGENTS.md` cobre constraint/índice). `NULL` é exatamente o significado certo
para toda linha que já existe — "este servidor está na equipe" —, então a
migração não precisa de passo de dados.

`AlterModelOptions` fixa `default_manager_name = "objects"`, que é o manager que
esconde as linhas removidas (`PrestacaoServidorAtivosManager`). É opção de
estado, não toca no banco.

**Volta:** `migrate prestacoes_contas 0031` derruba a coluna. Quem tiver linha
com `removida_em` preenchida volta a exibi-la na equipe do ofício — nada é
perdido, mas a prestação passa a listar servidor que saiu. Para conferir antes:

    SELECT count(*) FROM prestacoes_contas_prestacaoservidor
     WHERE removida_em IS NOT NULL;
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "prestacoes_contas",
            "0031_alter_modelotextorelatoriotecnico_options_and_more",
        ),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="prestacaoservidor",
            options={
                "default_manager_name": "objects",
                "ordering": ["prestacao", "pk"],
                "verbose_name": "Servidor da prestação",
                "verbose_name_plural": "Servidores da prestação",
            },
        ),
        migrations.AddField(
            model_name="prestacaoservidor",
            name="removida_em",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Removida da equipe em"
            ),
        ),
    ]
