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

# As tres superficies, a superficie do menu e os DOIS acentos, por tema.
# Espelha 00-palette.css; se os dois divergirem, o teste falha e diz qual.
#
# NOVO-55 desfez as duas simplificacoes do NOVO-28 que custaram a identidade:
# o grafite neutro voltou a ser MARINHO, e o acento unico voltou a ser um PAR
# — azul para acao, dourado para destaque, nos dois temas. Por isso
# `--color-gold` tem o mesmo valor nas duas linhas abaixo: ele nao acompanha o
# tema, ele marca o mesmo papel nos dois.
ESPERADO_CLARO = {
    "--cv-surface-page": "#eef3f9",
    "--cv-surface-card": "#ffffff",
    "--cv-surface-block": "#f6f9fc",
    "--cv-surface-shell": "#0b3050",
    "--color-accent": "#d8a21b",
    "--color-primary": "#155b9a",
}
ESPERADO_ESCURO = {
    "--cv-surface-page": "#07111d",
    "--cv-surface-card": "#1a2638",
    "--cv-surface-block": "#223348",
    "--cv-surface-shell": "#081827",
    "--color-accent": "#d8a21b",
    # Decisao de 05/08/2026: no escuro a acao tambem e dourada. Ver a nota em
    # 00-palette.css e `test_os_dois_acentos_nao_trocam_de_papel`.
    "--color-primary": "#d8a21b",
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
    # NOVO-29: superficies do rail de filtros e do quick-create entraram junto
    # com a geometria do login.
    "--surface-filter-input",
    "--surface-filter-button",
    "--surface-applied-chip",
    "--surface-quick-create",
    "--surface-quick-create-header",
    "--surface-inline-create-tab",
    "--surface-list-row",
)
TRES = {"var(--cv-surface-page)", "var(--cv-surface-card)", "var(--cv-surface-block)"}

CONTRASTE_MINIMO = 7.0  # WCAG AAA para corpo de texto


def _luminancia(hexa: str) -> float:
    canais = []
    for i in (1, 3, 5):
        c = int(hexa[i:i + 2], 16) / 255
        canais.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = canais
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contraste(a: str, b: str) -> float:
    la, lb = _luminancia(a), _luminancia(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _bloco(texto: str, seletor: str) -> str:
    m = re.search(rf"{re.escape(seletor)}\s*\{{(.*?)\}}", texto, re.S)
    assert m, f"bloco {seletor} nao encontrado"
    return m.group(1)


def _declaracoes(bloco: str) -> dict[str, str]:
    return {
        m.group(1): m.group(2).strip()
        for m in re.finditer(r"(--[a-z0-9-]+):\s*([^;]+);", bloco)
    }


class PaletaTresCoresTests(SimpleTestCase):
    def test_as_tres_sementes_e_o_acento_tem_os_valores_decididos(self):
        """Travar os hex impede deriva silenciosa.

        O contraste real de cada par esta medido em
        `test_o_texto_sobrevive_em_todas_as_superficies`, que calcula em vez de
        repetir um numero de docstring — foi assim que a nota de 18,48 (medida
        sobre card #ffffff) sobreviveu a troca do card para #ebebeb sem que
        nada acusasse.
        """
        texto = PALETA.read_text(encoding="utf-8")
        claro = _declaracoes(_bloco(texto, ":root"))
        escuro = _declaracoes(_bloco(texto, 'html[data-theme="dark"]'))

        for token, valor in ESPERADO_CLARO.items():
            self.assertEqual(claro.get(token), valor, f"{token} no tema claro")
        for token, valor in ESPERADO_ESCURO.items():
            self.assertEqual(escuro.get(token), valor, f"{token} no tema escuro")

    def test_o_texto_sobrevive_em_todas_as_superficies(self):
        """Contraste MEDIDO, nao anotado (NOVO-55).

        Cada tema tem uma tinta e quatro superficies onde texto pousa: pagina,
        card, bloco e menu. O menu usa tinta propria (`--on-shell`), porque a
        do tema claro sumiria nele. AA para corpo de texto e 4,5:1; aqui o
        piso e 7:1 (AAA), que e a folga que o sistema ja tinha.
        """
        texto = PALETA.read_text(encoding="utf-8")
        tokens = (CSS / "01-tokens.css").read_text(encoding="utf-8")
        tintas = {
            ":root": _declaracoes(_bloco(tokens, ":root"))["--cv-ink"],
            'html[data-theme="dark"]': _declaracoes(
                _bloco(tokens, 'html[data-theme="dark"]')
            )["--cv-ink"],
        }
        for seletor, esperado in ((":root", ESPERADO_CLARO),
                                  ('html[data-theme="dark"]', ESPERADO_ESCURO)):
            decls = _declaracoes(_bloco(texto, seletor))
            ink = tintas[seletor]
            for token in ("--cv-surface-page", "--cv-surface-card",
                          "--cv-surface-block"):
                with self.subTest(tema=seletor, superficie=token):
                    razao = _contraste(ink, esperado[token])
                    self.assertGreaterEqual(
                        razao, CONTRASTE_MINIMO,
                        f"{token} em {seletor}: {razao:.2f}:1 com a tinta {ink}",
                    )
            with self.subTest(tema=seletor, superficie="--cv-surface-shell"):
                razao = _contraste(decls["--on-shell"], esperado["--cv-surface-shell"])
                self.assertGreaterEqual(
                    razao, CONTRASTE_MINIMO,
                    f"menu em {seletor}: {razao:.2f}:1",
                )

    def test_os_dois_acentos_nao_trocam_de_papel(self):
        """Azul e acao, dourado e destaque — e nenhum dos dois vira o outro.

        O defeito que isto tranca e concreto: no NOVO-28 havia UM acento que
        trocava de matiz por tema, entao o botao "Novo oficio" — que consome o
        acento como fundo — vinha azul no claro e DOURADO no escuro. Quem le a
        tela aprende que dourado significa "clique"; ai o selo de rascunho,
        tambem dourado, passa a parecer botao.
        """
        texto = PALETA.read_text(encoding="utf-8")
        claro = _declaracoes(_bloco(texto, ":root"))
        escuro = _declaracoes(_bloco(texto, 'html[data-theme="dark"]'))

        self.assertEqual(
            claro["--color-accent"], escuro["--color-accent"],
            "o dourado marca o mesmo papel nos dois temas; nao acompanha o tema",
        )
        # No CLARO os dois papeis tem cores distintas. No ESCURO o produto
        # decidiu colapsar (05/08/2026): la a diferenca entre clicavel e
        # informativo passa a ser a FORMA, nao a cor. O gate registra a
        # assimetria em vez de fingir que ela nao existe — se um dia o claro
        # colapsar tambem, isto aqui reprova e alguem tem de decidir de novo.
        self.assertNotEqual(
            claro["--color-accent"], claro["--color-primary"],
            "no tema claro acao e destaque nao podem colapsar",
        )
        for tema, decls in (("claro", claro), ("escuro", escuro)):
            with self.subTest(tema=tema):
                self.assertGreaterEqual(
                    _contraste(decls["--on-accent"], decls["--color-accent"]),
                    4.5, "texto sobre o dourado cheio reprova em AA",
                )
                self.assertGreaterEqual(
                    _contraste(decls["--on-primary"], decls["--color-primary"]),
                    4.5, "texto sobre o azul cheio reprova em AA",
                )

    def test_o_chrome_e_pintado_so_com_a_superficie_do_menu(self):
        """Menu e faixa de cabecalho sao UMA peca — e o gate mede isso no CSS.

        O defeito e sempre o mesmo e nao aparece em teste de comportamento: a
        faixa redeclara `--cv-ink` para a tinta clara do menu, mas alguem, mais
        adiante e com especificidade maior, repinta o FUNDO de claro. O
        resultado e titulo branco sobre branco — aconteceu tres vezes num dia
        (`.list-header--wizard-band`, justificativas e usuarios), e as tres so
        apareceram no print.
        """
        chrome = ("list-header__band", "page-header-band")
        # `.list-header__band-actions`/`__band-aside` nao sao a faixa.
        seletor_e_corpo = re.compile(r"([^{}]*)\{([^{}]*)\}")
        fundo = re.compile(r"(?:^|;)\s*background(?:-color)?\s*:\s*([^;]+)", re.M)

        fora = []
        for arq in sorted(CSS.rglob("*.css")):
            if arq.name.endswith(".bundle.css") or arq.parent.name == "dev":
                continue
            texto = re.sub(r"/\*.*?\*/", "", arq.read_text(encoding="utf-8"), flags=re.S)
            for regra in seletor_e_corpo.finditer(texto):
                seletor, corpo = regra.group(1), regra.group(2)
                alvo = any(
                    re.search(rf"\.{peca}(?![\w-])", seletor) for peca in chrome
                )
                if not alvo:
                    continue
                for valor in fundo.findall(corpo):
                    valor = valor.strip()
                    if "--cv-surface-shell" in valor or valor in ("transparent", "none"):
                        continue
                    fora.append(
                        f"{arq.relative_to(CSS).as_posix()}: "
                        f"{seletor.strip()[:56]} → {valor[:40]}"
                    )
        self.assertEqual(
            fora, [],
            "faixa de chrome pintada fora de --cv-surface-shell:\n" + "\n".join(fora),
        )

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
        # NOVO-30 fase 3a: as ancoras voltaram para o componente. A camada de
        # token nao pode ancorar rodizio — o par depende de ONDE o elemento
        # esta, nao do tema, e a fase 1 as levou para la junto com o resto.
        secoes = (CSS / "components" / "form-sections.css").read_text(encoding="utf-8")
        shell = secoes

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
                escuro = texto.find("01-tokens.css")
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
