from django.test import SimpleTestCase

from documentos.services.signing import assinar_pdf_final


class SigningTests(SimpleTestCase):
    def test_assinar_disabled_returns_same_bytes(self):
        b = b"%PDF-1.4 test"
        out, meta = assinar_pdf_final(b)
        self.assertEqual(out, b)
        self.assertEqual(meta.get("backend"), "disabled")
        self.assertEqual(meta.get("sha256_in"), meta.get("sha256_out"))
        self.assertIn("field_name", meta)
