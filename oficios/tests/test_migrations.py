import importlib

from django.apps import apps
from django.test import TestCase

from cadastros.models import Servidor
from oficios.models import Oficio
from core.testing import area_de_teste


class ServidoresTermoAutorizacaoMigrationTests(TestCase):
    def test_runpython_preserva_comportamento_antigo_preenchendo_servidores_de_termo(self):
        migration = importlib.import_module("oficios.migrations.0007_oficio_servidores_termo_autorizacao")
        servidor = Servidor.objects.create(area=area_de_teste(), nome="SERVIDOR MIGRACAO")
        oficio = Oficio.objects.create(area=area_de_teste(), numero=99, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        oficio.servidores.add(servidor)

        migration.copiar_servidores_para_termos(apps, None)

        self.assertEqual(list(oficio.servidores_termo_autorizacao.values_list("pk", flat=True)), [servidor.pk])


class QuantidadeServidoresDiariasMigrationTests(TestCase):
    def test_runpython_congela_efetivo_atual_com_piso_um(self):
        migration = importlib.import_module(
            "oficios.migrations.0020_oficio_diarias_quantidade_servidores",
        )
        com_equipe = Oficio.objects.create(
            area=area_de_teste(),
            numero=100,
            ano=2026,
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        sem_equipe = Oficio.objects.create(
            area=area_de_teste(),
            numero=101,
            ano=2026,
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        com_equipe.servidores.add(
            Servidor.objects.create(
                area=area_de_teste(),
                nome="SERVIDOR MIGRAÇÃO NOVO-39 A",
            ),
            Servidor.objects.create(
                area=area_de_teste(),
                nome="SERVIDOR MIGRAÇÃO NOVO-39 B",
            ),
        )

        migration.congelar_efetivo_atual(apps, None)
        com_equipe.refresh_from_db()
        sem_equipe.refresh_from_db()

        self.assertEqual(com_equipe.diarias_quantidade_servidores, 2)
        self.assertEqual(sem_equipe.diarias_quantidade_servidores, 1)
