import sys
from io import StringIO
from pathlib import Path
from types import ModuleType
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.cache import cache
from django.conf import settings
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


class UnoserverCheckPartidaAFrioTests(SimpleTestCase):
    """Dois orçamentos, porque são dois custos diferentes.

    A primeira conversão paga o start do LibreOffice/UNO e custa uma ordem de
    grandeza a mais que as seguintes. Medido no CI em 29/07/2026:
    `ordem_servico.docx: 1119.4 ms, 96.7 ms, 93.2 ms`. Com um `max` só, o gate
    reprovava por aquecimento e não dizia nada sobre o regime estável — foram
    três reprovações seguidas, inclusive no `main`.

    Jogar a primeira medição fora seria a saída fácil e esconderia um custo
    real: quem gera o primeiro documento depois de um período ocioso espera
    aquele 1,1 s. Por isso ela continua vigiada, com limite próprio.
    """

    settings_do_gate = dict(
        DOCUMENTOS_UNOSERVER_URL="http://libreoffice:2003",
        DOCUMENTOS_UNOSERVER_TIMEOUT_SECONDS=2,
    )

    def _rodar(self, marcas, *args):
        """`marcas` são pares (início, fim) em segundos, um por conversão."""
        instantes = [valor for par in marcas for valor in par]
        saida = StringIO()
        with override_settings(**self.settings_do_gate):
            with mock.patch(
                "documentos.management.commands.documentos_unoserver_check."
                "unoserver_healthcheck",
                return_value=True,
            ), mock.patch(
                "documentos.management.commands.documentos_unoserver_check."
                "convert_docx_to_pdf_unoserver",
                return_value=b"%PDF-1.7\nok",
            ), mock.patch(
                "documentos.management.commands.documentos_unoserver_check."
                "time.perf_counter",
                side_effect=instantes,
            ):
                call_command(
                    "documentos_unoserver_check",
                    "--benchmark",
                    "--iterations",
                    str(len(marcas)),
                    *args,
                    stdout=saida,
                )
        return saida.getvalue()

    # 1119 ms a frio, 96 e 93 ms depois — os números reais do CI.
    MARCAS_DO_CI = [(10.0, 11.1194), (12.0, 12.0967), (13.0, 13.0932)]

    def test_o_caso_que_reprovava_no_ci_agora_passa(self):
        saida = self._rodar(
            self.MARCAS_DO_CI, "--max-ms", "1000", "--max-cold-ms", "1500"
        )

        self.assertIn("SLA atendido", saida)
        self.assertIn("primeira conversão (a frio)", saida)

    def test_a_partida_a_frio_continua_vigiada(self):
        """O ponto do orçamento separado: ele ainda reprova quando estoura."""
        with self.assertRaisesRegex(CommandError, "SLA de partida a frio excedido"):
            self._rodar(
                self.MARCAS_DO_CI, "--max-ms", "1000", "--max-cold-ms", "1000"
            )

    def test_regressao_no_regime_estavel_reprova_mesmo_com_partida_boa(self):
        """Aquecimento rápido não pode servir de disfarce para o resto lento."""
        marcas = [(10.0, 10.1), (12.0, 13.2), (14.0, 15.3)]

        with self.assertRaisesRegex(CommandError, "SLA excedido"):
            self._rodar(marcas, "--max-ms", "1000", "--max-cold-ms", "1500")

    def test_um_pico_isolado_nao_anula_toda_a_esteira(self):
        """NOVO-43: a mediana quente distingue cauda de regressão sustentada."""
        marcas = [(10.0, 10.1), (12.0, 12.1), (14.0, 16.0), (17.0, 17.1)]

        saida = self._rodar(marcas, "--max-ms", "1000", "--max-cold-ms", "1500")

        self.assertIn("mediana quente 100.0 ms", saida)

    def test_limite_por_recurso_e_aplicado_ao_recurso_certo(self):
        marcas = [(10.0, 10.1), (12.0, 12.4), (14.0, 14.4), (16.0, 16.4)]

        with self.assertRaisesRegex(CommandError, "sintetico.docx.*350 ms"):
            self._rodar(
                marcas,
                "--max-ms",
                "1000",
                "--max-cold-ms",
                "1500",
                "--max-ms-resource",
                "sintetico.docx=350",
            )

    def test_limite_de_recurso_que_nao_foi_medido_reprova(self):
        with self.assertRaisesRegex(CommandError, "recurso não medido: ausente.xlsx"):
            self._rodar(
                self.MARCAS_DO_CI,
                "--max-ms-resource",
                "ausente.xlsx=750",
                "--max-cold-ms",
                "1500",
            )

    def test_valor_igual_ao_limite_nao_reprova(self):
        marcas = [(10.0, 10.1), (12.0, 12.4), (14.0, 14.4), (16.0, 16.4)]

        saida = self._rodar(
            marcas,
            "--max-ms-resource",
            "sintetico.docx=400",
            "--max-cold-ms",
            "100",
        )

        self.assertIn("SLA atendido", saida)

    def test_sem_o_argumento_o_comportamento_antigo_e_preservado(self):
        """Quem chamar sem `--max-cold-ms` segue com um limite só, como antes."""
        with self.assertRaisesRegex(CommandError, "SLA excedido"):
            self._rodar(self.MARCAS_DO_CI, "--max-ms", "1000")

    def test_uma_iteracao_so_mede_a_propria_partida_a_frio(self):
        """Com `--iterations 1` não há regime estável: a única medida vale pelos dois."""
        with self.assertRaisesRegex(CommandError, "SLA excedido"):
            self._rodar([(10.0, 11.1194)], "--max-ms", "1000", "--max-cold-ms", "1500")

    def test_ci_usa_mediana_por_modelo_depois_da_suite_e_publica_log(self):
        workflow = (Path(settings.BASE_DIR) / ".github/workflows/tests.yml").read_text(
            encoding="utf-8"
        )
        suite = workflow.index("Run complete Django test suite with coverage on PostgreSQL")
        gate = workflow.index("Enforce real document generation SLA (NOVO-43)")

        self.assertLess(suite, gate)
        self.assertIn("--iterations 4", workflow[gate:])
        self.assertIn("ordem_servico_modelos.docx=250", workflow[gate:])
        self.assertIn("diario_bordo.xlsx=750", workflow[gate:])
        self.assertIn("Publish unoserver diagnostic (NOVO-43)", workflow[gate:])
