import hashlib

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import Servidor
from documentos.models import DocumentoArtefato
from documentos.models import DocumentoAssinaturaVersao
from documentos.services.access import select_artefato_pdf_fieldfile
from documentos.services.exceptions import ArquivoAssinadoInvalido
from documentos.services.persistence import anexar_arquivo_assinado
from documentos.services.persistence import remover_arquivo_assinado
from oficios.models import Oficio


def _pdf_bytes(marker: bytes = b"") -> bytes:
    return b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n" + marker


@override_settings(DOCUMENTOS_PERSIST_ARTEFATOS=True)
class AnexarArquivoAssinadoServiceTests(TestCase):
    def setUp(self):
        raw = _pdf_bytes()
        self.artefato = DocumentoArtefato.objects.create(
            tipo="termo_autorizacao",
            formato="pdf",
            hash_sha256=hashlib.sha256(raw).hexdigest(),
            arquivo=ContentFile(raw, name="gerado.pdf"),
        )

    def test_anexar_salva_arquivo_e_marca_assinado(self):
        upload = SimpleUploadedFile("assinado.pdf", _pdf_bytes(b"assinado"), content_type="application/pdf")
        anexar_arquivo_assinado(self.artefato, upload)
        self.artefato.refresh_from_db()
        self.assertTrue(self.artefato.esta_assinado)
        self.assertIsNotNone(self.artefato.assinado_em)
        self.assertEqual(self.artefato.assinado_nome_original, "assinado.pdf")
        self.assertEqual(self.artefato.versoes_assinadas.count(), 1)

    def test_substituir_preserva_as_versoes_anteriores(self):
        anexar_arquivo_assinado(
            self.artefato,
            SimpleUploadedFile("v1.pdf", _pdf_bytes(b"v1")),
        )
        anexar_arquivo_assinado(
            self.artefato,
            SimpleUploadedFile("v2.pdf", _pdf_bytes(b"v2")),
        )

        self.assertEqual(self.artefato.versoes_assinadas.count(), 2)
        self.assertEqual(
            self.artefato.versoes_assinadas.values("hash_sha256").distinct().count(),
            2,
        )

    def test_anexar_rejeita_extensao_errada(self):
        upload = SimpleUploadedFile("assinado.docx", _pdf_bytes(), content_type="application/pdf")
        with self.assertRaises(ArquivoAssinadoInvalido):
            anexar_arquivo_assinado(self.artefato, upload)

    def test_anexar_rejeita_conteudo_que_nao_e_pdf_de_verdade(self):
        upload = SimpleUploadedFile("assinado.pdf", b"isso nao e um pdf", content_type="application/pdf")
        with self.assertRaises(ArquivoAssinadoInvalido):
            anexar_arquivo_assinado(self.artefato, upload)

    def test_remover_limpa_campos_e_volta_a_servir_o_gerado(self):
        upload = SimpleUploadedFile("assinado.pdf", _pdf_bytes(b"assinado"), content_type="application/pdf")
        anexar_arquivo_assinado(self.artefato, upload)
        self.artefato.refresh_from_db()
        self.assertTrue(self.artefato.esta_assinado)

        remover_arquivo_assinado(self.artefato)
        self.artefato.refresh_from_db()
        self.assertFalse(self.artefato.esta_assinado)
        self.assertIsNone(self.artefato.assinado_em)
        self.assertEqual(self.artefato.assinado_nome_original, "")
        versao = self.artefato.versoes_assinadas.get()
        self.assertIsNotNone(versao.revogada_em)
        self.assertTrue(versao.arquivo.storage.exists(versao.arquivo.name))

    def test_versao_assinada_nao_pode_ser_excluida(self):
        anexar_arquivo_assinado(
            self.artefato,
            SimpleUploadedFile("assinado.pdf", _pdf_bytes(b"imutavel")),
        )

        with self.assertRaises(ValidationError):
            DocumentoAssinaturaVersao.objects.get().delete()

    def test_select_artefato_pdf_fieldfile_prefere_assinado(self):
        upload = SimpleUploadedFile("assinado.pdf", _pdf_bytes(b"assinado"), content_type="application/pdf")
        anexar_arquivo_assinado(self.artefato, upload)
        self.artefato.refresh_from_db()
        field = select_artefato_pdf_fieldfile(self.artefato)
        self.assertEqual(field.name, self.artefato.arquivo_assinado.name)


@override_settings(DOCUMENTOS_PERSIST_ARTEFATOS=True)
class ArtefatoAssinadoViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="assinado_u", password="x" * 12)
        self.client.force_login(self.user)
        self.cargo = Cargo.objects.create(nome="Cargo Assinado")
        self.servidor = Servidor.objects.create(nome="Serv Assinado", cargo=self.cargo, cpf="98765432100")
        self.oficio = Oficio.objects.create(
            protocolo="11.222.333-4",
            motivo="m",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        self.oficio.servidores.add(self.servidor)
        raw = _pdf_bytes()
        self.artefato = DocumentoArtefato.objects.create(
            tipo="termo_autorizacao",
            formato="pdf",
            oficio=self.oficio,
            servidor=self.servidor,
            hash_sha256=hashlib.sha256(raw).hexdigest(),
            arquivo=ContentFile(raw, name="gerado.pdf"),
        )

    def test_post_anexar_com_pdf_valido_marca_assinado(self):
        url = reverse("documentos:artefato_assinado_anexar", args=[self.artefato.pk])
        upload = SimpleUploadedFile("assinado.pdf", _pdf_bytes(b"assinado"), content_type="application/pdf")
        r = self.client.post(url, {"arquivo": upload})
        self.assertEqual(r.status_code, 302)
        self.artefato.refresh_from_db()
        self.assertTrue(self.artefato.esta_assinado)

    def test_post_anexar_sem_arquivo_nao_marca_assinado(self):
        url = reverse("documentos:artefato_assinado_anexar", args=[self.artefato.pk])
        r = self.client.post(url, {})
        self.assertEqual(r.status_code, 302)
        self.artefato.refresh_from_db()
        self.assertFalse(self.artefato.esta_assinado)

    def test_post_remover_limpa_assinado(self):
        upload = SimpleUploadedFile("assinado.pdf", _pdf_bytes(b"assinado"), content_type="application/pdf")
        anexar_arquivo_assinado(self.artefato, upload)
        url = reverse("documentos:artefato_assinado_remover", args=[self.artefato.pk])
        r = self.client.post(url)
        self.assertEqual(r.status_code, 302)
        self.artefato.refresh_from_db()
        self.assertFalse(self.artefato.esta_assinado)

    def test_get_nao_e_permitido(self):
        url = reverse("documentos:artefato_assinado_anexar", args=[self.artefato.pk])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 405)
