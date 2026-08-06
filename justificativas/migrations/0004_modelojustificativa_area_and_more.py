"""NOVO-09 — `ModeloJustificativa` ganha área, espelhando `ModeloMotivoOficio`.

O backfill **duplica cada modelo em todas as áreas**, por decisão registrada no
`docs/CATALOGO_DEFEITOS_2026-08.md`: os modelos que existem hoje servem a todas
as unidades, e atribuir todos a uma só deixaria as demais sem texto nenhum até
recadastrarem.

Ordem importa. O backfill roda **antes** das constraints: enquanto todas as
linhas têm `area=NULL`, `just_modelo_area_nome_unique` não teria o que validar, e
`just_modelo_global_padrao_unique` reprovaria o estado intermediário se a
duplicação já tivesse acontecido sem as originais terem saído do escopo global.
"""

import django.db.models.deletion
from django.db import migrations, models


def _liberar_gatilhos_pendentes(schema_editor):
    """Descarrega os gatilhos de FK adiados antes do próximo ALTER TABLE.

    O PostgreSQL recusa `ALTER TABLE` numa tabela com evento de gatilho
    pendente na mesma transação, e uma migração roda tudo numa transação só.
    Sem isto, a **volta** desta migração morre com
    `cannot ALTER TABLE ... because it has pending trigger events` na hora de
    recriar o `unique` do nome — depois do `RunPython` ter mexido nas linhas.
    Descoberto drilando o rollback, não em produção.

    Só no PostgreSQL: no SQLite da suíte o comando não existe e não é preciso.
    """
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def duplicar_por_area(apps, schema_editor):
    """Uma cópia de cada modelo global em cada área; a original fica com a primeira.

    Sem área cadastrada não há o que duplicar — os modelos seguem globais e a
    tela continua funcionando como antes.
    """
    ModeloJustificativa = apps.get_model("justificativas", "ModeloJustificativa")
    AreaTrabalho = apps.get_model("usuarios", "AreaTrabalho")

    areas = list(AreaTrabalho.objects.order_by("pk"))
    if not areas:
        return

    globais = list(ModeloJustificativa.objects.filter(area__isnull=True).order_by("pk"))
    if not globais:
        return

    copias = [
        ModeloJustificativa(
            area=area,
            nome=modelo.nome,
            texto=modelo.texto,
            ativo=modelo.ativo,
            ordem=modelo.ordem,
            is_padrao=modelo.is_padrao,
            created_at=modelo.created_at,
            updated_at=modelo.updated_at,
        )
        for modelo in globais
        for area in areas[1:]
    ]
    ModeloJustificativa.objects.bulk_create(copias)

    # As originais assumem a primeira área — em vez de serem apagadas e
    # recriadas, para não trocar o `pk` de nada que já aponte para elas.
    ModeloJustificativa.objects.filter(pk__in=[m.pk for m in globais]).update(area=areas[0])
    _liberar_gatilhos_pendentes(schema_editor)


def voltar_a_ser_global(apps, schema_editor):
    """Desfaz a duplicação sem levar junto o que foi criado depois.

    Só apaga a cópia que ainda é **idêntica** a uma linha da primeira área
    (mesmo nome, texto e ordem). Um modelo criado depois da migração, ou uma
    cópia que alguém editou, sobrevive — e fica com área, que é um estado válido
    pelo schema anterior (o campo era anulável, não inexistente).
    """
    ModeloJustificativa = apps.get_model("justificativas", "ModeloJustificativa")
    AreaTrabalho = apps.get_model("usuarios", "AreaTrabalho")

    areas = list(AreaTrabalho.objects.order_by("pk"))
    if not areas:
        return

    primeira = areas[0]
    originais = {
        (m.nome, m.texto, m.ordem)
        for m in ModeloJustificativa.objects.filter(area=primeira)
    }
    for copia in ModeloJustificativa.objects.exclude(area=primeira).exclude(area__isnull=True):
        if (copia.nome, copia.texto, copia.ordem) in originais:
            copia.delete()

    ModeloJustificativa.objects.filter(area=primeira).update(area=None)
    _liberar_gatilhos_pendentes(schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("justificativas", "0003_alter_justificativa_evento"),
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="modelojustificativa",
            name="area",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="modelos_justificativa",
                to="usuarios.areatrabalho",
                verbose_name="Area de trabalho",
            ),
        ),
        # O `unique` global no nome sai antes do backfill: com ele de pé, a
        # segunda área não conseguiria receber uma cópia com o mesmo título.
        migrations.AlterField(
            model_name="modelojustificativa",
            name="nome",
            field=models.CharField(max_length=120),
        ),
        migrations.RunPython(duplicar_por_area, voltar_a_ser_global),
        migrations.AddIndex(
            model_name="modelojustificativa",
            index=models.Index(
                fields=["area", "ordem", "nome"], name="just_modelo_area_ordem_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="modelojustificativa",
            constraint=models.UniqueConstraint(
                condition=models.Q(("area__isnull", True)),
                fields=("nome",),
                name="just_modelo_nome_global_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="modelojustificativa",
            constraint=models.UniqueConstraint(
                condition=models.Q(("area__isnull", False)),
                fields=("area", "nome"),
                name="just_modelo_area_nome_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="modelojustificativa",
            constraint=models.UniqueConstraint(
                condition=models.Q(("area__isnull", False), ("is_padrao", True)),
                fields=("area",),
                name="just_modelo_area_padrao_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="modelojustificativa",
            constraint=models.UniqueConstraint(
                condition=models.Q(("area__isnull", True), ("is_padrao", True)),
                fields=("is_padrao",),
                name="just_modelo_global_padrao_unique",
            ),
        ),
    ]
