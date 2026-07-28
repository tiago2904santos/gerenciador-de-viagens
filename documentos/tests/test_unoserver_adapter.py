import sys
from io import StringIO
from types import ModuleType
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.cache import cache
from django.test import SimpleTestCase
from django.test import override_settings

from documentos.services.adapters import libreoffice_pdf


class UnoserverAdapterTests(SimpleTestCase):
    @override_settings(DOCUMENTOS_BINARY_CONVERSION_CACHE=True)
    def test_cache_por_hash_evitar_segunda_conversao(self):
        cache.clear()
        converter = mock.Mock(return_value=b"%PDF-1.7\ncache")

        first = libreoffice_pdf._convert_with_cache(
            data=b"PK-conteudo-estavel",
            source_format="docx",
            engine="teste",
            converter=converter,
        )
        second = libreoffice_pdf._convert_with_cache(
            data=b"PK-conteudo-estavel",
            source_format="docx",
            engine="teste",
            converter=converter,
        )

        self.assertEqual(first, second)
        converter.assert_called_once()

    @mock.patch.object(libreoffice_pdf, "unoserver_healthcheck", return_value=True)
    def test_usa_cliente_xmlrpc_oficial_e_retorna_pdf(self, _healthcheck):
        client_instance = mock.Mock()
        client_instance.convert.return_value = b"%PDF-1.7\nconteudo"
        client_class = mock.Mock(return_value=client_instance)

        package = ModuleType("unoserver")
        client_module = ModuleType("unoserver.client")
        client_module.UnoClient = client_class

        with mock.patch.dict(
            sys.modules,
            {"unoserver": package, "unoserver.client": client_module},
        ):
            result = libreoffice_pdf.convert_docx_to_pdf_unoserver(
                docx_bytes=b"PK-docx",
                unoserver_url="http://libreoffice:2003",
                timeout_seconds=2,
            )

        self.assertTrue(result.startswith(b"%PDF"))
        client_class.assert_called_once_with(
            server="libreoffice",
            port="2003",
            host_location="remote",
            protocol="http",
        )
        client_instance.convert.assert_called_once_with(
            indata=b"PK-docx",
            convert_to="pdf",
            update_index=False,
        )

    def test_recusa_url_sem_host(self):
        with self.assertRaisesRegex(RuntimeError, "host válido"):
            libreoffice_pdf.convert_docx_to_pdf_unoserver(
                docx_bytes=b"PK-docx",
                unoserver_url="http://",
            )

    @mock.patch.object(libreoffice_pdf, "unoserver_healthcheck", return_value=True)
    def test_mesmo_host_usa_caminhos_locais(self, _healthcheck):
        client_instance = mock.Mock()

        def converter_local(**kwargs):
            from pathlib import Path

            self.assertTrue(Path(kwargs["inpath"]).read_bytes().startswith(b"PK"))
            Path(kwargs["outpath"]).write_bytes(b"%PDF-1.7\nlocal")

        client_instance.convert.side_effect = converter_local
        client_class = mock.Mock(return_value=client_instance)
        package = ModuleType("unoserver")
        client_module = ModuleType("unoserver.client")
        client_module.UnoClient = client_class

        with mock.patch.dict(
            sys.modules,
            {"unoserver": package, "unoserver.client": client_module},
        ):
            result = libreoffice_pdf.convert_docx_to_pdf_unoserver(
                docx_bytes=b"PK-docx",
                unoserver_url="http://127.0.0.1:2003",
            )

        self.assertEqual(result, b"%PDF-1.7\nlocal")
        client_class.assert_called_once_with(
            server="127.0.0.1",
            port="2003",
            host_location="local",
            protocol="http",
        )

    @mock.patch.object(libreoffice_pdf, "unoserver_healthcheck", return_value=False)
    def test_falha_rapido_quando_servico_esta_indisponivel(self, _healthcheck):
        with self.assertRaisesRegex(RuntimeError, "indisponível"):
            libreoffice_pdf.convert_docx_to_pdf_unoserver(
                docx_bytes=b"PK-docx",
                unoserver_url="http://libreoffice:2003",
                timeout_seconds=0.1,
            )


class UnoserverCheckCommandTests(SimpleTestCase):
    @override_settings(DOCUMENTOS_UNOSERVER_URL="")
    def test_benchmark_sem_url_reprova_em_vez_de_pular_gate(self):
        with self.assertRaisesRegex(CommandError, "não definido"):
            call_command("documentos_unoserver_check", "--benchmark")

    @override_settings(
        DOCUMENTOS_UNOSERVER_URL="http://libreoffice:2003",
        DOCUMENTOS_UNOSERVER_TIMEOUT_SECONDS=2,
    )
    @mock.patch(
        "documentos.management.commands.documentos_unoserver_check.convert_docx_to_pdf_unoserver",
        return_value=b"%PDF-1.7\nok",
    )
    @mock.patch(
        "documentos.management.commands.documentos_unoserver_check.unoserver_healthcheck",
        return_value=True,
    )
    def test_benchmark_aprova_abaixo_do_sla(self, _health, _convert):
        output = StringIO()
        with mock.patch(
            "documentos.management.commands.documentos_unoserver_check.time.perf_counter",
            side_effect=[10.0, 10.4],
        ):
            call_command(
                "documentos_unoserver_check",
                "--benchmark",
                "--max-ms",
                "1000",
                stdout=output,
            )
        self.assertIn("SLA atendido", output.getvalue())
        self.assertIn("sintetico.docx: 400.0 ms", output.getvalue())

    @override_settings(
        DOCUMENTOS_UNOSERVER_URL="http://libreoffice:2003",
        DOCUMENTOS_UNOSERVER_TIMEOUT_SECONDS=2,
    )
    @mock.patch(
        "documentos.management.commands.documentos_unoserver_check.convert_docx_to_pdf_unoserver",
        return_value=b"%PDF-1.7\nslow",
    )
    @mock.patch(
        "documentos.management.commands.documentos_unoserver_check.unoserver_healthcheck",
        return_value=True,
    )
    def test_benchmark_reprova_acima_do_sla(self, _health, _convert):
        with mock.patch(
            "documentos.management.commands.documentos_unoserver_check.time.perf_counter",
            side_effect=[10.0, 11.1],
        ):
            with self.assertRaisesRegex(CommandError, "SLA excedido"):
                call_command(
                    "documentos_unoserver_check",
                    "--benchmark",
                    "--max-ms",
                    "1000",
                )
