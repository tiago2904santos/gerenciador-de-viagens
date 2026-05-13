import hashlib
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import Servidor
from documentos.models import DocumentoArtefato
from documentos.services.temporary_links import create_artefato_pdf_temp_token
from oficios.models import Oficio


def _minimal_pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@override_settings(DOCUMENTOS_PERSIST_ARTEFATOS=True)
class ArtefatoPdfViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="pdf_viewer_u", password="x" * 12)
        self.client.force_login(self.user)
        self.cargo = Cargo.objects.create(nome="Cargo PDFV")
        self.servidor = Servidor.objects.create(nome="Serv PDFV", cargo=self.cargo, cpf="12345678901")
        self.oficio = Oficio.objects.create(
            protocolo="99.888.777-6",
            motivo="m",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        self.oficio.servidores.add(self.servidor)

    def _create_artefato(self) -> DocumentoArtefato:
        raw = _minimal_pdf_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        return DocumentoArtefato.objects.create(
            tipo="oficio",
            formato="pdf",
            oficio=self.oficio,
            hash_sha256=digest,
            arquivo=ContentFile(raw, name="oficio_test.pdf"),
        )

    def test_conteudo_inline_headers_and_range(self):
        art = self._create_artefato()
        url = reverse("documentos:artefato_pdf_conteudo", args=[art.pk])
        path = Path(settings.MEDIA_ROOT) / art.arquivo.name
        size = path.stat().st_size
        r206 = self.client.get(url, HTTP_RANGE="bytes=0-3")
        self.assertEqual(r206.status_code, 206)
        self.assertEqual(r206["Content-Type"], "application/pdf")
        self.assertIn("inline", r206["Content-Disposition"])
        self.assertEqual(r206["Accept-Ranges"], "bytes")
        self.assertEqual(r206["Content-Range"], f"bytes 0-3/{size}")

        r416 = self.client.get(url, HTTP_RANGE=f"bytes={size}-{size + 5}")
        self.assertEqual(r416.status_code, 416)

    def test_visualizar_renders(self):
        art = self._create_artefato()
        url = reverse("documentos:artefato_pdf_visualizar", args=[art.pk])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "documentos-pdf-viewer.js")

    def test_conteudo_publico_with_token(self):
        art = self._create_artefato()
        self.client.logout()
        tok = create_artefato_pdf_temp_token(str(art.pk))
        url = reverse("documentos:artefato_pdf_conteudo_publico") + f"?t={tok}"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")

    def test_docx_artefato_404_on_conteudo(self):
        raw = b"not pdf"
        digest = hashlib.sha256(raw).hexdigest()
        art = DocumentoArtefato.objects.create(
            tipo="oficio",
            formato="docx",
            oficio=self.oficio,
            hash_sha256=digest,
            arquivo=ContentFile(raw, name="oficio_test.docx"),
        )
        url = reverse("documentos:artefato_pdf_conteudo", args=[art.pk])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)
