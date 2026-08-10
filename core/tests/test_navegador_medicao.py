"""NOVO-83: as réguas de frontend sobem o Chromium que existe, não o que o pip espera."""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from scripts import navegador_medicao


class ExecutavelInstaladoTests(SimpleTestCase):
    """A resolução do caminho, que é a parte que decide se a régua roda."""

    def _arvore(self, raiz: Path, builds: dict[str, list[str]]) -> None:
        for pasta, arquivos in builds.items():
            for arquivo in arquivos:
                caminho = raiz / pasta / arquivo
                caminho.parent.mkdir(parents=True, exist_ok=True)
                caminho.write_text("#!/bin/sh\n", encoding="utf-8")
                caminho.chmod(0o755)

    def test_sem_a_variavel_de_ambiente_nao_inventa_caminho(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(navegador_medicao.executavel_instalado())

    def test_acha_o_chrome_completo(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            self._arvore(raiz, {"chromium-1194": ["chrome-linux/chrome"]})
            with mock.patch.dict(os.environ, {"PLAYWRIGHT_BROWSERS_PATH": tmp}):
                achado = navegador_medicao.executavel_instalado()
            self.assertEqual(achado, str(raiz / "chromium-1194" / "chrome-linux" / "chrome"))

    def test_prefere_o_build_mais_novo(self):
        """Quando a imagem deixa dois, o mais novo é o que ela pôs por último."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            self._arvore(
                raiz,
                {
                    "chromium-1194": ["chrome-linux/chrome"],
                    "chromium-1300": ["chrome-linux/chrome"],
                },
            )
            with mock.patch.dict(os.environ, {"PLAYWRIGHT_BROWSERS_PATH": tmp}):
                self.assertIn("chromium-1300", navegador_medicao.executavel_instalado())

    def test_diretorio_sem_navegador_devolve_none(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "ffmpeg-1011").mkdir()
            with mock.patch.dict(os.environ, {"PLAYWRIGHT_BROWSERS_PATH": tmp}):
                self.assertIsNone(navegador_medicao.executavel_instalado())


class AbrirChromiumTests(SimpleTestCase):
    """A queda só acontece no erro certo — senão ela esconde defeito de verdade."""

    def test_o_caminho_normal_e_tentado_primeiro(self):
        playwright = mock.Mock()
        navegador_medicao.abrir_chromium(playwright, headless=True)
        playwright.chromium.launch.assert_called_once_with(headless=True)
        # sem executable_path: no CI, `playwright install` já pôs o build certo
        self.assertNotIn("executable_path", playwright.chromium.launch.call_args.kwargs)

    def test_cai_para_o_instalado_quando_o_esperado_nao_existe(self):
        playwright = mock.Mock()
        playwright.chromium.launch.side_effect = [
            Exception("Executable doesn't exist at /opt/pw-browsers/chromium_headless_shell-1234/x"),
            "navegador",
        ]
        with mock.patch.object(
            navegador_medicao, "executavel_instalado", return_value="/opt/pw-browsers/x/chrome"
        ):
            self.assertEqual(navegador_medicao.abrir_chromium(playwright), "navegador")
        self.assertEqual(
            playwright.chromium.launch.call_args.kwargs["executable_path"],
            "/opt/pw-browsers/x/chrome",
        )

    def test_outro_erro_sobe_sem_disfarce(self):
        """Sandbox quebrado, memória, porta — nada disso vira 'navegador ausente'."""
        playwright = mock.Mock()
        playwright.chromium.launch.side_effect = Exception("Target page crashed")
        with mock.patch.object(
            navegador_medicao, "executavel_instalado", return_value="/opt/pw-browsers/x/chrome"
        ):
            with self.assertRaisesMessage(Exception, "Target page crashed"):
                navegador_medicao.abrir_chromium(playwright)

    def test_sem_nada_instalado_o_erro_original_sobe(self):
        playwright = mock.Mock()
        playwright.chromium.launch.side_effect = Exception("Executable doesn't exist at /x")
        with mock.patch.object(navegador_medicao, "executavel_instalado", return_value=None):
            with self.assertRaisesMessage(Exception, "Executable doesn't exist"):
                navegador_medicao.abrir_chromium(playwright)


class AsReguasUsamOAtalhoTests(SimpleTestCase):
    """Trava de regressão: se alguém voltar ao launch cru, a régua para de rodar aqui."""

    ROTAS = ("scripts/medir_divergencia_tema.py", "scripts/medir_css_por_rota.py")

    def test_nenhuma_regua_chama_chromium_launch_direto(self):
        from django.conf import settings

        cruas = []
        for caminho in self.ROTAS:
            texto = (Path(settings.BASE_DIR) / caminho).read_text(encoding="utf-8")
            if "playwright.chromium.launch(" in texto:
                cruas.append(caminho)
            self.assertIn("abrir_chromium", texto, f"{caminho} não usa o atalho")
        self.assertEqual(cruas, [], "voltou ao launch cru — ver NOVO-83")


class EsperarLayoutEstavelTests(SimpleTestCase):
    """NOVO-84: medir só depois que a página para de crescer."""

    def test_o_orcamento_e_repassado_ao_navegador(self):
        from scripts import medir_divergencia_tema as medidor

        pagina = mock.Mock()
        pagina.evaluate.return_value = {"estavel": True, "voltas": 3, "medida": "100x50x100"}
        resultado = medidor._esperar_layout_estavel(pagina, tentativas=7, intervalo_ms=11)

        self.assertTrue(resultado["estavel"])
        _script, argumentos = pagina.evaluate.call_args.args
        self.assertEqual(argumentos, {"tentativas": 7, "intervaloMs": 11})

    def test_o_erro_de_ordem_passa_a_dizer_a_rota_e_se_assentou(self):
        """Antes a mensagem não dizia nem qual rota era — eu tive que deduzir
        contando linhas de log. Agora ela carrega as duas informações que
        separam 'o instrumento falhou' de 'a página não para de mudar'."""
        from scripts import medir_divergencia_tema as medidor

        rota = mock.Mock(slug="roteiros-editar", path="/roteiros/1/editar/", requires_auth=True)
        pagina = mock.Mock()
        pagina.goto.return_value = mock.Mock(status=200)
        pagina.url = "http://127.0.0.1:8000/roteiros/1/editar/"

        with mock.patch.object(medidor, "_disable_motion"), mock.patch.object(
            medidor, "is_valid_final_url", return_value=True
        ), mock.patch.object(
            medidor,
            "_esperar_layout_estavel",
            return_value={"estavel": False, "voltas": 40, "medida": "4423x500x4423"},
        ), mock.patch.object(
            medidor, "_capture_order", return_value={"difference_keys": set()}
        ), mock.patch.object(
            medidor, "_summarize_pair", side_effect=RuntimeError("a ordem de captura alterou")
        ):
            with self.assertRaises(RuntimeError) as caixa:
                medidor._measure_route(pagina, rota, "http://127.0.0.1:8000", 30000)

        mensagem = str(caixa.exception)
        self.assertIn("roteiros-editar", mensagem)
        self.assertIn("layout estável: False", mensagem)
        self.assertIn("4423x500x4423", mensagem)

    def test_a_espera_acontece_antes_da_captura(self):
        """Esperar depois de capturar não serviria de nada."""
        from scripts import medir_divergencia_tema as medidor

        ordem = []
        rota = mock.Mock(slug="x", path="/x/", requires_auth=True)
        pagina = mock.Mock()
        pagina.goto.return_value = mock.Mock(status=200)
        pagina.url = "http://127.0.0.1:8000/x/"

        with mock.patch.object(medidor, "_disable_motion"), mock.patch.object(
            medidor, "is_valid_final_url", return_value=True
        ), mock.patch.object(
            medidor,
            "_esperar_layout_estavel",
            side_effect=lambda *a, **k: (ordem.append("espera"), {"estavel": True, "medida": "1x1x1"})[1],
        ), mock.patch.object(
            medidor,
            "_capture_order",
            side_effect=lambda *a, **k: (ordem.append("captura"), {"difference_keys": set()})[1],
        ), mock.patch.object(
            medidor, "_summarize_pair", return_value={}
        ):
            medidor._measure_route(pagina, rota, "http://127.0.0.1:8000", 30000)

        self.assertEqual(ordem[0], "espera")
        self.assertEqual(ordem.count("captura"), 2)
