"""Download PDF com motor indisponível: redirect amigável ao wizard de documentos."""

from unittest import mock

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from documentos.services.exceptions import DocumentValidationError
from documentos.services.types import DocumentoFormato
from oficios.models import Oficio


class DocumentoPdfErroAmigavelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester_pdf_ux", password="123456")
        self.client.force_login(self.user)

    @mock.patch("oficios.views.validar_oficio_para_documento", return_value={"pendencias": [], "status": "complete", "checks": {}})
    @mock.patch(
        "oficios.views.gerar_resposta_documento_oficio",
        side_effect=DocumentValidationError("Motor PDF indisponível para teste."),
    )
    def test_baixar_oficio_pdf_erro_redireciona_com_mensagem(self, *_mocks):
        oficio = Oficio.objects.create(numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        url_pdf = reverse("oficios:baixar_documento", args=[oficio.pk, DocumentoFormato.PDF.value])
        response = self.client.get(url_pdf, follow=True)
        self.assertEqual(response.redirect_chain[0][0], reverse("oficios:wizard_documentos", args=[oficio.pk]))
        self.assertEqual(response.redirect_chain[0][1], 302)
        self.assertContains(response, "Motor PDF indisponível para teste.")

    @mock.patch("oficios.views.validar_oficio_para_documento", return_value={"pendencias": [], "status": "complete", "checks": {}})
    @mock.patch("oficios.views.gerar_resposta_documento_oficio")
    def test_baixar_oficio_docx_nao_usa_redirect_de_pdf(self, m_gerar, _m_validar):
        oficio = Oficio.objects.create(numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        m_gerar.return_value = HttpResponse(b"x", content_type="application/octet-stream")
        url_docx = reverse("oficios:baixar_documento", args=[oficio.pk, DocumentoFormato.DOCX.value])
        response = self.client.get(url_docx)
        self.assertEqual(response.status_code, 200)
        m_gerar.assert_called_once()
