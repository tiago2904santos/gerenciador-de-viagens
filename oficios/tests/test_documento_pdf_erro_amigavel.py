"""Download PDF com motor indisponível: redirect amigável ao wizard de documentos."""

from unittest import mock

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from documentos.models import DocumentoGeracao
from documentos.services.exceptions import DocumentValidationError
from documentos.services.types import DocumentoFormato
from oficios.models import Oficio
from core.testing import area_de_teste
from core.testing import vincular_area


class DocumentoPdfErroAmigavelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester_pdf_ux", password="123456")
        self.client.force_login(self.user)
        vincular_area(self.user)

    @mock.patch("oficios.document_views.validar_oficio_para_documento", return_value={"pendencias": [], "status": "complete", "checks": {}})
    @mock.patch(
        "documentos.services.async_generation.gerar_resposta_do_job",
        side_effect=DocumentValidationError("Motor PDF indisponível para teste."),
    )
    def test_baixar_oficio_pdf_erro_fica_disponivel_no_polling(self, *_mocks):
        oficio = Oficio.objects.create(area=area_de_teste(), numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        url_pdf = reverse("oficios:baixar_documento", args=[oficio.pk, DocumentoFormato.PDF.value])
        response = self.client.get(url_pdf, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], DocumentoGeracao.STATUS_ERRO)
        self.assertEqual(response.json()["error"], "Motor PDF indisponível para teste.")

    @mock.patch("oficios.document_views.validar_oficio_para_documento", return_value={"pendencias": [], "status": "complete", "checks": {}})
    @mock.patch("documentos.services.async_generation.gerar_resposta_do_job")
    def test_baixar_oficio_docx_entrega_resultado_do_job(self, m_gerar, _m_validar):
        oficio = Oficio.objects.create(area=area_de_teste(), numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        m_gerar.return_value = HttpResponse(b"x", content_type="application/octet-stream")
        url_docx = reverse("oficios:baixar_documento", args=[oficio.pk, DocumentoFormato.DOCX.value])
        response = self.client.get(url_docx)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"x")
        m_gerar.assert_called_once()
