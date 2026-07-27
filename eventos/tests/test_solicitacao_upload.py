from io import BytesIO
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from eventos.models import Evento, EventoDocumentoSolicitacao
from eventos.services import converter_para_pdf_se_necessario
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buffer, format="PNG")
    return buffer.getvalue()


class ConverterParaPdfSeNecessarioTests(TestCase):
    def test_pdf_passa_direto_sem_conversao(self):
        arquivo = SimpleUploadedFile("doc.pdf", b"%PDF-1.4\n%%EOF\n", content_type="application/pdf")
        resultado = converter_para_pdf_se_necessario(arquivo)
        self.assertIs(resultado, arquivo)

    def test_png_e_convertido_para_pdf(self):
        arquivo = SimpleUploadedFile("foto.png", _png_bytes(), content_type="image/png")
        resultado = converter_para_pdf_se_necessario(arquivo)
        self.assertEqual(resultado.name, "foto.pdf")
        self.assertTrue(resultado.read().startswith(b"%PDF"))


class UploadSolicitacaoViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester", password="123456")
        self.client.force_login(self.user)
        self.evento = Evento.objects.create(titulo="Evento de teste")
        self.url = reverse("eventos:guiado_etapa", kwargs={"pk": self.evento.pk, "etapa": 4})

    def test_upload_imagem_e_salvo_como_pdf(self):
        arquivo = SimpleUploadedFile("convite.png", _png_bytes(), content_type="image/png")
        resp = self.client.post(self.url, {"action": "upload_solicitacao", "solicitacao_arquivos": arquivo})
        self.assertEqual(resp.status_code, 302)

        anexo = EventoDocumentoSolicitacao.objects.get(evento=self.evento)
        self.assertTrue(anexo.arquivo.name.lower().endswith(".pdf"))
        self.assertTrue(anexo.nome_original.lower().endswith(".pdf"))
        with anexo.arquivo.open("rb") as f:
            self.assertTrue(f.read().startswith(b"%PDF"))

    def test_upload_pdf_continua_pdf(self):
        arquivo = SimpleUploadedFile("oficio.pdf", b"%PDF-1.4\n%%EOF\n", content_type="application/pdf")
        resp = self.client.post(self.url, {"action": "upload_solicitacao", "solicitacao_arquivos": arquivo})
        self.assertEqual(resp.status_code, 302)

        anexo = EventoDocumentoSolicitacao.objects.get(evento=self.evento)
        self.assertTrue(anexo.arquivo.name.lower().endswith(".pdf"))

    def test_upload_com_conteudo_corrompido_e_rejeitado(self):
        arquivo = SimpleUploadedFile("foto.png", b"nao e uma imagem de verdade", content_type="image/png")
        resp = self.client.post(self.url, {"action": "upload_solicitacao", "solicitacao_arquivos": arquivo})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(EventoDocumentoSolicitacao.objects.filter(evento=self.evento).exists())


class SolicitacaoConteudoPrivadoTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media_dir.name,
            PRIVATE_MEDIA_X_ACCEL_REDIRECT=False,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="AREA-A")
        self.outra_area = AreaTrabalho.objects.create(nome="Área B", sigla="AREA-B")
        self.user = get_user_model().objects.create_user(username="arquivo", password="123456")
        VinculoUsuarioArea.objects.create(
            usuario=self.user,
            area=self.area,
            area_padrao=True,
        )
        self.client.force_login(self.user)

    def _anexo(self, area):
        evento = Evento.objects.create(titulo="Evento privado", area=area)
        anexo = EventoDocumentoSolicitacao.objects.create(
            evento=evento,
            arquivo=ContentFile(b"%PDF-1.4\nprivado", name="privado.pdf"),
            nome_original="privado.pdf",
        )
        return evento, anexo

    def test_entrega_arquivo_da_area_autorizada_sem_url_publica(self):
        evento, anexo = self._anexo(self.area)
        url = reverse("eventos:solicitacao_anexo_conteudo", args=[evento.pk, anexo.pk])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4\nprivado")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertNotIn("/media/", url)

    def test_arquivo_de_outra_area_retorna_404(self):
        evento, anexo = self._anexo(self.outra_area)
        url = reverse("eventos:solicitacao_anexo_conteudo", args=[evento.pk, anexo.pk])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)
