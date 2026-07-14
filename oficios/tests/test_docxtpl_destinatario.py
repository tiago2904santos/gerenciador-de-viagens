from django.test import TestCase

from cadastros.models import AssinaturaConfiguracao
from cadastros.models import Cargo
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Servidor
from oficios.docxtpl_context import build_oficio_docxtpl_context
from oficios.models import Oficio


class DestinatarioOficioDocxtplTests(TestCase):
    def setUp(self):
        self.cfg = ConfiguracaoSistema.get_singleton()
        self.cargo_adjunto = Cargo.objects.create(nome="Delegado-Geral Adjunto Operacional")
        self.cargo_geral = Cargo.objects.create(nome="Delegado-Geral")
        # Chefias: apenas nome completo, cargo e unidade — sem RG/CPF cadastrados.
        self.destinatario_adjunto = Servidor.objects.create(
            nome="Riad Braga Farhat",
            cargo=self.cargo_adjunto,
        )
        self.destinatario_geral = Servidor.objects.create(
            nome="Silvio Jacob Rockembach",
            cargo=self.cargo_geral,
        )
        AssinaturaConfiguracao.objects.create(
            configuracao=self.cfg,
            tipo=AssinaturaConfiguracao.DESTINATARIO_OFICIO_ADJUNTO,
            servidor=self.destinatario_adjunto,
            ordem=1,
        )
        AssinaturaConfiguracao.objects.create(
            configuracao=self.cfg,
            tipo=AssinaturaConfiguracao.DESTINATARIO_OFICIO_GERAL,
            servidor=self.destinatario_geral,
            ordem=1,
        )

    def test_destino_adjunto_usa_destinatario_adjunto(self):
        oficio = Oficio.objects.create(destino_gabinete=Oficio.DESTINO_GABINETE_ADJUNTO)
        ctx = build_oficio_docxtpl_context(oficio)
        self.assertEqual(ctx["orgao_destino"], "Gabinete do Delegado Geral Adjunto")
        self.assertEqual(ctx["nome_destinatario"], "Riad Braga Farhat")
        self.assertEqual(ctx["cargo_destinatario"], "Delegado-Geral Adjunto Operacional")

    def test_destino_geral_usa_destinatario_geral(self):
        oficio = Oficio.objects.create(destino_gabinete=Oficio.DESTINO_GABINETE_GERAL)
        ctx = build_oficio_docxtpl_context(oficio)
        self.assertEqual(ctx["orgao_destino"], "Gabinete do Delegado Geral")
        self.assertEqual(ctx["nome_destinatario"], "Silvio Jacob Rockembach")
        self.assertEqual(ctx["cargo_destinatario"], "Delegado-Geral")

    def test_sem_destinatario_cadastrado_retorna_vazio(self):
        AssinaturaConfiguracao.objects.filter(
            configuracao=self.cfg,
            tipo=AssinaturaConfiguracao.DESTINATARIO_OFICIO_GERAL,
        ).delete()
        oficio = Oficio.objects.create(destino_gabinete=Oficio.DESTINO_GABINETE_GERAL)
        ctx = build_oficio_docxtpl_context(oficio)
        self.assertEqual(ctx["nome_destinatario"], "")
        self.assertEqual(ctx["cargo_destinatario"], "")
