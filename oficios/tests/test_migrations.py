import importlib

from django.apps import apps
from django.test import TestCase

from cadastros.models import Servidor
from oficios.models import Oficio


class ServidoresTermoAutorizacaoMigrationTests(TestCase):
    def test_runpython_preserva_comportamento_antigo_preenchendo_servidores_de_termo(self):
        migration = importlib.import_module("oficios.migrations.0007_oficio_servidores_termo_autorizacao")
        servidor = Servidor.objects.create(nome="SERVIDOR MIGRACAO")
        oficio = Oficio.objects.create(numero=99, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        oficio.servidores.add(servidor)

        migration.copiar_servidores_para_termos(apps, None)

        self.assertEqual(list(oficio.servidores_termo_autorizacao.values_list("pk", flat=True)), [servidor.pk])
