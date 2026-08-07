from django.test import TestCase

from cadastros.models import ConfiguracaoSistema
from oficios.docxtpl_context import build_oficio_docxtpl_context
from oficios.models import Oficio
from core.testing import area_de_teste
from core.testing import com_request


class RodapeOficioDocxtplTests(TestCase):
    def setUp(self):
        # DB-02: selectors/forms/services recortam pela area do request;
        # chamada direta reproduz o contexto que a view teria.
        self.enterContext(com_request(area_de_teste()))
        self.cfg = ConfiguracaoSistema.get_singleton()

    def test_email_minusculo(self):
        self.cfg.email = "Contato@EXEMPLO.GOV.BR"
        self.cfg.save(update_fields=["email"])
        oficio = Oficio.objects.create(area=area_de_teste())
        ctx = build_oficio_docxtpl_context(oficio)
        self.assertEqual(ctx["email"], "contato@exemplo.gov.br")

    def test_endereco_separador_traco_e_cidade_uf(self):
        self.cfg.logradouro = "RUA DAS FLORES"
        self.cfg.numero = "100"
        self.cfg.bairro = "CENTRO"
        self.cfg.cidade_endereco = "LONDRINA"
        self.cfg.uf = "pr"
        self.cfg.cep = "80010000"
        self.cfg.save(
            update_fields=[
                "logradouro",
                "numero",
                "bairro",
                "cidade_endereco",
                "uf",
                "cep",
            ],
        )
        oficio = Oficio.objects.create(area=area_de_teste())
        ctx = build_oficio_docxtpl_context(oficio)
        self.assertIn(" - ", ctx["endereco"])
        self.assertIn("Londrina/PR", ctx["endereco"])
