from django.test import TestCase

from oficios.models import ModeloMotivoOficio
from oficios.models import Oficio
from core.testing import area_de_teste


class OficioModelTests(TestCase):
    def test_cria_oficio_minimo(self):
        oficio = Oficio.objects.create(area=area_de_teste())
        self.assertIsNotNone(oficio.pk)

    def test_numero_formatado_funciona(self):
        oficio = Oficio.objects.create(area=area_de_teste(), numero=1, ano=2026)
        self.assertEqual(oficio.numero_formatado, "01/2026")

    def test_str_funciona(self):
        oficio = Oficio.objects.create(area=area_de_teste(), numero=12, ano=2026)
        self.assertEqual(str(oficio), "Ofício 12/2026")

    def test_status_default_rascunho(self):
        oficio = Oficio.objects.create(area=area_de_teste())
        self.assertEqual(oficio.status, Oficio.STATUS_RASCUNHO)

    def test_modelo_motivo_normaliza_nome(self):
        modelo = ModeloMotivoOficio.objects.create(area=area_de_teste(), nome="   padrão equipe  ", texto=" Texto base ")
        self.assertEqual(modelo.nome, "PADRÃO EQUIPE")
