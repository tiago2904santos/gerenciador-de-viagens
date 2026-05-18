from decimal import Decimal

from django.test import TestCase

from cadastros.models import ConfiguracaoSistema
from oficios.docxtpl_context import build_oficio_docxtpl_context
from oficios.models import Oficio
from roteiros.models import Roteiro


class DiariasDocxtplTests(TestCase):
    def setUp(self):
        ConfiguracaoSistema.get_singleton()

    def test_valor_com_milhar_e_centavos(self):
        roteiro = Roteiro.objects.create(tipo=Roteiro.TIPO_AVULSO, status=Roteiro.STATUS_RASCUNHO)
        roteiro.quantidade_diarias = "10"
        roteiro.valor_diarias = Decimal("1500.5")
        roteiro.save(update_fields=["quantidade_diarias", "valor_diarias"])
        oficio = Oficio.objects.create(roteiro=roteiro)
        ctx = build_oficio_docxtpl_context(oficio)
        self.assertTrue(ctx["diaria"].startswith("R$1.500,50"))
        self.assertEqual(ctx["valor_total_oficio"], ctx["diaria"])

    def test_valor_com_extenso(self):
        roteiro = Roteiro.objects.create(tipo=Roteiro.TIPO_AVULSO, status=Roteiro.STATUS_RASCUNHO)
        roteiro.quantidade_diarias = "1"
        roteiro.valor_diarias = Decimal("100")
        roteiro.valor_diarias_extenso = "CEM REAIS"
        roteiro.save(update_fields=["quantidade_diarias", "valor_diarias", "valor_diarias_extenso"])
        oficio = Oficio.objects.create(roteiro=roteiro)
        ctx = build_oficio_docxtpl_context(oficio)
        self.assertIn("R$100,00", ctx["diaria"])
        self.assertIn("(Cem reais)", ctx["diaria"])
