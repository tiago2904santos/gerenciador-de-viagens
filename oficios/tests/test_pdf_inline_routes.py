"""Rotas PDF inline: redirect com pendências; Content-Disposition inline quando completo."""

from unittest import mock

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from oficios.models import Oficio


class PdfInlineRoutesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester_inline", password="123456")
        self.client.force_login(self.user)
        self.oficio = Oficio.objects.create(numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)

    def _mock_download_pdf(self):
        resp = HttpResponse(b"%PDF-1.4\n", content_type="application/pdf")
        resp["Content-Disposition"] = 'attachment; filename="oficio-1-2026.pdf"'
        resp["X-Document-Cache"] = "MISS"
        resp["X-Document-SHA256"] = "abc"
        return resp

    @mock.patch("oficios.document_views.validar_oficio_para_documento", return_value={"pendencias": ["falta algo"]})
    def test_oficio_pdf_inline_redireciona_se_incompleto(self, _m):
        url = reverse("oficios:oficio_pdf_inline", args=[self.oficio.pk])
        response = self.client.get(url, follow=False)
        self.assertEqual(response.status_code, 302)

    @mock.patch("oficios.document_views.validar_oficio_para_documento", return_value={"pendencias": []})
    @mock.patch("documentos.services.async_generation.gerar_resposta_do_job")
    def test_oficio_pdf_inline_disposition_inline(self, m_dl, _m_val):
        m_dl.return_value = self._mock_download_pdf()
        url = reverse("oficios:oficio_pdf_inline", args=[self.oficio.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("inline", response["Content-Disposition"])
        self.assertNotIn("attachment", response["Content-Disposition"])
        self.assertEqual(response["X-Document-SHA256"], "abc")
        _ = b"".join(response.streaming_content)

    @mock.patch("oficios.document_views.validar_oficio_para_documento", return_value={"pendencias": []})
    @mock.patch("documentos.services.async_generation.gerar_resposta_do_job")
    def test_justificativa_ordem_urls_resolvem(self, m_dl, _m_val):
        m_dl.return_value = self._mock_download_pdf()
        for name in (
            "oficios:justificativa_pdf_inline",
            "oficios:ordem_servico_pdf_inline",
        ):
            url = reverse(name, args=[self.oficio.pk])
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, msg=name)
            self.assertIn("inline", response["Content-Disposition"], msg=name)

    def test_plano_trabalho_pdf_inline_removido_do_oficio(self):
        from django.urls import NoReverseMatch

        with self.assertRaises(NoReverseMatch):
            reverse("oficios:plano_trabalho_pdf_inline", args=[self.oficio.pk])
