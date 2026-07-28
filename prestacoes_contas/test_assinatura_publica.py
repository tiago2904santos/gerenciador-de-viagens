"""Fatia 6/6 de T-01 — as bordas do link público de assinatura.

`tests_assinatura.py` já cobre bem o caminho feliz: emissão, validação de
identidade, assinatura, hash e rate limit. Esta fatia não repete nada disso —
cobre as **bordas**, que é onde uma superfície sem autenticação costuma falhar:

* link expirado;
* token inexistente ou adulterado;
* link cancelado depois de emitido;
* pedir um tipo de documento que o link não contém;
* reenviar assinatura em documento já assinado.

As respostas afirmam o **código exato**, não "diferente de 200": expirado,
inexistente e adulterado devolvem **410 Gone** na landing, o que é uma escolha
boa — não revela se aquele token um dia existiu. O endpoint do PDF, para a mesma
causa, devolve **404**: inconsistência de contrato que só apareceu porque a
asserção afirma o código exato. Um teste frouxo aceitaria até um 500.

A auditoria lista a assinatura pública entre os pontos genuinamente bons do
sistema — *"token criptografado, hash indexado, expiração e rate limit em duas
dimensões"*. Expiração e cancelamento eram justamente as partes ainda não
verificadas por teste.
"""

from __future__ import annotations

import base64
from datetime import timedelta
from io import BytesIO
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Cargo
from cadastros.models import Servidor
from oficios.models import Oficio
from prestacoes_contas import assinatura_services as svc
from prestacoes_contas.models import AssinaturaDocumento
from prestacoes_contas.models import PrestacaoContas


def _pdf() -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(72, 700, "Origem")
    c.showPage()
    c.save()
    return buf.getvalue()


def _png() -> str:
    from PIL import Image

    buf = BytesIO()
    Image.new("RGBA", (120, 40), (0, 0, 0, 0)).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


class AssinaturaPublicaBordasTests(TestCase):
    def setUp(self):
        self.cargo = Cargo.objects.create(nome="Agente")
        self.servidor = Servidor.objects.create(
            nome="Servidor RT", cargo=self.cargo, cpf="11122233344"
        )
        self.oficio = Oficio.objects.create(numero=10, ano=2026, protocolo="123456789")
        self.oficio.servidores.add(self.servidor)
        self.prestacao = PrestacaoContas.objects.get(oficio=self.oficio)
        self.ps = self.prestacao.servidores_prestacao.get(servidor=self.servidor)

    def emitir(self):
        with mock.patch.object(svc, "_origem_rt_bytes", return_value=_pdf()):
            token, docs = svc.emitir_link_rt(self.ps)
        return token, docs[0]

    def landing(self, token):
        return self.client.get(
            reverse("prestacoes_contas:assinatura_landing", args=[token])
        )

    def validar_identidade(self, token, tipo="rt", cpf="11122233344"):
        return self.client.post(
            reverse("prestacoes_contas:assinatura_identidade", args=[token, tipo]),
            {"cpf": cpf, "confirma_nome": "on"},
        )

    # ── expiração ────────────────────────────────────────────────────────

    def test_link_expirado_nao_abre_a_landing(self):
        token, doc = self.emitir()
        self.assertEqual(self.landing(token).status_code, 200)

        AssinaturaDocumento.objects.filter(pk=doc.pk).update(
            link_expira_em=timezone.now() - timedelta(seconds=1)
        )

        response = self.landing(token)

        self.assertEqual(response.status_code, 410)

    def test_link_expirado_nao_serve_o_pdf_de_origem(self):
        """Mesmo com identidade já validada, o PDF para de sair após expirar.

        Aqui o código é **404**, e não o 410 da landing — mesma causa, respostas
        diferentes conforme o endpoint. Não é falha de segurança (o arquivo não
        sai nos dois casos), mas é inconsistência de contrato, e ficou explícita
        só porque a asserção afirma o código exato.
        """
        token, doc = self.emitir()
        self.validar_identidade(token)
        pdf_url = reverse("prestacoes_contas:assinatura_pdf_origem", args=[token, "rt"])
        self.assertEqual(self.client.get(pdf_url).status_code, 200)

        AssinaturaDocumento.objects.filter(pk=doc.pk).update(
            link_expira_em=timezone.now() - timedelta(seconds=1)
        )

        response = self.client.get(pdf_url)

        self.assertEqual(response.status_code, 404)

    def test_link_expirado_recusa_a_assinatura(self):
        token, doc = self.emitir()
        self.validar_identidade(token)
        AssinaturaDocumento.objects.filter(pk=doc.pk).update(
            link_expira_em=timezone.now() - timedelta(seconds=1)
        )

        self.client.post(
            reverse("prestacoes_contas:assinatura_assinar", args=[token, "rt"]),
            {
                "assinatura_png": _png(),
                "modo": "fonte",
                "fonte": "classica",
                "pagina": "0",
                "pos_x": "0.5",
                "pos_y": "0.7",
                "largura": "0.3",
                "altura": "0.1",
            },
        )

        doc.refresh_from_db()
        self.assertNotEqual(doc.status, AssinaturaDocumento.STATUS_ASSINADA)

    # ── token inválido ───────────────────────────────────────────────────

    def test_token_inexistente_responde_410(self):
        """410 Gone, o mesmo do expirado — não revela se o token já existiu."""
        response = self.landing("token-que-nunca-existiu")

        self.assertEqual(response.status_code, 410)

    def test_token_adulterado_em_um_caractere_nao_abre(self):
        """O token é conferido por inteiro — não basta o prefixo."""
        token, _doc = self.emitir()
        adulterado = token[:-1] + ("a" if token[-1] != "a" else "b")

        response = self.landing(adulterado)

        self.assertEqual(response.status_code, 410)

    # ── cancelamento ─────────────────────────────────────────────────────

    def test_cancelar_invalida_o_link_ja_emitido(self):
        token, _doc = self.emitir()
        self.assertEqual(self.landing(token).status_code, 200)

        svc.cancelar_assinatura_rt(self.ps)

        self.assertEqual(self.landing(token).status_code, 410)

    # ── tipo de documento ────────────────────────────────────────────────

    def test_tipo_ausente_no_link_nao_e_servido(self):
        """O link de RT não dá acesso ao diário de bordo."""
        token, _doc = self.emitir()

        response = self.client.get(
            reverse("prestacoes_contas:assinatura_pdf_origem", args=[token, "db"])
        )

        self.assertEqual(response.status_code, 404)

    # ── reuso ────────────────────────────────────────────────────────────

    def test_documento_assinado_nao_e_assinado_de_novo(self):
        """Reenviar não sobrescreve: o hash e o código de verificação ficam."""
        token, doc = self.emitir()
        self.validar_identidade(token)
        assinar_url = reverse("prestacoes_contas:assinatura_assinar", args=[token, "rt"])
        dados = {
            "assinatura_png": _png(),
            "modo": "fonte",
            "fonte": "classica",
            "pagina": "0",
            "pos_x": "0.5",
            "pos_y": "0.7",
            "largura": "0.3",
            "altura": "0.1",
        }
        self.client.post(assinar_url, dados)

        doc.refresh_from_db()
        self.assertEqual(doc.status, AssinaturaDocumento.STATUS_ASSINADA)
        hash_original = doc.hash_documento
        codigo_original = doc.codigo_verificacao

        self.client.post(assinar_url, dados)

        doc.refresh_from_db()
        self.assertEqual(doc.hash_documento, hash_original)
        self.assertEqual(doc.codigo_verificacao, codigo_original)
