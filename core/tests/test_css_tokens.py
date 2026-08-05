"""Gate de CI da Etapa 7 fase 14 — tokens CSS e classes canônicas.

1. Literais de cor (hex, rgb, rgba) só em arquivos de token/tema autorizados.
2. Classes canônicas emitidas por templates críticos têm definição no bundle CSS.
"""

from __future__ import annotations

import collections
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)
CSS_DIR = ROOT / "static" / "css"

# Mesma política de exceção do audit_frontend_standards.py (Etapa 7 gate).
COLOR_LITERAL_ALLOWED = {
    "static/css/00-palette.css",
    "static/css/01-tokens.css",
    "static/css/shell.bundle.css",  # gerado (NOVO-12); literais vêm das fontes acima
}

_HEX_COLOR = re.compile(r"(?<![\w#])#([0-9a-fA-F]{3,8})\b")
_RGB_COLOR = re.compile(r"\brgba?\(\s*[\d.%]+")
_CSS_COMMENT = re.compile(r"/\*.*?\*/")
_CSS_VALUE = re.compile(r":\s*.+")

# Arquivos novos da fase 13 — devem estar 100% livres de literais.
STRICT_COLOR_LITERAL_FILES = {
    "static/css/components/cv-notice.css",
    "static/css/components/cv-metric.css",
}

# Baseline medido em 30/07/2026 antes da fase 14; o gate falha se a dívida subir.
# 660 -> 620 no NOVO-28: a paleta de tres cores tokenizou o login e a
# assinatura publica por inteiro (os dois sairam com ZERO literal). O numero
# so desce (AGENTS.md, regra 5).
COLOR_LITERAL_BASELINE = 620

# Escala fechada R-01 — espelha a camada canônica em static/css/01-tokens.css.
ALLOWED_MEDIA_BREAKPOINTS = frozenset({
    420, 520, 600, 640, 720, 721, 768, 800, 820, 840, 841, 900,
    1080, 1180, 1181, 1400, 1480,
})

_MEDIA_BLOCK = re.compile(r"@media\s+([^{]+)\{", re.IGNORECASE)
_MEDIA_WIDTH = re.compile(r"(?:min|max)-width:\s*(\d+)px", re.IGNORECASE)

# Templates de alto tráfego + componentes globais que já emitem cv-notice / cv-metric.
CRITICAL_CANONICAL_CLASSES = {
    "cv-notice",
    "cv-notice--info",
    "cv-notice--success",
    "cv-notice--warning",
    "cv-notice--danger",
    "cv-notice-stack",
    "cv-metric",
    "cv-metric--tile",
    "cv-metric-grid",
    "cv-metric-grid--4",
}


def _rel_css(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _strip_comments(line: str) -> str:
    return _CSS_COMMENT.sub("", line)


def _find_color_literals(path: Path) -> list[tuple[int, str]]:
    rel = _rel_css(path)
    if rel in COLOR_LITERAL_ALLOWED:
        return []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        lines = path.read_text(encoding="latin-1").splitlines()

    findings: list[tuple[int, str]] = []
    for idx, raw in enumerate(lines, start=1):
        line = _strip_comments(raw)
        if not _CSS_VALUE.search(line):
            continue
        if _HEX_COLOR.search(line) or _RGB_COLOR.search(line):
            findings.append((idx, raw.strip()))
    return findings


def _find_media_width_violations() -> list[str]:
    violations: list[str] = []
    for path in sorted(CSS_DIR.rglob("*.css")):
        if path.name.endswith(".bundle.css"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1")
        rel = _rel_css(path)
        for block in _MEDIA_BLOCK.finditer(text):
            prelude = block.group(1)
            for match in _MEDIA_WIDTH.finditer(prelude):
                value = int(match.group(1))
                if value not in ALLOWED_MEDIA_BREAKPOINTS:
                    violations.append(f"{rel}: {value}px")
    return violations


def _count_all_color_literal_violations() -> list[str]:
    violations: list[str] = []
    for path in sorted(CSS_DIR.rglob("*.css")):
        if path.name.endswith(".bundle.css"):
            continue
        for line_no, snippet in _find_color_literals(path):
            violations.append(f"{_rel_css(path)}:{line_no}: {snippet}")
    return violations


def _css_bundle_text() -> str:
    parts: list[str] = []
    for path in sorted(CSS_DIR.rglob("*.css")):
        if path.name.endswith(".bundle.css"):
            continue
        try:
            parts.append(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            parts.append(path.read_text(encoding="latin-1"))
    return "\n".join(parts)


class CssTokenGateTests(SimpleTestCase):
    def test_canonical_component_stylesheets_have_no_color_literals(self):
        """Novos componentes cv-notice/cv-metric devem usar apenas var() de token."""
        violations: list[str] = []
        for rel in sorted(STRICT_COLOR_LITERAL_FILES):
            path = ROOT / rel
            for line_no, snippet in _find_color_literals(path):
                violations.append(f"{rel}:{line_no}: {snippet}")

        self.assertEqual(violations, [], "\n".join(violations))

    def test_media_breakpoints_use_closed_scale(self):
        """Gate R-01: @media width usa somente a escala documentada em 01-tokens.css."""
        violations = _find_media_width_violations()
        self.assertEqual(
            violations,
            [],
            "Breakpoints fora da escala fechada R-01:\n" + "\n".join(violations[:20]),
        )

    def test_color_literal_debt_does_not_exceed_baseline(self):
        """Gate Etapa 7: hex/rgb fora de tokens — dívida existente não pode aumentar."""
        violations = _count_all_color_literal_violations()
        self.assertLessEqual(
            len(violations),
            COLOR_LITERAL_BASELINE,
            f"Dívida de literais de cor subiu para {len(violations)} "
            f"(baseline {COLOR_LITERAL_BASELINE}). "
            f"Novos: {violations[COLOR_LITERAL_BASELINE:COLOR_LITERAL_BASELINE + 5]}",
        )

    def test_critical_canonical_classes_have_css_definitions(self):
        """Gate leve: classes cv-notice/cv-metric usadas em templates críticos existem no CSS."""
        bundle = _css_bundle_text()
        missing: list[str] = []
        for class_name in sorted(CRITICAL_CANONICAL_CLASSES):
            if not re.search(rf"\.{re.escape(class_name)}\b", bundle):
                missing.append(class_name)

        self.assertEqual(
            missing,
            [],
            f"Classes canônicas sem definição CSS: {', '.join(missing)}",
        )

    def test_critical_templates_emit_canonical_notice_and_metric_classes(self):
        """Templates migrados na fase 13 emitem cv-notice / cv-metric como classe primária."""
        expectations = {
            "templates/components/ui/feedback/alert.html": ("cv-notice", "cv-notice--"),
            "templates/components/feedback/alerts.html": ("cv-notice-stack", "cv-notice"),
            "templates/components/cards/summary_card.html": ("cv-metric", "cv-metric--tile"),
            "templates/core/dashboard.html": ("cv-metric-grid",),
        }
        for rel_path, tokens in expectations.items():
            text = (ROOT / rel_path).read_text(encoding="utf-8")
            for token in tokens:
                with self.subTest(template=rel_path, token=token):
                    self.assertIn(token, text)

    def test_base_html_links_shell_bundle_with_notice_and_metric(self):
        """NOVO-12: o shell entrega um CSS; notice/metric entram via bundle gerado."""
        base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertIn("css/shell.bundle.css", base)
        self.assertNotIn("css/components/cv-notice.css", base)
        self.assertNotIn("css/components/cv-metric.css", base)
        bundle = (ROOT / "static" / "css" / "shell.bundle.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(">>> css/components/cv-notice.css >>>", bundle)
        self.assertIn(">>> css/components/cv-metric.css >>>", bundle)


# ===========================================================================
# NOVO-30 fase 3a — a camada unica de token
#
# POR QUE ESTES GATES EXISTEM
#
# O gate da fase 1 contava token declarado FORA da camada, e dava zero. Nunca
# olhou para dentro: `01-tokens.css` chegou na fase 3 com 1.034 nomes distintos
# em 2.078 declaracoes, 88 blocos de regra de componente, duas copias literais
# do mesmo bloco e linhas de 11.959 caracteres — exatamente o artefato que a
# §6 do AGENTS.md descreve como reprovado. Medir o lado errado e o defeito;
# esta bateria mede o lado certo (NOVO-31).
# ===========================================================================

TETO_DE_TOKENS = 60

# Prefixo `--_` marca variavel PRIVADA de componente (declarada e consumida no
# mesmo arquivo). Nao e token de design e nao entra na contagem — mas tambem
# nao pode aparecer na camada, senao vira alias com outro nome.
_DECL_TOKEN = re.compile(r"(?:^|[{;])\s*(--[a-zA-Z0-9_-]+)\s*:\s*([^;}]*)", re.M)
CAMADA_DE_TOKEN = {"00-palette.css", "01-tokens.css"}

# Familia de token x propriedade que pode consumi-la. `padding: var(--sh-lg)` e
# sintaticamente valido: o navegador descarta a declaracao e o card fica sem
# respiro, sem quebrar teste nenhum. Foi assim que um token de padding guardado
# como `12px 16px 12px 32px` virou sombra na consolidacao.
FAMILIA_EXCLUSIVA = {
    "--sh-": ("box-shadow", "filter", "backdrop-filter", "text-shadow"),
    "--tr-": ("transition", "animation"),
    "--z-": ("z-index",),
}
# `border-radius` tem "border" no nome e e medida, nao cor: a checagem e por
# nome inteiro, nao por pedaco.
PROPS_DE_COR = frozenset({
    "color", "background", "background-color", "background-image", "border-color",
    "border-top-color", "border-right-color", "border-bottom-color",
    "border-left-color", "outline-color", "fill", "stroke", "caret-color",
    "accent-color", "text-decoration-color", "scrollbar-color",
})
PROPS_DE_MEDIDA = frozenset({
    "padding", "margin", "gap", "row-gap", "column-gap", "width", "height",
    "min-width", "min-height", "max-width", "max-height", "font-size", "z-index",
    "border-radius", "inset", "top", "right", "bottom", "left", "flex-basis",
    "border-width", "letter-spacing", "line-height",
})
FAMILIAS_DE_MEDIDA = ("--sp-", "--r-", "--h-", "--fs-", "--fw-")
FAMILIAS_DE_COR = (
    "--cv-ink", "--cv-border", "--cv-state", "--cv-surface", "--color-accent",
    "--on-accent", "--focus-ring", "--accent-tint",
)


_COMENTARIO = re.compile(r"/\*.*?\*/", re.S)


def _css_fontes() -> list[Path]:
    return [f for f in sorted(CSS_DIR.rglob("*.css")) if f.name != "shell.bundle.css"]


def _declaracoes(texto: str) -> list[tuple[str, str]]:
    return _DECL_TOKEN.findall(_COMENTARIO.sub("", texto))


class CamadaUnicaDeTokenTests(SimpleTestCase):
    def test_o_vocabulario_inteiro_cabe_no_teto(self):
        """Contando TODAS as declaracoes, nao so as que comecam a linha.

        A fase 1 usou `^\\s*--nome:` e por isso um `:root {--a: 1;--b: 2;...}`
        de 3.902 caracteres numa linha so contava como um token.
        """
        nomes = set()
        for arquivo in _css_fontes():
            for nome, _valor in _declaracoes(arquivo.read_text(encoding="utf-8")):
                if not nome.startswith("--_"):
                    nomes.add(nome)
        self.assertLessEqual(
            len(nomes),
            TETO_DE_TOKENS,
            f"{len(nomes)} tokens declarados (teto {TETO_DE_TOKENS}): {sorted(nomes)}",
        )

    def test_nome_novo_de_token_so_nasce_na_camada(self):
        """Componente pode REDECLARAR um token canonico num contexto — e assim que
        o rodizio de superficies funciona — mas nao pode inventar nome."""
        da_camada = set()
        for nome_arquivo in CAMADA_DE_TOKEN:
            for nome, _v in _declaracoes((CSS_DIR / nome_arquivo).read_text(encoding="utf-8")):
                da_camada.add(nome)

        inventados = []
        for arquivo in _css_fontes():
            if arquivo.name in CAMADA_DE_TOKEN:
                continue
            for nome, _v in _declaracoes(arquivo.read_text(encoding="utf-8")):
                if nome.startswith("--_") or nome in da_camada:
                    continue
                inventados.append(f"{_rel_css(arquivo)}: {nome}")
        self.assertEqual(inventados, [], f"token fora da camada unica: {inventados[:10]}")

    def test_a_camada_nao_estiliza_componente(self):
        """So `:root` e `html[data-theme="dark"]`. Regra de componente ali dentro
        foi como a fase 2 zerou o contador de `data-theme` sem dissolver nada."""
        for nome_arquivo in sorted(CAMADA_DE_TOKEN):
            texto = _COMENTARIO.sub("", (CSS_DIR / nome_arquivo).read_text(encoding="utf-8"))
            seletores = [s.strip() for s in re.findall(r"(?:^|\})\s*([^{}@]+?)\s*\{", texto)]
            fora = [s for s in seletores if s not in (":root", 'html[data-theme="dark"]')]
            with self.subTest(arquivo=nome_arquivo):
                self.assertEqual(fora, [], f"{nome_arquivo} estilizando componente: {fora}")

    def test_a_camada_e_legivel(self):
        """Linha minificada esconde token do olho e do gate por linha."""
        for nome_arquivo in sorted(CAMADA_DE_TOKEN):
            texto = (CSS_DIR / nome_arquivo).read_text(encoding="utf-8")
            longas = [i for i, linha in enumerate(texto.splitlines(), 1) if len(linha) > 200]
            with self.subTest(arquivo=nome_arquivo):
                self.assertEqual(longas, [], f"{nome_arquivo}: linhas > 200 chars {longas}")

    def test_nenhuma_referencia_aponta_para_token_inexistente(self):
        declarados = set()
        for arquivo in _css_fontes():
            declarados.update(nome for nome, _v in _declaracoes(arquivo.read_text(encoding="utf-8")))

        orfas = []
        for arquivo in _css_fontes():
            texto = _COMENTARIO.sub("", arquivo.read_text(encoding="utf-8"))
            for nome in re.findall(r"var\(\s*(--[a-zA-Z0-9_-]+)\s*[,)]", texto):
                if nome not in declarados:
                    orfas.append(f"{_rel_css(arquivo)}: {nome}")
        self.assertEqual(orfas, [], f"var() sem token: {sorted(set(orfas))[:10]}")

    def test_cada_familia_de_token_so_cabe_onde_faz_sentido(self):
        fora = []
        for arquivo in _css_fontes():
            texto = _COMENTARIO.sub("", arquivo.read_text(encoding="utf-8"))
            for corpo in re.findall(r"\{([^{}]*)\}", texto):
                for declaracao in corpo.split(";"):
                    if ":" not in declaracao:
                        continue
                    prop, valor = declaracao.split(":", 1)
                    prop = prop.strip()
                    if prop.startswith("--"):
                        continue
                    sozinho = re.fullmatch(r"\s*var\(\s*(--[a-zA-Z0-9_-]+)\s*\)\s*", valor)
                    for nome in re.findall(r"var\(\s*(--[a-zA-Z0-9_-]+)", valor):
                        for prefixo, permitidas in FAMILIA_EXCLUSIVA.items():
                            if nome.startswith(prefixo) and prop not in permitidas:
                                fora.append(f"{_rel_css(arquivo)}: {prop}: var({nome})")
                    if not sozinho:
                        continue
                    nome = sozinho.group(1)
                    if nome.startswith(FAMILIAS_DE_MEDIDA) and prop in PROPS_DE_COR:
                        fora.append(f"{_rel_css(arquivo)}: {prop}: var({nome}) — medida como cor")
                    if nome.startswith(FAMILIAS_DE_COR) and prop in PROPS_DE_MEDIDA:
                        fora.append(f"{_rel_css(arquivo)}: {prop}: var({nome}) — cor como medida")
        self.assertEqual(fora, [], f"token na propriedade errada: {sorted(set(fora))[:10]}")


# ===========================================================================
# NOVO-30 fase 3b — geometria na escada fechada
#
# O gate do prompt media so a forma curta (`padding:`, `border:`,
# `border-radius:`). `padding-inline`, `border-color` e
# `border-start-start-radius` passavam por baixo dele — dava para zerar o
# contador empurrando o valor para a forma longa, com a suite verde e o
# objetivo intacto. Este mede as duas: teto de string na curta, escada fechada
# em toda forma longa.
# ===========================================================================

TETO_DA_FORMA_CURTA = {
    "border-radius": 6,
    "padding": 8,
    "margin": 8,
    "border": 3,
}

# Tudo que uma medida de geometria pode valer, em qualquer forma.
_ESCADA = re.compile(
    r"var\(--(?:sp-[1-8]|r-(?:sm|md|lg|xl|pill)|bd|bd-strong|h-(?:sm|md|lg))\)"
)
_NEUTROS = frozenset({
    "0", "auto", "inherit", "initial", "unset", "revert", "none", "transparent",
    "currentColor", "solid", "dashed", "dotted", "double", "hidden",
})
# Funcao (calc/clamp/color-mix/env) e cor sao conferidas por outros gates; aqui
# so interessa comprimento solto.
_FUNCAO = ("calc(", "clamp(", "min(", "max(", "env(", "color-mix(", "rgba(", "rgb(", "var(")

_PROPS_LONGAS = re.compile(
    r"^(?:padding|margin)(?:-(?:block|inline)(?:-(?:start|end))?|-(?:top|right|bottom|left))$"
    r"|^border-(?:start|end)-(?:start|end)-radius$"
    r"|^border-(?:top|bottom)-(?:left|right)-radius$"
    r"|^border(?:-(?:block|inline))?(?:-(?:start|end|top|right|bottom|left))?$"
)


def _componentes(valor):
    """Componentes de topo do valor, respeitando parenteses."""
    out, atual, prof = [], "", 0
    for c in valor:
        if c == "(":
            prof += 1
        elif c == ")":
            prof -= 1
        if c.isspace() and prof == 0:
            if atual:
                out.append(atual)
                atual = ""
            continue
        atual += c
    if atual:
        out.append(atual)
    return out


def _declaracoes_css(texto):
    """(prop, valor) de cada declaracao, sem comentario."""
    limpo = _COMENTARIO.sub("", texto)
    for corpo in re.findall(r"\{([^{}]*)\}", limpo):
        for pedaco in corpo.split(";"):
            if ":" not in pedaco:
                continue
            prop, _, valor = pedaco.partition(":")
            prop = prop.strip()
            if re.fullmatch(r"-{0,2}[a-zA-Z][-a-zA-Z0-9]*", prop):
                yield prop, " ".join(valor.replace("!important", "").split())


class EscadaDeGeometriaTests(SimpleTestCase):
    """A escala e fechada: seis raios, oito espacos, tres bordas."""

    def test_forma_curta_nao_passa_do_teto(self):
        """`!important` sai antes de contar: ele e alvo da fase 4, nao desta."""
        vistos = {prop: set() for prop in TETO_DA_FORMA_CURTA}
        for arquivo in _css_fontes():
            for prop, valor in _declaracoes_css(arquivo.read_text(encoding="utf-8")):
                if prop in vistos:
                    vistos[prop].add(valor)
        for prop, teto in TETO_DA_FORMA_CURTA.items():
            with self.subTest(prop=prop):
                self.assertLessEqual(
                    len(vistos[prop]), teto,
                    f"{prop}: {len(vistos[prop])} valores distintos (teto {teto}) "
                    f"— {sorted(vistos[prop])}",
                )

    def test_forma_longa_tambem_vem_da_escada(self):
        """Sem isto, `padding-inline: 13px` zeraria o contador da forma curta."""
        fora = []
        for arquivo in _css_fontes():
            for prop, valor in _declaracoes_css(arquivo.read_text(encoding="utf-8")):
                if not _PROPS_LONGAS.fullmatch(prop):
                    continue
                for c in _componentes(valor):
                    if c in _NEUTROS or _ESCADA.fullmatch(c) or c.startswith(_FUNCAO):
                        continue
                    fora.append(f"{_rel_css(arquivo)}: {prop}: {c}")
        self.assertEqual(
            fora, [],
            f"comprimento fora da escada fechada: {sorted(set(fora))[:12]}",
        )


# ===========================================================================
# NOVO-30 fase 3c — uma sombra so, e nenhum foco
#
# DECISAO DE PRODUTO (04/08/2026), com a consequencia escrita:
#   1. Elevacao tem UM degrau, minimo. O que se destaca do fundo se destaca
#      pela superficie da paleta e pela borda.
#   2. O sistema NAO sinaliza foco — nem anel, nem halo, nem contorno.
#      Isto e falha de WCAG 2.4.7 (Focus Visible): quem navega por teclado
#      perde a unica pista de onde esta. Esta travado por teste para nao
#      voltar por acidente, nao porque seja boa pratica.
# ===========================================================================

SOMBRAS_PERMITIDAS = frozenset({"var(--sh-sm)", "none"})
_REGRA_DE_FOCO = re.compile(r":focus(?:-visible|-within)?\b")


class SombraEFocoTests(SimpleTestCase):
    def test_existe_uma_sombra_so(self):
        vistas = collections.Counter()
        for arquivo in _css_fontes():
            for prop, valor in _declaracoes_css(arquivo.read_text(encoding="utf-8")):
                if prop in ("box-shadow", "-webkit-box-shadow"):
                    vistas[valor] += 1
        self.assertEqual(
            set(vistas) - SOMBRAS_PERMITIDAS, set(),
            f"sombra fora do degrau unico: {sorted(set(vistas) - SOMBRAS_PERMITIDAS)[:8]}",
        )

    def test_a_camada_declara_um_degrau_de_elevacao(self):
        tokens = (CSS_DIR / "01-tokens.css").read_text(encoding="utf-8")
        self.assertIn("--sh-sm:", tokens)
        for morto in ("--sh-md:", "--sh-lg:", "--focus-ring:"):
            with self.subTest(token=morto):
                self.assertNotIn(morto, tokens)

    def test_nenhuma_regra_sinaliza_foco(self):
        """O contorno padrao do navegador tambem conta — dai o reset global."""
        acusados = []
        for arquivo in _css_fontes():
            texto = _COMENTARIO.sub("", arquivo.read_text(encoding="utf-8"))
            for seletor, corpo in re.findall(r"([^{}]+)\{([^{}]*)\}", texto):
                if not _REGRA_DE_FOCO.search(seletor):
                    continue
                for pedaco in corpo.split(";"):
                    if ":" not in pedaco:
                        continue
                    prop, _, valor = pedaco.partition(":")
                    prop, valor = prop.strip(), " ".join(valor.split())
                    if prop in ("box-shadow", "-webkit-box-shadow") and valor not in ("none", ""):
                        acusados.append(f"{_rel_css(arquivo)}: {seletor.strip()[:40]} — {prop}")
                    if prop.startswith("outline") and valor.replace("!important", "").strip() not in ("none", "0", ""):
                        acusados.append(f"{_rel_css(arquivo)}: {seletor.strip()[:40]} — {prop}: {valor}")
        self.assertEqual(acusados, [], f"indicador de foco de volta: {acusados[:8]}")

    def test_o_reset_global_de_foco_existe(self):
        base = (CSS_DIR / "base.css").read_text(encoding="utf-8")
        bloco = base.split(":focus,", 1)
        self.assertEqual(len(bloco), 2, "base.css sem o reset global de foco")
        self.assertIn("outline: none", bloco[1].split("}", 1)[0])


# ===========================================================================
# NOVO-30 fase 4 — `!important` so onde ele vence alguem de fora
#
# COMO O NUMERO FOI DECIDIDO
#
# Nao por estimativa: por medicao. `scripts/medir_estilos.py` capturou o
# `getComputedStyle` de 1.488 elementos (5 telas x 2 temas, 24 propriedades),
# os 474 `!important` foram removidos e a captura refeita. Os 456 cosmeticos
# mudaram ZERO propriedade computada — venciam adversarios que a fase 2 e a 3a
# ja tinham dissolvido. Os 18 estruturais ficaram porque escondem/mostram, e a
# medicao das 5 telas nao alcanca wizard, modal e editor: apagar ali seria
# risco que o instrumento nao ve.
# ===========================================================================

TETO_DE_IMPORTANT = 18


class ImportantTests(SimpleTestCase):
    def test_important_nao_passa_do_teto(self):
        total = 0
        for arquivo in _css_fontes():
            for _prop, valor in _declaracoes_css(arquivo.read_text(encoding="utf-8")):
                pass
            total += _COMENTARIO.sub("", arquivo.read_text(encoding="utf-8")).count("!important")
        self.assertLessEqual(
            total, TETO_DE_IMPORTANT,
            f"{total} `!important` (teto {TETO_DE_IMPORTANT}) — o numero so desce",
        )

    def test_cada_important_diz_quem_ele_vence(self):
        """Sem justificativa escrita, o `!important` nao entra.

        E a exigencia do prompt da fase 4: quem sobra tem de nomear a regra de
        terceiro que esta vencendo. Se nao esta vencendo nada de fora, e para
        apagar — nao para documentar.
        """
        sem_motivo = []
        for arquivo in _css_fontes():
            texto = arquivo.read_text(encoding="utf-8")
            for numero, linha in enumerate(texto.splitlines(), 1):
                if "!important" not in linha or linha.strip().startswith(("/*", "*")):
                    continue
                vizinhanca = "\n".join(texto.splitlines()[max(0, numero - 4):numero])
                if "/*" not in vizinhanca:
                    sem_motivo.append(f"{_rel_css(arquivo)}:{numero}")
        self.assertEqual(
            sem_motivo, [],
            f"`!important` sem dizer quem ele vence: {sem_motivo[:8]}",
        )

    def test_o_auditor_nao_tem_excecao_de_arquivo(self):
        """A camada de token virou parte da REGRA, nao uma dispensa."""
        auditor = (ROOT / "scripts" / "audit_frontend_standards.py").read_text(encoding="utf-8")
        inicio = auditor.index("CSS_EXCEPTIONS: dict[str, dict] = {")
        corpo = auditor[inicio:auditor.index("\n}\n", inicio)]
        arquivos = re.findall(r'"(static/css/[^"]+)":', corpo)
        self.assertEqual(
            [a for a in arquivos if not a.endswith("shell.bundle.css")], [],
            "excecao de arquivo de volta no auditor de frontend",
        )


class CssMortoRatchetTests(SimpleTestCase):
    """Teto de regras de CSS sem consumidor (NOVO-37).

    O criterio esta em `scripts/audit_css_morto.py`. O teto e a divida MEDIDA,
    nao zero: a fase 5a ja cortou 5.404 linhas e sobraram 314 regras que aquela
    varredura nao alcancava — `@media` aninhado, e o que so o parser deste
    auditor enxerga. Cortar essas 314 e um PR proprio, com medicao propria;
    aqui a catraca so impede que o numero suba.
    """

    TETO = 314

    def test_o_css_sem_consumidor_nao_cresce(self):
        import importlib.util

        caminho = ROOT / "scripts" / "audit_css_morto.py"
        spec = importlib.util.spec_from_file_location("audit_css_morto", caminho)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        alvo, mortas = modulo.analisa()
        total = sum(len(v) for v in alvo.values())
        detalhe = sorted(
            ((len(f), str(a.relative_to(ROOT))) for a, f in alvo.items()), reverse=True)
        self.assertLessEqual(
            total, self.TETO,
            f"CSS sem consumidor subiu para {total} ({len(mortas)} classes): "
            f"{detalhe[:6]}",
        )
