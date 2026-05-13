import hashlib

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import Servidor
from documentos.models import DocumentoArtefato
from oficios.models import Oficio


def _minimal_pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@override_settings(DOCUMENTOS_PERSIST_ARTEFATOS=True, SIGNATURE_BACKEND="disabled")
class AssinarArtefatoViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="sign_u", password="y" * 12)
        self.client.force_login(self.user)
        self.cargo = Cargo.objects.create(nome="Cargo S")
        self.servidor = Servidor.objects.create(nome="Serv S", cargo=self.cargo, cpf="98765432100")
        self.oficio = Oficio.objects.create(
            protocolo="11.222.333-4",
            motivo="m",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        self.oficio.servidores.add(self.servidor)

    def _pdf_artefato(self) -> DocumentoArtefato:
        raw = _minimal_pdf_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        return DocumentoArtefato.objects.create(
            tipo="oficio",
            formato="pdf",
            oficio=self.oficio,
            hash_sha256=digest,
            arquivo=ContentFile(raw, name="oficio_sign_test.pdf"),
        )

    def test_assinar_requer_login(self):
        art = self._pdf_artefato()
        self.client.logout()
        url = reverse("documentos:assinar_artefato", args=[art.pk])
        r = self.client.post(url)
        self.assertEqual(r.status_code, 302)

    def test_assinar_docx_artefato_404(self):
        raw = b"x"
        digest = hashlib.sha256(raw).hexdigest()
        art = DocumentoArtefato.objects.create(
            tipo="oficio",
            formato="docx",
            oficio=self.oficio,
            hash_sha256=digest,
            arquivo=ContentFile(raw, name="x.docx"),
        )
        url = reverse("documentos:assinar_artefato", args=[art.pk])
        r = self.client.post(url)
        self.assertEqual(r.status_code, 404)

    def test_assinar_pdf_disabled_persiste_e_responde(self):
        art = self._pdf_artefato()
        url = reverse("documentos:assinar_artefato", args=[art.pk])
        r = self.client.post(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertEqual(r["X-Signature-Backend"], "disabled")
        art.refresh_from_db()
        self.assertTrue(art.arquivo_assinado.name)
        self.assertTrue(art.hash_sha256_assinado)
