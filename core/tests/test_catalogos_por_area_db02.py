"""`DB-02` grupo 2 — os catálogos semeados ganham dono, um por área.

O `NOVO-34` classificou `TipoEvento`, `AtividadePlanoTrabalho`, `ProgramaSolicitante`
e `HorarioAtendimento` como "catálogo com padrão global" e deixou uma pergunta em
aberto: **o global é usado hoje?**

A medição respondeu que não, e isso muda o que a duplicação significa. Toda leitura
desses quatro passa por `filter_queryset_by_area`, que é estrito
(`core/tenancy.py:69-71` — `filter(area=area)`, sem união com o balde nulo). As 22
linhas de seed são vistas por **zero** usuários com área; só quem não tem área as
enxerga. As constraints `*_global_unique` provam que um namespace global foi
projetado, mas nenhum leitor o realiza.

Ou seja: não se está repartindo um catálogo compartilhado — está-se **dando a cada
área um catálogo que ela hoje não tem**. Para o usuário é conteúdo que aparece.

Decisão do usuário em 07/08/2026 (§8 do plano mestre): duplicar por área, seguindo
o `NOVO-09`.
"""

from __future__ import annotations

from importlib import import_module

from django.apps import apps as apps_reais
from django.db import connection
from django.test import TestCase

from core.tenancy import filter_queryset_by_area
from eventos.models import TipoEvento
from planos_trabalho.models import (
    AtividadePlanoTrabalho,
    HorarioAtendimento,
    ProgramaSolicitante,
)
from usuarios.models import AreaTrabalho

CATALOGOS = (TipoEvento, AtividadePlanoTrabalho, ProgramaSolicitante, HorarioAtendimento)


class _EditorMinimo:
    """O que as funções de migração realmente usam do `schema_editor`.

    Um `connection.schema_editor()` de verdade não abre dentro da transação do
    teste no SQLite (`NotSupportedError: cannot be used while foreign key
    constraint checks are enabled`), e ele não é necessário aqui: as funções só
    consultam `connection.vendor` e executam `SET CONSTRAINTS ALL IMMEDIATE`.
    Este substituto executa de verdade — no PostgreSQL o comando roda.
    """

    def __init__(self):
        self.connection = connection

    def execute(self, sql, params=None):
        with connection.cursor() as cursor:
            cursor.execute(sql, params)


def _duplicar():
    """Roda as duas funções de ida das migrações contra o registro real.

    Os modelos históricos e os reais são compatíveis nos campos que as funções
    tocam, e rodar assim mantém o teste ligado ao código que vai para produção —
    em vez de reimplementar a lógica e provar a reimplementação.
    """
    editor = _EditorMinimo()
    import_module(
        "eventos.migrations.0016_db02_catalogos_por_area",
    ).duplicar_por_area(apps_reais, editor)
    import_module(
        "planos_trabalho.migrations.0024_db02_catalogos_por_area",
    ).duplicar_por_area(apps_reais, editor)


class CatalogoSemeadoTests(TestCase):
    """O estado de partida: o seed de migração, sem área."""

    def test_novo49_remove_o_seed_global_da_instalacao_nova(self):
        """O seed histórico é saneado antes de ``area`` virar obrigatório."""
        for modelo in CATALOGOS:
            with self.subTest(modelo=modelo._meta.label):
                total = modelo._base_manager.count()
                sem_area = modelo._base_manager.filter(area__isnull=True).count()

                self.assertEqual(total, 0)
                self.assertEqual(sem_area, 0)

    def test_o_catalogo_global_e_invisivel_para_quem_tem_area(self):
        """**O defeito, medido.**

        É o que responde a pergunta que o `NOVO-34` deixou aberta: o global não é
        um padrão compartilhado, é conteúdo que ninguém alcança.
        """
        area = AreaTrabalho.objects.create(nome="Alfa", sigla="ALFA")

        for modelo in CATALOGOS:
            with self.subTest(modelo=modelo._meta.label):
                visiveis = filter_queryset_by_area(
                    modelo._base_manager.all(), area,
                ).count()

                self.assertEqual(visiveis, 0)

    def test_so_quem_nao_tem_area_enxerga_o_global(self):
        """A outra metade: as linhas existem, e é o recorte que as esconde."""
        for modelo in CATALOGOS:
            with self.subTest(modelo=modelo._meta.label):
                self.assertEqual(
                    filter_queryset_by_area(modelo._base_manager.all(), None).count(),
                    modelo._base_manager.count(),
                )


class DuplicacaoPorAreaTests(TestCase):
    def test_sem_area_cadastrada_a_duplicacao_nao_faz_nada(self):
        """Instalação nova: os seeds acabaram de rodar e não existe área ainda.

        É o mesmo comportamento do `NOVO-09`, e é por isso que estes quatro modelos
        **não** podem virar `NOT NULL` nesta fatia — ver o `NOVO-49`.
        """
        antes = {m._meta.label: m._base_manager.count() for m in CATALOGOS}

        _duplicar()

        for modelo in CATALOGOS:
            with self.subTest(modelo=modelo._meta.label):
                self.assertEqual(modelo._base_manager.count(), antes[modelo._meta.label])
                self.assertEqual(
                    modelo._base_manager.filter(area__isnull=True).count(),
                    antes[modelo._meta.label],
                )

    def test_cada_area_passa_a_ter_o_catalogo_inteiro(self):
        """O efeito que o usuário vê: de 0 item visível para o catálogo completo."""
        alfa = AreaTrabalho.objects.create(nome="Alfa", sigla="ALFA")
        beta = AreaTrabalho.objects.create(nome="Beta", sigla="BETA")
        tamanho = {m._meta.label: m._base_manager.count() for m in CATALOGOS}

        _duplicar()

        for modelo in CATALOGOS:
            with self.subTest(modelo=modelo._meta.label):
                esperado = tamanho[modelo._meta.label]
                for area in (alfa, beta):
                    self.assertEqual(
                        filter_queryset_by_area(modelo._base_manager.all(), area).count(),
                        esperado,
                    )

    def test_nao_sobra_linha_sem_dono(self):
        """A original fica com a primeira área — o balde nulo esvazia."""
        AreaTrabalho.objects.create(nome="Alfa", sigla="ALFA")
        AreaTrabalho.objects.create(nome="Beta", sigla="BETA")

        _duplicar()

        for modelo in CATALOGOS:
            with self.subTest(modelo=modelo._meta.label):
                self.assertEqual(
                    modelo._base_manager.filter(area__isnull=True).count(), 0,
                )

    def test_o_total_e_o_catalogo_vezes_o_numero_de_areas(self):
        """Nem cópia a menos, nem cópia a mais."""
        tamanho = {m._meta.label: m._base_manager.count() for m in CATALOGOS}
        for i in range(3):
            AreaTrabalho.objects.create(nome=f"Área {i}", sigla=f"A{i}")

        _duplicar()

        for modelo in CATALOGOS:
            with self.subTest(modelo=modelo._meta.label):
                self.assertEqual(
                    modelo._base_manager.count(), tamanho[modelo._meta.label] * 3,
                )

    def test_rodar_duas_vezes_nao_multiplica(self):
        """A segunda passada não acha global nenhum e sai sem fazer nada."""
        AreaTrabalho.objects.create(nome="Alfa", sigla="ALFA")
        _duplicar()
        depois_de_uma = {m._meta.label: m._base_manager.count() for m in CATALOGOS}

        _duplicar()

        for modelo in CATALOGOS:
            with self.subTest(modelo=modelo._meta.label):
                self.assertEqual(
                    modelo._base_manager.count(), depois_de_uma[modelo._meta.label],
                )


class ContratoDaMigracaoTests(TestCase):
    """As duas armadilhas que a migração precisa respeitar, escritas como regra."""

    ARQUIVOS = (
        "eventos/migrations/0016_db02_catalogos_por_area.py",
        "planos_trabalho/migrations/0024_db02_catalogos_por_area.py",
    )

    def fonte(self, rel: str) -> str:
        from django.conf import settings
        from pathlib import Path

        return (Path(settings.BASE_DIR) / rel).read_text(encoding="utf-8")

    def test_a_migracao_usa_base_manager_e_nunca_objects(self):
        """Modelo histórico não recebe o manager customizado do `BE-09`.

        Com `default_manager_name` definido, `objects` **não existe** no modelo
        histórico. E o erro só aparece na **volta**, porque a ida sai cedo quando
        não há área — foi assim que ele apareceu aqui, drilando o rollback.
        """
        for rel in self.ARQUIVOS:
            with self.subTest(arquivo=rel):
                fonte = self.fonte(rel)

                self.assertIn("_base_manager", fonte)
                self.assertNotIn(".objects.", fonte)

    def test_a_migracao_libera_os_gatilhos_antes_do_alter_table(self):
        """Herdado do `NOVO-09`: sem isto a volta morre no PostgreSQL.

        `cannot ALTER TABLE ... because it has pending trigger events` — o
        PostgreSQL recusa `ALTER TABLE` numa tabela com gatilho de FK pendente na
        mesma transação, e migração roda tudo numa transação só.
        """
        for rel in self.ARQUIVOS:
            with self.subTest(arquivo=rel):
                fonte = self.fonte(rel)

                self.assertIn("SET CONSTRAINTS ALL IMMEDIATE", fonte)
                self.assertIn('vendor == "postgresql"', fonte)

    def test_a_migracao_e_reversivel(self):
        """`QA-03` proíbe migração irreversível; a volta tem de existir."""
        for rel in self.ARQUIVOS:
            with self.subTest(arquivo=rel):
                fonte = self.fonte(rel)

                self.assertIn("devolver_ao_global", fonte)
                self.assertIn(
                    "migrations.RunPython(duplicar_por_area, devolver_ao_global)", fonte,
                )
