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
from core.testing import area_de_teste
from core.testing import vincular_area


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buffer, format="PNG")
    return buffer.getvalue()


def _bmp_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (10, 10), color="blue").save(buffer, format="BMP")
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
        vincular_area(self.user)
        self.client.force_login(self.user)
        self.evento = Evento.objects.create(area=area_de_teste(), titulo="Evento de teste")
        self.url = reverse("eventos:guiado_etapa", kwargs={"pk": self.evento.pk, "etapa": 4})
        self.anexar_url = reverse("eventos:solicitacao_anexar", kwargs={"pk": self.evento.pk})

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

    def test_modal_anexar_aceita_arquivo_unico(self):
        arquivo = SimpleUploadedFile("convite.png", _png_bytes(), content_type="image/png")
        resp = self.client.post(self.anexar_url, {"arquivo": arquivo})
        self.assertEqual(resp.status_code, 302)

        anexo = EventoDocumentoSolicitacao.objects.get(evento=self.evento)
        self.assertTrue(anexo.arquivo.name.lower().endswith(".pdf"))

    def test_modal_anexar_aceita_varios_arquivos_e_converte_toda_imagem(self):
        arquivos = [
            SimpleUploadedFile("convite.png", _png_bytes(), content_type="image/png"),
            SimpleUploadedFile("foto.bmp", _bmp_bytes(), content_type="image/bmp"),
        ]

        resp = self.client.post(self.anexar_url, {"arquivo": arquivos})

        self.assertEqual(resp.status_code, 302)
        anexos = list(EventoDocumentoSolicitacao.objects.filter(evento=self.evento))
        self.assertEqual([anexo.nome_original for anexo in anexos], ["convite.pdf", "foto.pdf"])
        for anexo in anexos:
            with anexo.arquivo.open("rb") as arquivo:
                self.assertTrue(arquivo.read().startswith(b"%PDF"))

    def test_etapa4_oferece_anexar_documento_e_menu_unico_de_criacao(self):
        """A etapa 4 concentra os dois fluxos de criação em um único FAB V2."""
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "evento-etapa4-actions-menu")
        self.assertContains(resp, "Anexar documento")
        self.assertContains(resp, "panel__header panel__header--centered")
        self.assertContains(resp, "data-attach-signed-url")
        self.assertContains(resp, 'data-attach-signed-multiple="true"')
        self.assertContains(resp, 'data-attach-signed-accept="application/pdf,.pdf,image/*"')
        self.assertContains(resp, self.anexar_url)
        self.assertContains(resp, 'data-overlay-target="evento-planejamento-create-menu"')
        self.assertContains(resp, 'id="evento-planejamento-create-menu"')
        self.assertContains(resp, "Ordem de Serviço")
        self.assertContains(resp, "Plano de Trabalho")
        self.assertContains(resp, resp.context["create_urls"]["ordem"])
        self.assertContains(resp, resp.context["create_urls"]["plano"])
        self.assertNotContains(resp, "Novo plano")
        self.assertNotContains(resp, "Nova OS")

    def test_acoes_do_arquivo_usam_a_superficie_do_painel(self):
        EventoDocumentoSolicitacao.objects.create(
            evento=self.evento,
            arquivo=ContentFile(b"%PDF-1.4\n%%EOF\n", name="solicitacao.pdf"),
            nome_original="solicitacao.pdf",
        )

        resp = self.client.get(self.url)

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'class="icon-button file-list__action"', count=2)


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
