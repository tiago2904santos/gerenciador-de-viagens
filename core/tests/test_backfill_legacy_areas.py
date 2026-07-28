from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from cadastros.models import Servidor
from cadastros.models import Unidade
from cadastros.models import ConfiguracaoSistema
from oficios.models import Oficio
from usuarios.models import AreaTrabalho


class BackfillLegacyAreasConflictTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(
            nome="Área de destino",
            sigla="DST",
        )
        self.target_unit = Unidade.objects.create(
            area=self.area,
            nome="Unidade duplicada",
        )
        self.legacy_unit = Unidade.objects.create(nome="Unidade duplicada")
        self.target_config = ConfiguracaoSistema.objects.create(area=self.area)
        self.legacy_config = ConfiguracaoSistema.objects.create(
            area=None,
            unidade=self.legacy_unit,
            cidade_endereco="SEDE LEGADA",
        )
        self.target_server = Servidor.objects.create(
            area=self.area,
            nome="Nome oficial",
            cpf="12345678901",
            telefone="41999990000",
        )
        self.legacy_server = Servidor.objects.create(
            area=None,
            unidade=self.legacy_unit,
            nome="Nome legado",
            cpf="12345678901",
            telefone="41999990000",
        )
        self.existing_oficio = Oficio.objects.create(
            area=self.area,
            ano=2026,
            numero=10,
        )
        self.legacy_oficio = Oficio.objects.create(
            area=None,
            ano=2026,
            numero=10,
        )
        self.legacy_oficio.servidores.add(self.legacy_server)

    def test_dry_run_nao_altera_dados(self):
        output = StringIO()

        call_command(
            "backfill_legacy_areas",
            area=self.area.sigla,
            resolve_conflicts=True,
            stdout=output,
        )

        self.assertTrue(Unidade.objects.filter(pk=self.legacy_unit.pk).exists())
        self.legacy_oficio.refresh_from_db()
        self.assertIsNone(self.legacy_oficio.area_id)
        self.assertEqual(self.legacy_oficio.numero, 10)
        self.assertIn("RENUMERAR", output.getvalue())

    def test_commit_consolida_identidade_e_renumera_sem_perder_relacoes(self):
        call_command(
            "backfill_legacy_areas",
            area=self.area.sigla,
            resolve_conflicts=True,
            commit=True,
            stdout=StringIO(),
        )

        self.assertFalse(Unidade.objects.filter(pk=self.legacy_unit.pk).exists())
        self.assertFalse(Servidor.objects.filter(pk=self.legacy_server.pk).exists())
        self.assertFalse(
            ConfiguracaoSistema.objects.filter(pk=self.legacy_config.pk).exists(),
        )
        self.target_config.refresh_from_db()
        self.assertEqual(self.target_config.unidade, self.target_unit)
        self.assertEqual(self.target_config.cidade_endereco, "SEDE LEGADA")
        self.legacy_oficio.refresh_from_db()
        self.assertEqual(self.legacy_oficio.area, self.area)
        self.assertGreater(self.legacy_oficio.numero, self.existing_oficio.numero)
        self.assertTrue(
            self.legacy_oficio.servidores.filter(pk=self.target_server.pk).exists(),
        )
