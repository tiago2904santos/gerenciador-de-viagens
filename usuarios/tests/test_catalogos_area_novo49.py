"""NOVO-49 — toda área nasce com os quatro catálogos canônicos."""

from unittest.mock import patch

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase
from django.test import TransactionTestCase

from eventos.models import TipoEvento
from planos_trabalho.models import (
    AtividadePlanoTrabalho,
    HorarioAtendimento,
    ProgramaSolicitante,
)
from usuarios.forms import AreaTrabalhoForm
from usuarios.models import AreaTrabalho
from usuarios.services import criar_area


CATALOGOS = (
    TipoEvento,
    AtividadePlanoTrabalho,
    ProgramaSolicitante,
    HorarioAtendimento,
)


class CatalogosDaAreaNovaTests(TestCase):
    def criar_area(self, *, nome="Área NOVO-49", sigla="N49"):
        form = AreaTrabalhoForm({"nome": nome, "sigla": sigla})
        self.assertTrue(form.is_valid(), form.errors)
        return criar_area(form)

    def test_area_nova_recebe_todos_os_catalogos(self):
        area = self.criar_area()

        for modelo in CATALOGOS:
            with self.subTest(modelo=modelo._meta.label):
                self.assertGreater(
                    modelo._base_manager.filter(area=area).count(),
                    0,
                    "a área foi criada com o catálogo vazio",
                )

    def test_duas_areas_recebem_copias_independentes(self):
        primeira = self.criar_area(nome="Primeira", sigla="P49")
        segunda = self.criar_area(nome="Segunda", sigla="S49")

        for modelo in CATALOGOS:
            with self.subTest(modelo=modelo._meta.label):
                primeira_ids = set(
                    modelo._base_manager.filter(area=primeira).values_list("pk", flat=True)
                )
                segunda_ids = set(
                    modelo._base_manager.filter(area=segunda).values_list("pk", flat=True)
                )
                self.assertTrue(primeira_ids)
                self.assertTrue(segunda_ids)
                self.assertTrue(primeira_ids.isdisjoint(segunda_ids))

    def test_falha_ao_semear_desfaz_a_criacao_da_area(self):
        form = AreaTrabalhoForm({"nome": "Falha", "sigla": "F49"})
        self.assertTrue(form.is_valid(), form.errors)

        with (
            patch(
                "usuarios.services.semear_catalogos_da_area",
                side_effect=RuntimeError("falha controlada"),
            ),
            self.assertRaisesMessage(RuntimeError, "falha controlada"),
        ):
            criar_area(form)

        self.assertFalse(AreaTrabalho.objects.filter(sigla="F49").exists())


class CatalogosSemBaldeGlobalTests(TestCase):
    def test_area_e_obrigatoria_nos_quatro_modelos(self):
        for modelo in CATALOGOS:
            with self.subTest(modelo=modelo._meta.label):
                self.assertFalse(modelo._meta.get_field("area").null)

    def test_migracoes_nao_deixam_catalogo_sem_dono(self):
        for modelo in CATALOGOS:
            with self.subTest(modelo=modelo._meta.label):
                self.assertFalse(
                    modelo._base_manager.filter(area__isnull=True).exists(),
                )


class MigracaoCatalogosNovo49Tests(TransactionTestCase):
    """Prova o upgrade real partindo do estado deixado pelo DB-02."""

    reset_sequences = True
    migrate_from = [
        ("usuarios", "0001_initial"),
        ("eventos", "0016_db02_catalogos_por_area"),
        ("planos_trabalho", "0024_db02_catalogos_por_area"),
    ]
    migrate_to = [
        ("eventos", "0017_remove_tipoevento_eventos_tipo_nome_global_unique_and_more"),
        (
            "planos_trabalho",
            "0025_remove_atividadeplanotrabalho_planos_atividade_codigo_global_unique_and_more",
        ),
    ]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        apps = executor.loader.project_state(self.migrate_from).apps
        Area = apps.get_model("usuarios", "AreaTrabalho")
        self.area_pk = Area._base_manager.create(nome="Área migrada", sigla="M49").pk

    def tearDown(self):
        MigrationExecutor(connection).migrate(self.migrate_to)
        super().tearDown()

    def test_upgrade_copia_o_catalogo_e_elimina_nulos(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to).apps

        esperados = {
            ("eventos", "TipoEvento"): 5,
            ("planos_trabalho", "AtividadePlanoTrabalho"): 11,
            ("planos_trabalho", "ProgramaSolicitante"): 3,
            ("planos_trabalho", "HorarioAtendimento"): 3,
        }
        for (app_label, model_name), total in esperados.items():
            modelo = apps.get_model(app_label, model_name)
            with self.subTest(modelo=modelo._meta.label):
                self.assertEqual(
                    modelo._base_manager.filter(area_id=self.area_pk).count(),
                    total,
                )
                self.assertFalse(
                    modelo._base_manager.filter(area__isnull=True).exists(),
                )
