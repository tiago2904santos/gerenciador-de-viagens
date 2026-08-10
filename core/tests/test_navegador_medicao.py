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
