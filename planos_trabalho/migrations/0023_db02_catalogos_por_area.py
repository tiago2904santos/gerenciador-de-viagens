"""`DB-02` grupo 2 — os catálogos semeados passam a ter dono, um por área.

`AtividadePlanoTrabalho` (11), `ProgramaSolicitante` (3) e `HorarioAtendimento` (3)
nascem sem área, criados pelos seeds de `0002`, `0003` e `0008`. O `NOVO-34` os
chamou de "catálogo com padrão global" e deixou em aberto se o global era usado.

**A medição respondeu que não, e isso muda o que a duplicação significa.** Toda
leitura desses três passa por `filter_queryset_by_area`, que é estrito
(`core/tenancy.py:63-67`, `filter(area=area)`, sem união com o balde nulo):
`selectors.py:136,175,183`, `services.py:767,870`, `forms.py:188,207,743`. Medido
em 07/08/2026 nas três áreas do banco de desenvolvimento: as 17 linhas destes três
modelos são vistas por **zero** usuários com área. Só quem não tem área as enxerga.

Ou seja: não estamos repartindo um catálogo compartilhado — estamos **dando a cada
área um catálogo que hoje ela não tem**. Para o usuário é conteúdo que aparece, não
conteúdo que muda de dono.

Decisão do usuário em 07/08/2026, registrada no §8 do plano mestre: duplicar por
área, seguindo o `NOVO-09`. Este arquivo copia a forma daquele, inclusive a parte
que custou caro lá.
"""

from django.db import migrations

#: **`_base_manager`, nunca `objects`.** Modelo histórico de migração não recebe o
#: manager customizado: com `default_manager_name` definido (o `AreaScopedManager`
#: do `BE-09`), `objects` simplesmente não existe ali. E o erro só aparece na
#: **volta**, porque a ida sai cedo quando não há área — foi assim que ele apareceu,
#: drilando o rollback num banco de teste.


#: Modelos deste app que recebem cópia por área, com os campos que **não** entram
#: na cópia. `id` é novo em cada cópia; `area` é o que estamos atribuindo.
MODELOS = ("AtividadePlanoTrabalho", "ProgramaSolicitante", "HorarioAtendimento")

NAO_COPIAR = {"id", "area"}


def _liberar_gatilhos_pendentes(schema_editor):
    """Descarrega os gatilhos de FK adiados antes do próximo `ALTER TABLE`.

    Herdado do `NOVO-09`, onde foi descoberto drilando o rollback: o PostgreSQL
    recusa `ALTER TABLE` numa tabela com evento de gatilho pendente na mesma
    transação, e uma migração roda tudo numa transação só. Sem isto, a **volta**
    desta migração morre com `cannot ALTER TABLE ... because it has pending
    trigger events`.

    Só no PostgreSQL: no SQLite da suíte o comando não existe e não é preciso.
    """
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def _copiar(modelo, origem, area):
    campos = {
        f.attname if f.is_relation else f.name: getattr(
            origem, f.attname if f.is_relation else f.name,
        )
        for f in modelo._meta.concrete_fields
        if f.name not in NAO_COPIAR
    }
    return modelo(area=area, **campos)


def duplicar_por_area(apps, schema_editor):
    """Uma cópia em cada área; a **original fica com a primeira**, não sobra global.

    Sem área cadastrada não há o que duplicar — é exatamente o caso da instalação
    nova, em que os seeds acabaram de rodar e nenhuma área existe ainda. Ali os
    catálogos seguem globais e a tela continua como antes, igual ao `NOVO-09`.
    """
    AreaTrabalho = apps.get_model("usuarios", "AreaTrabalho")
    areas = list(AreaTrabalho._base_manager.order_by("pk"))
    if not areas:
        return

    primeira, demais = areas[0], areas[1:]

    for nome in MODELOS:
        modelo = apps.get_model("planos_trabalho", nome)
        globais = list(modelo._base_manager.filter(area__isnull=True).order_by("pk"))
        if not globais:
            continue

        if demais:
            modelo._base_manager.bulk_create(
                [_copiar(modelo, linha, area) for area in demais for linha in globais]
            )
        modelo._base_manager.filter(pk__in=[linha.pk for linha in globais]).update(
            area=primeira,
        )

    _liberar_gatilhos_pendentes(schema_editor)


def devolver_ao_global(apps, schema_editor):
    """Volta: mantém uma linha por chave, sem área, e descarta as demais cópias.

    Não é o inverso exato — cópia que o usuário editou depois perde a edição. Está
    escrito aqui porque migração irreversível é o que o `QA-03` proíbe, e porque a
    volta precisa deixar o banco num estado que a ida saiba reprocessar.
    """
    AreaTrabalho = apps.get_model("usuarios", "AreaTrabalho")
    areas = list(AreaTrabalho._base_manager.order_by("pk"))
    if not areas:
        return

    chave_por_modelo = {
        "AtividadePlanoTrabalho": "codigo",
        "ProgramaSolicitante": "nome",
        "HorarioAtendimento": "faixa",
    }

    for nome in MODELOS:
        modelo = apps.get_model("planos_trabalho", nome)
        chave = chave_por_modelo[nome]
        vistos = set()
        for linha in modelo._base_manager.filter(area__isnull=False).order_by("pk"):
            valor = getattr(linha, chave)
            if valor in vistos:
                linha.delete()
            else:
                vistos.add(valor)
                modelo._base_manager.filter(pk=linha.pk).update(area=None)

    _liberar_gatilhos_pendentes(schema_editor)


class Migration(migrations.Migration):
    dependencies = [
        ("planos_trabalho", "0022_db08_colecoes_ordenadas"),
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(duplicar_por_area, devolver_ao_global),
    ]
