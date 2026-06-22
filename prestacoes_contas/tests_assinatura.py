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
        self.cargo = Cargo.objects.create(nome="Agente")
        self.servidor = Servidor.objects.create(nome="Servidor RT", cargo=self.cargo, cpf="11122233344")
        self.motorista = Servidor.objects.create(nome="Motorista DB", cargo=self.cargo, cpf="99988877766")
        self.oficio = Oficio.objects.create(numero=10, ano=2026, protocolo="123456789")
        self.oficio.servidores.add(self.servidor)
        self.oficio.motorista = self.motorista
        self.oficio.save(update_fields=["motorista", "updated_at"])
        self.prestacao = PrestacaoContas.objects.get(oficio=self.oficio, servidor=self.servidor)

    def test_signer_resolution(self):
        self.assertEqual(svc.signer_do_documento(self.prestacao, "rt"), self.servidor)
        self.assertEqual(svc.signer_do_documento(self.prestacao, "db"), self.motorista)

    @mock.patch.object(svc, "_gerar_origem_bytes", return_value=_pdf_uma_pagina())
    def test_emitir_link_rt(self, _m):
        token, docs = svc.emitir_link(self.prestacao, ["rt"])
        self.assertTrue(token)
        self.assertEqual(len(docs), 1)
        doc = docs[0]
        self.assertEqual(doc.tipo, "rt")
        self.assertEqual(doc.signer, self.servidor)
        self.assertEqual(doc.status, AssinaturaDocumento.STATUS_PENDENTE)
        self.assertTrue(doc.arquivo_origem)
        self.assertTrue(doc.link_ativo)

    @mock.patch.object(svc, "_gerar_origem_bytes", return_value=_pdf_uma_pagina())
    def test_emitir_link_unico_compartilha_token(self, _m):
        token, docs = svc.emitir_link(self.prestacao, ["rt", "db"])
        self.assertEqual(len(docs), 2)
        self.assertEqual({d.link_token for d in docs}, {token})

    def test_emitir_link_sem_motorista_falha(self):
        self.oficio.motorista = None
        self.oficio.save(update_fields=["motorista", "updated_at"])
        with self.assertRaises(svc.AssinaturaError):
            svc.emitir_link(self.prestacao, ["db"])

    def test_emitir_link_sem_cpf_falha(self):
        self.servidor.cpf = ""
        self.servidor.save(update_fields=["cpf"])
        with self.assertRaises(svc.AssinaturaError):
            svc.emitir_link(self.prestacao, ["rt"])

    @mock.patch.object(svc, "_gerar_origem_bytes", return_value=_pdf_uma_pagina())
    def test_validar_identidade(self, _m):
        _token, docs = svc.emitir_link(self.prestacao, ["rt"])
        doc = docs[0]
        self.assertFalse(svc.validar_identidade(doc, "00000"))
        self.assertTrue(svc.validar_identidade(doc, "11122"))
        self.assertIsNotNone(doc.identidade_confirmada_em)


class AssinaturaPublicFlowTests(TestCase):
    def setUp(self):
        self.cargo = Cargo.objects.create(nome="Agente")
        self.servidor = Servidor.objects.create(nome="Servidor Fulano", cargo=self.cargo, cpf="11122233344")
        self.oficio = Oficio.objects.create(numero=11, ano=2026, protocolo="123456789")
        self.oficio.servidores.add(self.servidor)
        self.prestacao = PrestacaoContas.objects.get(oficio=self.oficio, servidor=self.servidor)

    @mock.patch.object(svc, "_gerar_origem_bytes", return_value=_pdf_uma_pagina())
    def _emitir(self, _m):
        token, docs = svc.emitir_link(self.prestacao, ["rt"])
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
        r = self.client.post(ident_url, {"cpf5": "00000", "confirma_nome": "on"})
        self.assertEqual(r.status_code, 200)

        # Identidade correta redireciona para assinar.
        r = self.client.post(ident_url, {"cpf5": "11122", "confirma_nome": "on"})
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
                "fonte": "dancing",
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

        # O sistema passa a usar o arquivo assinado.
        conteudo = svc.pdf_rt_assinado_ou_gerado(self.prestacao)
        self.assertTrue(conteudo.startswith(b"%PDF"))

    def test_rate_limit_identidade(self):
        token, _doc = self._emitir()
        ident_url = reverse("prestacoes_contas:assinatura_identidade", args=[token, "rt"])
        for _ in range(5):
            self.client.post(ident_url, {"cpf5": "00000", "confirma_nome": "on"})
        # 6ª tentativa: bloqueado, mesmo com CPF correto.
        r = self.client.post(ident_url, {"cpf5": "11122", "confirma_nome": "on"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Muitas tentativas")


class AssinaturaCardRenderTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester_asgn", password="123456")
        self.client.force_login(self.user)
        self.cargo = Cargo.objects.create(nome="Agente")
        self.servidor = Servidor.objects.create(nome="Servidor Card", cargo=self.cargo, cpf="11122233344")
        self.oficio = Oficio.objects.create(numero=12, ano=2026, protocolo="123456789")
        self.oficio.servidores.add(self.servidor)
        self.prestacao = PrestacaoContas.objects.get(oficio=self.oficio, servidor=self.servidor)

    def test_rt_page_mostra_card(self):
        r = self.client.get(reverse("prestacoes_contas:rt_criar", args=[self.prestacao.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Assinatura eletrônica")
        self.assertContains(r, "Gerar link de assinatura")
        # Regressão: o card é incluído com `only`, então `csrf_token` precisa ser
        # repassado explicitamente — sem isso o form POST falha com "CSRF token missing".
        self.assertContains(r, "csrfmiddlewaretoken")

    def test_gerar_link_via_form_admin(self):
        # POST do formulário do card não pode ser barrado por CSRF.
        url = reverse("prestacoes_contas:assinatura_gerar", args=[self.prestacao.pk])
        with mock.patch.object(svc, "_gerar_origem_bytes", return_value=b"%PDF-1.4\n%%EOF\n"):
            r = self.client.post(url, {"tipo": "rt", "next": reverse("prestacoes_contas:rt_criar", args=[self.prestacao.pk])})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(
            AssinaturaDocumento.objects.filter(prestacao=self.prestacao, tipo="rt").count(), 1
        )

    def test_diario_page_mostra_card_sem_motorista(self):
        r = self.client.get(reverse("prestacoes_contas:diario_criar", args=[self.prestacao.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Assinatura eletrônica")
        # Sem motorista cadastrado, exibe o motivo do bloqueio.
        self.assertContains(r, "motorista do ofício")

    def test_consolidado_page_mostra_secao(self):
        r = self.client.get(reverse("prestacoes_contas:consolidado", args=[self.prestacao.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Assinaturas")
