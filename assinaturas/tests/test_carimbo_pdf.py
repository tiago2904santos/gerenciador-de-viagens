from __future__ import annotations

import io
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from assinaturas.services.carimbo_pdf import DadosCarimbo
from assinaturas.services.carimbo_pdf import SIGNATURE_LABEL_HEIGHT_PT
from assinaturas.services.carimbo_pdf import SIGNATURE_LABEL_QR_PT
from assinaturas.services.carimbo_pdf import SIGNATURE_LABEL_WIDTH_PT
from assinaturas.services.carimbo_pdf import aplicar_carimbo_pdf
from assinaturas.services.carimbo_pdf import renderizar_aparencia_assinatura


def _minimal_valid_pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R/Resources<<>>>>endobj\n"
        b"4 0 obj<</Length 21>>stream\nBT /F1 12 Tf ET\nendstream\nendobj\n"
        b"xref\n0 5\n0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000214 00000 n \n"
        b"trailer<</Size 5/Root 1 0 R>>\n"
        b"startxref\n310\n"
        b"%%EOF\n"
    )


def _dados() -> DadosCarimbo:
    return DadosCarimbo(
        nome_assinante="Maria Silva",
        cpf_mascarado="***.000.000-**",
        data_hora_assinatura=timezone.now(),
        codigo_verificacao="CV-2026-A1B2C3-D4E5",
        url_validacao="https://testserver/assinaturas/verificar/CV-2026-A1B2C3-D4E5/",
    )


def _dados_com_cargo_e_hash() -> DadosCarimbo:
    d = _dados()
    return DadosCarimbo(
        nome_assinante=d.nome_assinante,
        cpf_mascarado=d.cpf_mascarado,
        data_hora_assinatura=d.data_hora_assinatura,
        codigo_verificacao=d.codigo_verificacao,
        url_validacao=d.url_validacao,
        cargo_assinante="Delegado",
        hash_curto="abcdef123456",
    )


class CarimboPdfTests(TestCase):
    def test_renderizar_aparencia_retorna_pdf_bytes(self):
        raw = renderizar_aparencia_assinatura(_dados(), 155, 54)
        reader = PdfReader(io.BytesIO(raw))
        self.assertEqual(len(reader.pages), 1)

    def test_aplicar_carimbo_pdf_produz_pdf_valido(self):
        pdf_in = _minimal_valid_pdf_bytes()
        out, meta = aplicar_carimbo_pdf(pdf_in, _dados(), None)
        reader = PdfReader(io.BytesIO(out))
        self.assertGreaterEqual(len(reader.pages), 1)
        self.assertEqual(meta.get("label_width_pt"), SIGNATURE_LABEL_WIDTH_PT)
        self.assertEqual(meta.get("label_height_pt"), SIGNATURE_LABEL_HEIGHT_PT)
        self.assertEqual(meta.get("qr_size_pt"), SIGNATURE_LABEL_QR_PT)
        self.assertIn("page_number", meta)

    def test_position_meta_dimensoes_obrigatorias(self):
        pdf_in = _minimal_valid_pdf_bytes()
        _out, meta = aplicar_carimbo_pdf(pdf_in, _dados(), None)
        self.assertEqual(meta.get("label_width_pt"), 155)
        self.assertEqual(meta.get("label_height_pt"), 54)
        self.assertEqual(meta.get("qr_size_pt"), 42)

    def test_metadados_assinatura_no_pdf_final(self):
        pdf_in = _minimal_valid_pdf_bytes()
        out, _meta = aplicar_carimbo_pdf(pdf_in, _dados(), None)
        reader = PdfReader(io.BytesIO(out))
        md = reader.metadata
        self.assertIsNotNone(md)
        decoded = {k: (str(v) if v is not None else "") for k, v in (md or {}).items()}
        keys = "".join(decoded.keys()).lower()
        self.assertIn("assinatura_codigo", keys)
        self.assertIn("assinatura_sistema", keys)

    def test_pdf_sem_paginas_erro_claro(self):
        with mock.patch("assinaturas.services.carimbo_pdf.PdfReader") as m_reader:
            inst = mock.Mock()
            inst.pages = []
            m_reader.return_value = inst
            with self.assertRaises(ValueError) as ctx:
                aplicar_carimbo_pdf(b"%PDF-1.4", _dados(), None)
            self.assertIn("página", str(ctx.exception).lower())

    def test_etiqueta_nao_exibe_cargo_nem_hash_mesmo_quando_preenchidos(self):
        pdf_in = _minimal_valid_pdf_bytes()
        out, _meta = aplicar_carimbo_pdf(pdf_in, _dados_com_cargo_e_hash(), None)
        text = "".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(out)).pages)
        self.assertNotIn("Cargo:", text)
        self.assertNotIn("Hash:", text)
        self.assertIn("verifique em", text.lower())
        self.assertIn("CV-2026-A1B2C3-D4E5", text)

    def test_reportlab_pdf_simples_em_memoria(self):
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(200, 200))
        c.drawString(20, 100, "x")
        c.save()
        out, meta = aplicar_carimbo_pdf(buf.getvalue(), _dados(), None)
        self.assertIsInstance(out, bytes)
        self.assertGreater(len(out), 50)
        self.assertEqual(meta.get("page_number"), 1)
