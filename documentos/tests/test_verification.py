import hashlib
import os
from unittest import skipUnless

from django.test import SimpleTestCase
from django.test import override_settings

from assinaturas.services.verification import verificar_pdf_bytes
from documentos.services.signing import assinar_pdf_final


class PdfVerificationUnitTests(SimpleTestCase):
    def test_verificar_bytes_sem_assinatura(self):
        raw = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
        r = verificar_pdf_bytes(raw)
        self.assertFalse(r.get("ok"))
        self.assertIn(r.get("reason"), ("no_signatures", "pdf_read_error"))

    def test_verificar_bytes_invalidos(self):
        r = verificar_pdf_bytes(b"nada")
        self.assertFalse(r.get("ok"))
        self.assertEqual(r.get("reason"), "pdf_read_error")


@skipUnless(os.getenv("SIGNATURE_TEST_PKCS12_PATH"), "Define SIGNATURE_TEST_PKCS12_PATH para assinar com PKCS#12.")
@override_settings(
    SIGNATURE_BACKEND="pkcs12",
    SIGNATURE_PKCS12_PATH=os.getenv("SIGNATURE_TEST_PKCS12_PATH"),
    SIGNATURE_PKCS12_PASSWORD=os.getenv("SIGNATURE_TEST_PKCS12_PASSWORD", ""),
    SIGNATURE_VISIBLE=False,
)
class PdfVerificationPkcs12Tests(SimpleTestCase):
    def test_assinar_verificar_e_falhar_apos_adulteracao(self):
        raw = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
        signed, _meta = assinar_pdf_final(raw)
        ok = verificar_pdf_bytes(signed)
        self.assertTrue(ok.get("ok"), msg=ok.get("summary") or ok)

        tampered = signed[:-4] + b"XXXX"
        bad = verificar_pdf_bytes(tampered)
        self.assertFalse(bad.get("ok"))

        # Hash de negócio: conteúdo adulterado não coincide com digest do ficheiro íntegro
        self.assertNotEqual(hashlib.sha256(signed).hexdigest(), hashlib.sha256(tampered).hexdigest())
