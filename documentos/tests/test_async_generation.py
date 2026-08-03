from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import reverse

from oficios.models import Oficio
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea

from documentos.models import DocumentoGeracao
from documentos.tasks import gerar_documento_assincrono


class DocumentoGeracaoModelTests(TestCase):
    def test_job_novo_comeca_na_fila_e_sem_arquivo(self):
        job = DocumentoGeracao.objects.create(
            tipo="oficio",
            parametros={"object_id": 17, "formato": "pdf"},
        )

        self.assertEqual(job.status, DocumentoGeracao.STATUS_NA_FILA)
        self.assertFalse(job.arquivo)

    @mock.patch("documentos.services.async_generation.gerar_resposta_do_job")
    def test_task_persiste_resultado_para_download_posterior(self, gerar):
        response = HttpResponse(b"%PDF-1.4\n", content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="oficio.pdf"'
        gerar.return_value = response
        job = DocumentoGeracao.objects.create(
            tipo="oficio",
            parametros={"object_id": 17, "formato": "pdf"},
        )

        gerar_documento_assincrono(str(job.pk))

        job.refresh_from_db()
        self.addCleanup(job.arquivo.delete, save=False)
        self.assertEqual(job.status, DocumentoGeracao.STATUS_CONCLUIDO)
        self.assertEqual(job.nome_arquivo, "oficio.pdf")
        self.assertTrue(job.hash_sha256)
        with job.arquivo.open("rb") as generated:
            self.assertEqual(generated.read(), b"%PDF-1.4\n")


@override_settings(CELERY_TASK_ALWAYS_EAGER=False)
class DocumentoGeracaoHttpTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="s06",
        )
        self.client.force_login(self.user)
        self.oficio = Oficio.objects.create(numero=1, ano=2026)

    @mock.patch("documentos.tasks.gerar_documento_assincrono.delay")
    @mock.patch(
        "oficios.document_views.validar_oficio_para_documento",
        return_value={"status": "complete", "pendencias": []},
    )
    def test_download_ajax_apenas_enfileira_e_devolve_polling(self, _validar, delay):
        url = reverse(
            "oficios:baixar_documento",
            args=[self.oficio.pk, "pdf"],
        )

        response = self.client.get(
            url,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        job = DocumentoGeracao.objects.get()
        delay.assert_called_once_with(str(job.pk))
        self.assertEqual(payload["status"], DocumentoGeracao.STATUS_NA_FILA)
        self.assertEqual(payload["status_url"], reverse("documentos:geracao_status", args=[job.pk]))
        self.assertNotIn("result_url", payload)

    @mock.patch("documentos.tasks.gerar_documento_assincrono.delay")
    @mock.patch(
        "oficios.document_views.validar_oficio_para_documento",
        return_value={"status": "complete", "pendencias": []},
    )
    def test_geracao_em_iframe_usa_tela_embutida_sem_shell(self, _validar, _delay):
        url = reverse(
            "oficios:baixar_documento",
            args=[self.oficio.pk, "pdf"],
        )

        response = self.client.get(url, HTTP_SEC_FETCH_DEST="iframe")

        self.assertEqual(response.status_code, 202)
        self.assertTemplateUsed(response, "documentos/geracao_aguarde_embedded.html")
        self.assertContains(response, "data-document-generation-wait", status_code=202)
        self.assertNotContains(response, 'class="app-shell', status_code=202)

    def test_status_e_resultado_respeitam_area_do_request(self):
        job = DocumentoGeracao.objects.create(
            tipo="oficio",
            parametros={"object_id": self.oficio.pk, "formato": "pdf"},
        )

        status_response = self.client.get(
            reverse("documentos:geracao_status", args=[job.pk]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], DocumentoGeracao.STATUS_NA_FILA)

    def test_resultado_inline_preserva_headers_e_conteudo(self):
        job = DocumentoGeracao.objects.create(
            tipo="oficio",
            parametros={"object_id": self.oficio.pk, "formato": "pdf"},
            status=DocumentoGeracao.STATUS_CONCLUIDO,
            disposicao="inline",
            nome_arquivo="oficio.pdf",
            content_type="application/pdf",
            hash_sha256="abc",
        )
        job.arquivo.save("oficio.pdf", ContentFile(b"%PDF-1.4\n"))
        self.addCleanup(job.arquivo.delete, save=False)

        response = self.client.get(
            reverse("documentos:geracao_resultado", args=[job.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("inline", response["Content-Disposition"])
        self.assertEqual(response["X-Frame-Options"], "SAMEORIGIN")
        self.assertEqual(response["X-Document-SHA256"], "abc")
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4\n")

    def test_job_de_outra_area_retorna_404(self):
        area_usuario = AreaTrabalho.objects.create(nome="Área A", sigla="A")
        area_job = AreaTrabalho.objects.create(nome="Área B", sigla="B")
        VinculoUsuarioArea.objects.create(
            usuario=self.user,
            area=area_usuario,
            area_padrao=True,
        )
        job = DocumentoGeracao.objects.create(
            area=area_job,
            tipo="oficio",
            parametros={"object_id": self.oficio.pk, "formato": "pdf"},
        )

        response = self.client.get(
            reverse("documentos:geracao_status", args=[job.pk]),
        )

        self.assertEqual(response.status_code, 404)
