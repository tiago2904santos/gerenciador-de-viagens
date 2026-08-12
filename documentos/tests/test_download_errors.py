from types import SimpleNamespace
from unittest import mock

from django.contrib.messages.middleware import MessageMiddleware
from django.http import HttpResponse
from django.test import RequestFactory
from django.test import SimpleTestCase
from django.test import override_settings
from django.urls import reverse

from documentos.services.adapters import weasyprint_pdf
from documentos.services.downloads import download_documento_or_redirect_pdf_error
from documentos.services.exceptions import DocumentValidationError
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo
from documentos.services import warm_cache


def _request():
    request = RequestFactory().get("/")
    request.session = {}
    MessageMiddleware(lambda req: None).process_request(request)
    return request


class DownloadDocumentErrorTests(SimpleTestCase):
    def test_docx_nao_engole_erro_de_geracao(self):
        def gerar():
            raise DocumentValidationError("DOCX inválido")

        with self.assertRaisesMessage(DocumentValidationError, "DOCX inválido"):
            download_documento_or_redirect_pdf_error(
                _request(), oficio_id=7, formato=DocumentoFormato.DOCX, gerar=gerar
            )

    def test_pdf_invalido_redireciona_e_expoe_mensagem(self):
        request = _request()

        response = download_documento_or_redirect_pdf_error(
            request,
            oficio_id=7,
            formato=DocumentoFormato.PDF,
            gerar=mock.Mock(side_effect=DocumentValidationError("Motor indisponível")),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("oficios:wizard_documentos", args=[7]))
        self.assertEqual([str(message) for message in request._messages], ["Motor indisponível"])

    def test_pdf_valido_devolve_resposta_do_gerador(self):
        expected = HttpResponse(b"%PDF")
        response = download_documento_or_redirect_pdf_error(
            _request(), oficio_id=7, formato=DocumentoFormato.PDF, gerar=lambda: expected
        )
        self.assertIs(response, expected)


class WeasyPrintAdapterErrorTests(SimpleTestCase):
    def test_biblioteca_nativa_ausente_vira_erro_operacional(self):
        original_import = __import__

        def import_with_native_error(name, *args, **kwargs):
            if name == "weasyprint":
                raise OSError("libgobject ausente")
            return original_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=import_with_native_error):
            with self.assertRaisesMessage(RuntimeError, "bibliotecas nativas"):
                weasyprint_pdf.render_pdf_bytes_weasyprint(
                    html_template_name="unused.html", context={}, stylesheet_paths=()
                )

    @override_settings(DOCUMENTOS_BASE_URL="https://documentos.example/")
    def test_render_configura_base_url_e_desliga_dicas_de_apresentacao(self):
        html = mock.Mock()
        html.write_pdf.return_value = b"%PDF-ok"
        html_factory = mock.Mock(return_value=html)
        fake_module = SimpleNamespace(HTML=html_factory, CSS=mock.Mock())

        with mock.patch.dict("sys.modules", {"weasyprint": fake_module}):
            with mock.patch.object(weasyprint_pdf, "render_to_string", return_value="<p>ok</p>"):
                result = weasyprint_pdf.render_pdf_bytes_weasyprint(
                    html_template_name="documento.html", context={"nome": "A"}, stylesheet_paths=()
                )

        self.assertEqual(result, b"%PDF-ok")
        html_factory.assert_called_once_with(string="<p>ok</p>", base_url="https://documentos.example/")
        html.write_pdf.assert_called_once_with(stylesheets=[], presentational_hints=False)


class WarmCacheErrorTests(SimpleTestCase):
    def test_arquivo_inacessivel_por_erro_de_storage_retorna_false(self):
        storage = mock.Mock()
        storage.exists.side_effect = OSError("storage fora")
        artefato = SimpleNamespace(arquivo=SimpleNamespace(name="oficio.pdf", storage=storage))

        self.assertFalse(warm_cache.pdf_artefato_original_acessivel(artefato))

    @override_settings(DOCUMENTOS_PREGENERATE_PDF=True)
    def test_falha_ao_enfileirar_nao_quebra_request(self):
        oficio = SimpleNamespace(pk=42)
        task = mock.Mock()
        task.delay.side_effect = RuntimeError("broker fora")

        with mock.patch("oficios.services.validar_oficio_para_documento", return_value={"pendencias": []}):
            with mock.patch("documentos.tasks.gerar_pdf_oficio_cache", task):
                with self.assertLogs(warm_cache.logger, level="WARNING") as logs:
                    result = warm_cache.ensure_document_artifact_cached(
                        oficio, tipo=DocumentoTipo.OFICIO
                    )

        self.assertIsNone(result)
        self.assertIn("não foi enfileirada", logs.output[0])

    @override_settings(DOCUMENTOS_PREGENERATE_PDF=True)
    def test_pendencia_documental_impede_enfileirar(self):
        task = mock.Mock()
        with mock.patch(
            "oficios.services.validar_oficio_para_documento",
            return_value={"pendencias": ["servidor"]},
        ):
            with mock.patch("documentos.tasks.gerar_pdf_oficio_cache", task):
                warm_cache.ensure_document_artifact_cached(
                    SimpleNamespace(pk=42), tipo=DocumentoTipo.OFICIO
                )
        task.delay.assert_not_called()
