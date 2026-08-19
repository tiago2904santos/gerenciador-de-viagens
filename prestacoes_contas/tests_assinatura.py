"""Testes do fluxo de assinatura eletrônica de RT e Diário de Bordo."""

import base64
from io import BytesIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import Servidor
from oficios.models import Oficio
from prestacoes_contas import assinatura_services as svc
from prestacoes_contas.models import AssinaturaDocumento
from prestacoes_contas.models import PrestacaoContas
from core.testing import area_de_teste
from core.testing import vincular_area


def _pdf_uma_pagina() -> bytes:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(72, 700, "Documento de teste")
    c.showPage()
    c.save()
    return buf.getvalue()


def _png_data_url() -> str:
    from PIL import Image

    img = Image.new("RGBA", (200, 60), (0, 0, 0, 0))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


class AssinaturaServiceTests(TestCase):
    def setUp(self):
        self.cargo = Cargo.objects.create(area=area_de_teste(), nome="Agente")
        self.servidor = Servidor.objects.create(area=area_de_teste(), nome="Servidor RT", cargo=self.cargo, cpf="11122233344")
        self.motorista = Servidor.objects.create(area=area_de_teste(), nome="Motorista DB", cargo=self.cargo, cpf="99988877766")
        self.oficio = Oficio.objects.create(area=area_de_teste(), numero=10, ano=2026, protocolo="123456789")
        self.oficio.servidores.add(self.servidor)
        self.oficio.motorista = self.motorista
        self.oficio.save(update_fields=["motorista", "updated_at"])
        self.prestacao = PrestacaoContas.objects.get(oficio=self.oficio)
        self.ps = self.prestacao.servidores_prestacao.get(servidor=self.servidor)

    def test_signer_resolution(self):
        self.assertEqual(svc.signer_rt(self.ps), self.servidor)
        self.assertEqual(svc.signer_db(self.prestacao), self.motorista)

    @mock.patch.object(svc, "_origem_rt_bytes", return_value=_pdf_uma_pagina())
    def test_emitir_link_rt(self, _m):
        token, docs = svc.emitir_link_rt(self.ps)
        self.assertTrue(token)
        self.assertEqual(len(docs), 1)
        doc = docs[0]
        self.assertEqual(doc.tipo, "rt")
        self.assertEqual(doc.signer, self.servidor)
        self.assertEqual(doc.status, AssinaturaDocumento.STATUS_PENDENTE)
        self.assertTrue(doc.arquivo_origem)
        self.assertTrue(doc.link_ativo)

    @mock.patch.object(svc, "_origem_rt_bytes", return_value=_pdf_uma_pagina())
    @mock.patch.object(svc, "_origem_db_bytes", return_value=_pdf_uma_pagina())
    def test_links_rt_e_db_sao_emitidos(self, _db, _rt):
        token_rt, docs_rt = svc.emitir_link_rt(self.ps)
        token_db, docs_db = svc.emitir_link_db(self.prestacao)
        self.assertTrue(token_rt)
        self.assertTrue(token_db)
        self.assertEqual(len(docs_rt), 1)
        self.assertEqual(len(docs_db), 1)

    def test_emitir_link_sem_motorista_falha(self):
        self.oficio.motorista = None
        self.oficio.save(update_fields=["motorista", "updated_at"])
        with self.assertRaises(svc.AssinaturaError):
            svc.emitir_link_db(self.prestacao)

    def test_emitir_link_sem_cpf_falha(self):
        self.servidor.cpf = ""
        self.servidor.save(update_fields=["cpf"])
        with self.assertRaises(svc.AssinaturaError):
            svc.emitir_link_rt(self.ps)

    @mock.patch.object(svc, "_origem_rt_bytes", return_value=_pdf_uma_pagina())
    def test_validar_identidade(self, _m):
        _token, docs = svc.emitir_link_rt(self.ps)
        doc = docs[0]
        self.assertFalse(svc.validar_identidade(doc, "00000000000"))
        self.assertFalse(svc.validar_identidade(doc, "11122"))  # prefixo incompleto não basta
        self.assertTrue(svc.validar_identidade(doc, "11122233344"))
        self.assertIsNotNone(doc.identidade_confirmada_em)

    @mock.patch.object(svc, "_origem_rt_bytes", return_value=_pdf_uma_pagina())
    def test_validar_identidade_aceita_cpf_formatado(self, _m):
        _token, docs = svc.emitir_link_rt(self.ps)
        doc = docs[0]
        self.assertTrue(svc.validar_identidade(doc, "111.222.333-44"))


class AssinaturaPublicFlowTests(TestCase):
    def setUp(self):
        self.cargo = Cargo.objects.create(area=area_de_teste(), nome="Agente")
        self.servidor = Servidor.objects.create(area=area_de_teste(), nome="Servidor Fulano", cargo=self.cargo, cpf="11122233344")
        self.oficio = Oficio.objects.create(area=area_de_teste(), numero=11, ano=2026, protocolo="123456789")
        self.oficio.servidores.add(self.servidor)
        self.prestacao = PrestacaoContas.objects.get(oficio=self.oficio)
        self.ps = self.prestacao.servidores_prestacao.get(servidor=self.servidor)

    @mock.patch.object(svc, "_origem_rt_bytes", return_value=_pdf_uma_pagina())
    def _emitir(self, _m):
        token, docs = svc.emitir_link_rt(self.ps)
        return token, docs[0]

    def test_fluxo_publico_completo(self):
        token, doc = self._emitir()

        # Landing lista os documentos do link com o botão para começar.
        r = self.client.get(reverse("prestacoes_contas:assinatura_landing", args=[token]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Relatório Técnico")

        # PDF de origem bloqueado sem confirmar identidade.
        r = self.client.get(reverse("prestacoes_contas:assinatura_pdf_origem", args=[token, "rt"]))
        self.assertEqual(r.status_code, 403)

        # Identidade com CPF errado não passa.
        ident_url = reverse("prestacoes_contas:assinatura_identidade", args=[token, "rt"])
        r = self.client.post(ident_url, {"cpf": "00000000000", "confirma_nome": "on"})
        self.assertEqual(r.status_code, 200)

        # Identidade correta redireciona para assinar.
        r = self.client.post(ident_url, {"cpf": "11122233344", "confirma_nome": "on"})
        self.assertRedirects(r, reverse("prestacoes_contas:assinatura_assinar", args=[token, "rt"]))

        # Agora o PDF de origem é servido.
        r = self.client.get(reverse("prestacoes_contas:assinatura_pdf_origem", args=[token, "rt"]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")

        # Envia a assinatura.
        r = self.client.post(
            reverse("prestacoes_contas:assinatura_assinar", args=[token, "rt"]),
            {
                "assinatura_png": _png_data_url(),
                "modo": "fonte",
                "fonte": "classica",
                "pagina": "0",
                "pos_x": "0.5",
                "pos_y": "0.7",
                "largura": "0.3",
                "altura": "0.1",
            },
        )
        self.assertRedirects(r, reverse("prestacoes_contas:assinatura_concluido", args=[token]))

        doc.refresh_from_db()
        self.assertEqual(doc.status, AssinaturaDocumento.STATUS_ASSINADA)
        self.assertTrue(doc.arquivo_assinado)
        self.assertTrue(doc.codigo_verificacao)
        self.assertEqual(len(doc.hash_documento), 64)  # SHA-256 hex

        # O sistema passa a usar o arquivo assinado.
        conteudo = svc.pdf_rt_assinado_ou_gerado(self.ps)
        self.assertTrue(conteudo.startswith(b"%PDF"))

    def test_rate_limit_identidade(self):
        token, _doc = self._emitir()
        ident_url = reverse("prestacoes_contas:assinatura_identidade", args=[token, "rt"])
        for _ in range(5):
            self.client.post(ident_url, {"cpf": "00000000000", "confirma_nome": "on"})
        # 6ª tentativa: bloqueado, mesmo com CPF correto.
        r = self.client.post(ident_url, {"cpf": "11122233344", "confirma_nome": "on"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Muitas tentativas")


class AssinaturaCardRenderTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester_asgn", password="123456")
        self.client.force_login(self.user)
        vincular_area(self.user)
        self.cargo = Cargo.objects.create(area=area_de_teste(), nome="Agente")
        self.servidor = Servidor.objects.create(area=area_de_teste(), nome="Servidor Card", cargo=self.cargo, cpf="11122233344")
        self.oficio = Oficio.objects.create(area=area_de_teste(), numero=12, ano=2026, protocolo="123456789")
        self.oficio.servidores.add(self.servidor)
        self.prestacao = PrestacaoContas.objects.get(oficio=self.oficio)
        self.ps = self.prestacao.servidores_prestacao.get(servidor=self.servidor)

    def test_rt_page_mostra_card(self):
        r = self.client.get(reverse("prestacoes_contas:rt_servidor", args=[self.ps.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Relatório Técnico")

    def test_gerar_link_via_form_admin(self):
        # POST do formulário do card não pode ser barrado por CSRF.
        url = reverse("prestacoes_contas:assinatura_rt_gerar", args=[self.ps.pk])
        with mock.patch.object(svc, "_origem_rt_bytes", return_value=b"%PDF-1.4\n%%EOF\n"):
            r = self.client.post(url, {"next": reverse("prestacoes_contas:rt_servidor", args=[self.ps.pk])})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(
            AssinaturaDocumento.objects.filter(prestacao=self.prestacao, tipo="rt").count(), 1
        )

    def test_diario_page_mostra_card_sem_motorista(self):
        r = self.client.get(reverse("prestacoes_contas:diario_servidor", args=[self.ps.pk]))
        self.assertEqual(r.status_code, 200)
        # O card está temporariamente oculto no template, mas o contexto continua
        # expondo corretamente o bloqueio por ausência de motorista.
        self.assertIn("assinatura", r.context)
        self.assertFalse(r.context["assinatura"]["pode_assinar"])
        self.assertIn("motorista do ofício", r.context["assinatura"]["motivo"])

    def test_consolidado_page_mostra_secao(self):
        r = self.client.get(reverse("prestacoes_contas:consolidado_servidor", args=[self.ps.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Resumo, conferência e pacote consolidado deste servidor")
        self.assertContains(r, 'class="fact-list"')
        self.assertContains(r, 'class="person-list"')
        self.assertNotContains(r, "oficio-documentos-admin-facts")
        self.assertNotContains(r, "oficio-documentos-facts")
        self.assertNotContains(r, "oficio-documentos-travellers-grid")
        self.assertNotContains(r, "oficio-documentos-traveller-tile")
        self.assertIn("servidores", r.context)
        self.assertIn("assinatura_rt", r.context["servidores"][0])
