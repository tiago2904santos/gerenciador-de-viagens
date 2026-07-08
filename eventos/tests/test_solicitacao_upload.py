from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from eventos.models import Evento, EventoDocumentoSolicitacao
from eventos.services import converter_para_pdf_se_necessario


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
