"""Gate da paleta de tres cores (NOVO-28).

A regra: o sistema se pinta com tres superficies que se revezam, mais um
acento. Sem este teste a regra derrete — foi o que aconteceu com a camada de
tokens anterior, que virou uma segunda paleta fixa (238 declaracoes literais
em theme.css contra 121 apontando para outro token).

Verificacao estatica de proposito. Medir na tela exigiria navegador no runner
do CI; o instrumento visual e `scripts/medir_paleta.py`, que roda sob demanda
e produz a evidencia de antes/depois. Aqui ficam as invariantes que nao
precisam de navegador e por isso podem ser baratas o bastante para rodar
sempre.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

CSS = Path(settings.BASE_DIR) / "static" / "css"
PALETA = CSS / "00-palette.css"

# As tres superficies e o acento, por tema. Espelha 00-palette.css; se os dois
# divergirem, o teste falha e diz qual.
ESPERADO_CLARO = {
    "--cv-surface-page": "#eceef1",
    "--cv-surface-card": "#ffffff",
    "--cv-surface-block": "#eceef1",
    "--color-accent": "#155b9a",
}
ESPERADO_ESCURO = {
    "--cv-surface-page": "#0d0f11",
    "--cv-surface-card": "#191c1f",
    "--cv-surface-block": "#23272b",
    "--color-accent": "#d8a21b",
}

# Superficies do shell que devem resolver para uma das tres. Quem nao esta aqui
# ou e excecao declarada (estado semantico, botao cheio) ou e divida conhecida,
# listada no plano como PR B/C/D.
SUPERFICIES_DO_SHELL = (
    "--surface-stepper",
    "--surface-form-panel",
    "--surface-form-section",
    "--surface-list-panel",
    "--surface-field-group",
    "--surface-filter-bar",
    "--surface-footer-actions",
    "--cv-form-section-bg",
    "--cv-form-section-header-bg",
)
TRES = {"var(--cv-surface-page)", "var(--cv-surface-card)", "var(--cv-surface-block)"}


def _bloco(texto: str, seletor: str) -> str:
    m = re.search(rf"{re.escape(seletor)}\s*\{{(.*?)\}}", texto, re.S)
    assert m, f"bloco {seletor} nao encontrado em 00-palette.css"
    return m.group(1)


def _declaracoes(bloco: str) -> dict[str, str]:
    return {
        m.group(1): m.group(2).strip()
        for m in re.finditer(r"(--[a-z0-9-]+):\s*([^;]+);", bloco)
    }


class PaletaTresCoresTests(SimpleTestCase):
    def test_as_tres_sementes_e_o_acento_tem_os_valores_decididos(self):
        """Os hex vieram de medicao, nao de gosto — travar impede deriva silenciosa.

        Contraste do texto sobre o card: 18,48 no claro e 15,35 no escuro (WCAG).
        Card x bloco: dE 6,2 e 5,4. Tinta a 15%: dE 11,1 e 18,0.
        """
        texto = PALETA.read_text(encoding="utf-8")
        claro = _declaracoes(_bloco(texto, ":root"))
        escuro = _declaracoes(_bloco(texto, 'html[data-theme="dark"]'))

        for token, valor in ESPERADO_CLARO.items():
            self.assertEqual(claro.get(token), valor, f"{token} no tema claro")
        for token, valor in ESPERADO_ESCURO.items():
            self.assertEqual(escuro.get(token), valor, f"{token} no tema escuro")

    def test_o_par_do_rodizio_comeca_no_fundo_da_pagina(self):
        """A raiz esta pousada no fundo do site e oferece o card ao primeiro filho."""
        claro = _declaracoes(_bloco(PALETA.read_text(encoding="utf-8"), ":root"))
        self.assertEqual(claro.get("--cv-surface"), "var(--cv-surface-page)")
        self.assertEqual(claro.get("--cv-surface-next"), "var(--cv-surface-card)")

    def test_superficies_do_shell_resolvem_para_uma_das_tres(self):
        """Nenhuma superficie do shell inventa cor propria."""
        texto = (CSS / "page-shell.css").read_text(encoding="utf-8")
        fora = []
        for token in SUPERFICIES_DO_SHELL:
            for m in re.finditer(rf"^\s*{re.escape(token)}:\s*([^;]+);", texto, re.M):
                valor = m.group(1).strip()
                if valor not in TRES:
                    fora.append(f"{token}: {valor}")
        self.assertEqual(fora, [], "superficies do shell fora das tres cores")

    def test_os_dois_ancoras_declaram_o_par_invertido(self):
        """O rodizio inteiro depende destas quatro declaracoes.

        Se alguem tirar uma delas, os filhos herdam o par do avo e a alternancia
        para de acontecer — sem erro, so com a tela ficando de uma cor so.
        """
        secoes = (CSS / "components" / "form-sections.css").read_text(encoding="utf-8")
        shell = (CSS / "page-shell.css").read_text(encoding="utf-8")

        bloco = _declaracoes(_bloco(secoes, ".cv-form-block"))
        self.assertEqual(bloco.get("--cv-surface"), "var(--cv-surface-block)")
        self.assertEqual(bloco.get("--cv-surface-next"), "var(--cv-surface-card)")

        aninhado = _declaracoes(_bloco(secoes, ".cv-form-block .cv-form-block"))
        self.assertEqual(aninhado.get("--cv-surface"), "var(--cv-surface-card)")
        self.assertEqual(aninhado.get("--cv-surface-next"), "var(--cv-surface-block)")

        card = _declaracoes(_bloco(shell, ".cv-form-section-card"))
        self.assertEqual(card.get("--cv-surface"), "var(--cv-surface-card)")
        self.assertEqual(card.get("--cv-surface-next"), "var(--cv-surface-block)")

    def test_login_e_assinatura_carregam_a_paleta_depois_do_tema_escuro(self):
        """Ordem importa: os dois arquivos declaram em html[data-theme="dark"].

        As duas paginas ficam fora do bundle global e montam a propria lista de
        <link>. Se a paleta subir antes do tema escuro, o acento novo e ignorado
        no escuro — e o defeito nao aparece no claro, que e onde se costuma olhar.
        """
        base = Path(settings.BASE_DIR) / "templates"
        for rel in ("core/login.html",
                    "prestacoes_contas/assinatura/base_publico.html"):
            with self.subTest(template=rel):
                texto = (base / rel).read_text(encoding="utf-8")
                escuro = texto.find("03-theme-dark.css")
                paleta = texto.find("00-palette.css")
                self.assertNotEqual(paleta, -1, "a pagina nao carrega 00-palette.css")
                self.assertLess(escuro, paleta, "paleta precisa vir depois do tema escuro")

    def test_a_paleta_nao_depende_de_outro_arquivo(self):
        """Login e assinatura puxam so este arquivo; ele nao pode ter dependencia.

        As sementes sao literais aqui — e o unico lugar do sistema onde uma cor
        de superficie pode ser escrita a mao.
        """
        texto = PALETA.read_text(encoding="utf-8")
        self.assertNotIn("@import", texto)
        for bloco, esperado in ((":root", ESPERADO_CLARO),
                                ('html[data-theme="dark"]', ESPERADO_ESCURO)):
            decls = _declaracoes(_bloco(texto, bloco))
            for token in esperado:
                self.assertRegex(
                    decls[token], r"^#[0-9a-f]{6}$",
                    f"{token} em {bloco} precisa ser literal, nao var()",
                )
