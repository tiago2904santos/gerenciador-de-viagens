from django.test import TestCase

from cadastros.models import Cargo
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Servidor
from cadastros.models import Unidade
from oficios.docxtpl_context import build_oficio_docxtpl_context
from oficios.models import Oficio
from core.testing import area_de_teste
from core.testing import com_request


class DestinatarioOficioDocxtplTests(TestCase):
    def setUp(self):
        # DB-02: selectors/forms/services recortam pela area do request;
        # chamada direta reproduz o contexto que a view teria.
        self.enterContext(com_request(area_de_teste()))
        self.cfg = ConfiguracaoSistema.get_singleton()
        self.cargo = Cargo.objects.create(area=area_de_teste(), nome="Delegado-Geral Adjunto Operacional")
        self.unidade = Unidade.objects.create(area=area_de_teste(), nome="Gabinete do Delegado Geral Adjunto")

    def test_sem_destinatario_configurado_usa_padrao(self):
        oficio = Oficio.objects.create(area=area_de_teste())
        ctx = build_oficio_docxtpl_context(oficio)
        self.assertEqual(ctx["orgao_destino"], "Gabinete do Delegado Geral Adjunto")
        self.assertEqual(ctx["nome_destinatario"], "")
        self.assertEqual(ctx["cargo_destinatario"], "")

    def test_destinatario_configurado_alimenta_destino_e_nome_cargo(self):
        destinatario = Servidor.objects.create(area=area_de_teste(), 
            nome="Riad Braga Farhat",
            cargo=self.cargo,
            unidade=self.unidade,
        )
        self.cfg.destinatario_oficio = destinatario
        self.cfg.save()

        oficio = Oficio.objects.create(area=area_de_teste())
        ctx = build_oficio_docxtpl_context(oficio)
        self.assertEqual(ctx["orgao_destino"], "Gabinete do Delegado Geral Adjunto")
        self.assertEqual(ctx["nome_destinatario"], "Riad Braga Farhat")
        self.assertEqual(ctx["cargo_destinatario"], "Delegado-Geral Adjunto Operacional")

    def test_destinatario_manual_sem_servidor_cadastrado(self):
        self.cfg.destinatario_oficio_nome = "Maria Souza"
        self.cfg.destinatario_oficio_cargo = "Diretora"
        self.cfg.destinatario_oficio_unidade = "Secretaria Executiva"
        self.cfg.save()

        oficio = Oficio.objects.create(area=area_de_teste())
        ctx = build_oficio_docxtpl_context(oficio)
        self.assertEqual(ctx["orgao_destino"], "Secretaria Executiva")
        self.assertEqual(ctx["nome_destinatario"], "Maria Souza")
        self.assertEqual(ctx["cargo_destinatario"], "Diretora")
