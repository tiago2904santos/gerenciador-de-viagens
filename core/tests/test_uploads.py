from unittest import mock

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.test import override_settings

from core.uploads import validate_private_document_upload


class PrivateUploadPolicyTests(SimpleTestCase):
    @override_settings(PRIVATE_UPLOAD_REQUIRE_ANTIVIRUS=False)
    def test_aceita_pdf_com_assinatura_valida(self):
        upload = SimpleUploadedFile(
            "documento.pdf",
            b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF",
            content_type="application/pdf",
        )

        validate_private_document_upload(upload)

    @override_settings(PRIVATE_UPLOAD_REQUIRE_ANTIVIRUS=False)
    def test_normaliza_nome_antes_do_armazenamento(self):
        upload = SimpleUploadedFile(
            "../../Relatório final (versão 1).PDF",
            b"%PDF-1.7\n%%EOF",
        )

        validate_private_document_upload(upload)

        self.assertEqual(upload.name, "Relatorio-final-versao-1.pdf")

    @override_settings(PRIVATE_UPLOAD_REQUIRE_ANTIVIRUS=False)
    def test_rejeita_extensao_pdf_com_conteudo_falso(self):
        upload = SimpleUploadedFile(
            "documento.pdf",
            b"<script>nao e pdf</script>",
            content_type="application/pdf",
        )

        with self.assertRaises(ValidationError):
            validate_private_document_upload(upload)

    @override_settings(
        PRIVATE_UPLOAD_REQUIRE_ANTIVIRUS=False,
        PRIVATE_UPLOAD_MAX_BYTES=4,
    )
    def test_rejeita_arquivo_acima_do_limite(self):
        upload = SimpleUploadedFile("documento.pdf", b"%PDF-1.7")

        with self.assertRaises(ValidationError):
            validate_private_document_upload(upload)

    @override_settings(
        PRIVATE_UPLOAD_REQUIRE_ANTIVIRUS=True,
        CLAMAV_SCAN_COMMAND="clamdscan",
    )
    @mock.patch("core.uploads.subprocess.run", side_effect=FileNotFoundError)
    def test_falha_fechada_quando_antivirus_esta_indisponivel(self, _run):
        upload = SimpleUploadedFile("documento.pdf", b"%PDF-1.7\n%%EOF")

        with self.assertRaisesMessage(ValidationError, "antivírus está indisponível"):
            validate_private_document_upload(upload)
