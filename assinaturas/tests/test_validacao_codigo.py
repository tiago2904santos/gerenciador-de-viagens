from __future__ import annotations

import hashlib
from io import StringIO

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings

from assinaturas.services.assinatura_artefato import assinar_artefato_com_etiqueta
from assinaturas.services.validacao_codigo import validar_assinatura_por_codigo
from cadastros.models import Servidor
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
class ValidacaoCodigoTests(TestCase):
    def setUp(self):
        raw = _pdf()
        d = hashlib.sha256(raw).hexdigest()
        self.servidor = Servidor.objects.create(nome="S")
        self.art = DocumentoArtefato.objects.create(
            tipo="t",
            formato="pdf",
            servidor=self.servidor,
            hash_sha256=d,
            arquivo=ContentFile(raw, name="v.pdf"),
        )
        rf = RequestFactory()
        req = rf.get("/")
        req.META["HTTP_HOST"] = "testserver"
        self.ass = assinar_artefato_com_etiqueta(self.art, nome_assinante="Z", request=req)

    def test_valido(self):
        r = validar_assinatura_por_codigo(self.ass.codigo_verificacao)
        self.assertTrue(r["existe"])
        self.assertTrue(r["integra"])

    def test_inexistente(self):
        r = validar_assinatura_por_codigo("CV-2099-ABCDEF-GHIJ")
        self.assertFalse(r["existe"])

    def test_alterado_invalida(self):
        self.art.arquivo_assinado.save("x.pdf", ContentFile(b"x"), save=True)
        r = validar_assinatura_por_codigo(self.ass.codigo_verificacao)
        self.assertFalse(r["integra"])

    def test_management_command(self):
        out = StringIO()
        call_command("diagnosticar_assinatura_pdf", self.ass.codigo_verificacao, stdout=out)
        self.assertIn("integra", out.getvalue().lower())
