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
class AssinaturasApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="api_sig_u", password="z" * 12)
        self.client.force_login(self.user)
        self.cargo = Cargo.objects.create(nome="Cargo API")
        self.servidor = Servidor.objects.create(nome="Serv API", cargo=self.cargo, cpf="11122233344")
        self.oficio = Oficio.objects.create(
            protocolo="55.666.777-8",
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
            arquivo=ContentFile(raw, name="oficio_api.pdf"),
        )

    def test_api_verificar_sem_assinatura_retorna_422(self):
        art = self._pdf_artefato()
        url = reverse("assinaturas:api_verificar_documento", args=[art.pk])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 422)
        data = r.json()
        self.assertFalse(data.get("ok"))

    def test_api_assinar_json_disabled(self):
        art = self._pdf_artefato()
        url = reverse("assinaturas:api_assinar_documento", args=[art.pk])
        r = self.client.post(url)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body.get("ok"))
        self.assertEqual(body.get("meta", {}).get("backend"), "disabled")
