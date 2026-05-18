from __future__ import annotations

import hashlib

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings

from assinaturas.models import AssinaturaDigital
from assinaturas.services.assinatura_artefato import assinar_artefato_com_etiqueta
from assinaturas.services.assinatura_artefato import assinatura_arquivo_esta_integra
from assinaturas.services.codigos import codigo_tem_formato_valido
from documentos.models import DocumentoArtefato


def _minimal_pdf() -> bytes:
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
class AssinaturaArtefatoServiceTests(TestCase):
    def setUp(self):
        raw = _minimal_pdf()
        digest = hashlib.sha256(raw).hexdigest()
        self.artefato = DocumentoArtefato.objects.create(
            tipo="teste",
            formato="pdf",
            hash_sha256=digest,
            arquivo=ContentFile(raw, name="t.pdf"),
        )
        self.user = get_user_model().objects.create_user(username="sig_u", password="p" * 12)

    def test_assina_pdf_simples_cria_registo(self):
        rf = RequestFactory()
        req = rf.get("/")
        req.META["HTTP_HOST"] = "testserver"
        ass = assinar_artefato_com_etiqueta(
            self.artefato,
            nome_assinante="Teste",
            cpf_assinante="12345678901",
            email_assinante="a@b.co",
            usuario=self.user,
            request=req,
            posicao=None,
        )
        self.assertIsInstance(ass, AssinaturaDigital)
        self.assertTrue(codigo_tem_formato_valido(ass.codigo_verificacao))

    def test_atualiza_arquivo_assinado_e_hashes(self):
        rf = RequestFactory()
        req = rf.get("/")
        req.META["HTTP_HOST"] = "testserver"
        ass = assinar_artefato_com_etiqueta(
            self.artefato,
            nome_assinante="X",
            cpf_assinante="",
            request=req,
        )
        self.artefato.refresh_from_db()
        self.assertTrue(self.artefato.arquivo_assinado.name)
        self.assertEqual(self.artefato.assinatura_backend, "etiqueta_pdf")
        self.assertEqual(ass.hash_documento, self.artefato.hash_sha256)
        self.assertEqual(ass.hash_documento_assinado, self.artefato.hash_sha256_assinado)

    def test_integridade_true_apos_assinar(self):
        rf = RequestFactory()
        req = rf.get("/")
        req.META["HTTP_HOST"] = "testserver"
        ass = assinar_artefato_com_etiqueta(self.artefato, nome_assinante="Y", request=req)
        self.assertTrue(assinatura_arquivo_esta_integra(ass))

    def test_integridade_false_se_alterar_ficheiro(self):
        rf = RequestFactory()
        req = rf.get("/")
        req.META["HTTP_HOST"] = "testserver"
        ass = assinar_artefato_com_etiqueta(self.artefato, nome_assinante="Z", request=req)
        self.artefato.arquivo_assinado.save("x.pdf", ContentFile(b"corrompido"), save=True)
        self.assertFalse(assinatura_arquivo_esta_integra(ass))

    def test_sem_pdf_falha(self):
        self.artefato.formato = "docx"
        self.artefato.save(update_fields=["formato"])
        with self.assertRaises(ValueError) as ctx:
            assinar_artefato_com_etiqueta(self.artefato, nome_assinante="N", request=None)
        self.assertIn("PDF", str(ctx.exception))
