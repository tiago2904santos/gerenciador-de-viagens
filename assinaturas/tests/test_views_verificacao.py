from __future__ import annotations

import hashlib

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import Client
from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from assinaturas.services.assinatura_artefato import assinar_artefato_com_etiqueta
from documentos.models import DocumentoArtefato


def _pdf():
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


@override_settings(DOCUMENTOS_PERSIST_ARTEFATOS=True)
class VerificacaoPublicaViewsTests(TestCase):
    def setUp(self):
        raw = _pdf()
        digest = hashlib.sha256(raw).hexdigest()
        self.art = DocumentoArtefato.objects.create(
            tipo="t",
            formato="pdf",
            hash_sha256=digest,
            arquivo=ContentFile(raw, name="v.pdf"),
        )
        self.user = get_user_model().objects.create_user(username="v_u", password="p" * 12)
        rf = RequestFactory()
        req = rf.get("/")
        req.META["HTTP_HOST"] = "testserver"
        self.ass = assinar_artefato_com_etiqueta(self.art, nome_assinante="Nome", request=req)

    def test_codigo_valido_200(self):
        c = Client()
        url = reverse("assinaturas:assinatura-verificar-codigo", kwargs={"codigo": self.ass.codigo_verificacao})
        r = c.get(url)
        self.assertEqual(r.status_code, 200)

    def test_codigo_invalido_404(self):
        c = Client()
        url = reverse("assinaturas:assinatura-verificar-codigo", kwargs={"codigo": "CV-2099-XXXXXX-YYYY"})
        r = c.get(url)
        self.assertEqual(r.status_code, 404)

    def test_pagina_mostra_codigo_e_hash(self):
        c = Client()
        url = reverse("assinaturas:assinatura-verificar-codigo", kwargs={"codigo": self.ass.codigo_verificacao})
        r = c.get(url)
        self.assertContains(r, self.ass.codigo_verificacao)
        self.assertContains(r, self.ass.hash_documento[:16])

    def test_pdf_assinado_inline_content_type(self):
        c = Client()
        url = reverse("assinaturas:assinatura-pdf-assinado", kwargs={"assinatura_id": self.ass.pk})
        r = c.get(url)
        self.assertEqual(r.status_code, 200)
        ct = r.headers.get("Content-Type") or ""
        self.assertTrue(ct.startswith("application/pdf"))

    def test_hash_alterado_indica_integridade_falha(self):
        self.art.arquivo_assinado.save("x.pdf", ContentFile(b"alterado"), save=True)
        c = Client()
        url = reverse("assinaturas:assinatura-verificar-codigo", kwargs={"codigo": self.ass.codigo_verificacao})
        r = c.get(url)
        self.assertContains(r, "data-testid=\"integridade-falha\"")
