"""Gate de CI da Etapa 7 fase 14 — tokens CSS e classes canônicas.

1. Literais de cor (hex, rgb, rgba) só em arquivos de token/tema autorizados.
2. Classes canônicas emitidas por templates críticos têm definição no bundle CSS.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)
CSS_DIR = ROOT / "static" / "css"


def _is_generated_css(path: Path) -> bool:
    return path.name.endswith(".bundle.css") or path.parent == CSS_DIR / "profiles"

# Mesma política de exceção do audit_frontend_standards.py (Etapa 7 gate).
COLOR_LITERAL_ALLOWED = {
    "static/css/base/tokens.css",  # UI-03: absorveu base/theme.css na E7
    "static/css/base/03-theme-dark.css",
    "static/css/components/theme-dark-components.css",  # transitório — dissolver nas fases seguintes
    "static/css/pages/auth.css",  # transitório — login fora do bundle global
    "static/css/shell.bundle.css",  # gerado (NOVO-12); literais vêm das fontes acima
    "static/css/shell.form-components.bundle.css",  # variante gerada (UI-04/HT-04)
}

_HEX_COLOR = re.compile(r"(?<![\w#])#([0-9a-fA-F]{3,8})\b")
_RGB_COLOR = re.compile(r"\brgba?\(\s*[\d.%]+")
_CSS_COMMENT = re.compile(r"/\*.*?\*/")
_CSS_VALUE = re.compile(r":\s*.+")

# Arquivos novos da fase 13 — devem estar 100% livres de literais.
STRICT_COLOR_LITERAL_FILES = {
    "static/css/feedback/notice.css",
    "static/css/feedback/metric.css",
}

# Baseline medido em 30/07/2026 antes da fase 14; o gate falha se a dívida subir.
COLOR_LITERAL_BASELINE = 660

# Escala fechada R-01 — espelha o comentário em static/css/base/tokens.css (Breakpoints).
ALLOWED_MEDIA_BREAKPOINTS = frozenset({
    420, 520, 600, 640, 720, 721, 768, 800, 820, 840, 841, 900,
    1080, 1180, 1181, 1400, 1480,
})

_MEDIA_BLOCK = re.compile(r"@media\s+([^{]+)\{", re.IGNORECASE)
_MEDIA_WIDTH = re.compile(r"(?:min|max)-width:\s*(\d+)px", re.IGNORECASE)

# Templates de alto tráfego + componentes globais que já emitem notice / metric.
CRITICAL_CANONICAL_CLASSES = {
    "notice",
    "notice--info",
    "notice--success",
    "notice--warning",
    "notice--danger",
    "notice-stack",
    "metric",
    "metric--tile",
    "metric-grid",
    "metric-grid--4",
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
        if _is_generated_css(path):
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
        if _is_generated_css(path):
            continue
        for line_no, snippet in _find_color_literals(path):
            violations.append(f"{_rel_css(path)}:{line_no}: {snippet}")
    return violations


def _css_bundle_text() -> str:
    parts: list[str] = []
    for path in sorted(CSS_DIR.rglob("*.css")):
        if _is_generated_css(path):
            continue
        try:
            parts.append(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            parts.append(path.read_text(encoding="latin-1"))
    return "\n".join(parts)


class CssTokenGateTests(SimpleTestCase):
    def test_form_block_usa_o_passo_de_14px_da_escala(self):
        tokens = (CSS_DIR / "base" / "tokens.css").read_text(encoding="utf-8")
        sections = (CSS_DIR / "fields" / "form-sections.css").read_text(encoding="utf-8")

        self.assertIn("--space-3-5: 14px;", tokens)
        self.assertIn("padding: var(--space-3-5);", sections)
        self.assertNotIn("padding: 14px;", sections)

    def test_theme_accents_are_blue_in_light_and_gold_in_dark(self):
        """NOVO-111: accent é paleta de tema; warning continua semântico."""
        light = (CSS_DIR / "base" / "tokens.css").read_text(encoding="utf-8")
        dark = (CSS_DIR / "base" / "03-theme-dark.css").read_text(encoding="utf-8")

        self.assertIn("--color-accent: #155b9a;", light)
        self.assertIn("--color-accent-hover: #17476f;", light)
        self.assertIn("--color-accent-soft: #deebfb;", light)
        self.assertIn("--color-on-accent: var(--color-white);", light)
        self.assertIn("--color-warning: #d8a21b;", light)
        self.assertNotIn(
            "--color-warning-border: var(--color-accent-border-strong);",
            light,
        )

        self.assertIn("--color-accent: #d8a21b;", dark)
        self.assertIn("--color-accent-hover: #e0ab3c;", dark)
        self.assertIn("--color-accent-soft: #3b3320;", dark)
        self.assertIn("--color-on-accent: var(--color-primary-dark);", dark)
        self.assertIn("--sidebar-active-border: var(--color-accent-border-strong);", dark)
        self.assertIn("--sidebar-panel-border: var(--color-accent-border-soft);", dark)

    def test_canonical_component_stylesheets_have_no_color_literals(self):
        """Novos componentes notice/metric devem usar apenas var() de token."""
        violations: list[str] = []
        for rel in sorted(STRICT_COLOR_LITERAL_FILES):
            path = ROOT / rel
            for line_no, snippet in _find_color_literals(path):
                violations.append(f"{rel}:{line_no}: {snippet}")

        self.assertEqual(violations, [], "\n".join(violations))

    def test_media_breakpoints_use_closed_scale(self):
        """Gate R-01: @media width usa somente a escala documentada em tokens.css."""
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
        """Gate leve: classes notice/metric usadas em templates críticos existem no CSS."""
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
        """Templates migrados emitem os contratos v2 de alerta e métrica."""
        expectations = {
            "templates/cotton/v2/alert.html": ("alert", "data-tone"),
            "templates/base.html": ("<c-v2.alert",),
            # `summary_card.html` saiu com o painel de `/`; `metric` continua
            # sendo o canônico e é medido em quem ainda o usa.
            "templates/planos_trabalho/partials/_resumo_evento_body.html": ("fact-list",),
            "templates/core/dashboard.html": ("metric-grid",),
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
        self.assertNotIn("css/feedback/notice.css", base)
        self.assertNotIn("css/feedback/metric.css", base)
        bundle = (ROOT / "static" / "css" / "shell.bundle.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(">>> css/feedback/notice.css >>>", bundle)
        self.assertIn(">>> css/feedback/metric.css >>>", bundle)
