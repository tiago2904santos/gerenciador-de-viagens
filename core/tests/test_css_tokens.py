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

CANONICAL_CUSTOM_PROPERTIES = frozenset({
    "--r-0", "--r-sm", "--r-md", "--r-lg", "--r-xl", "--r-pill",
    "--sp-1", "--sp-2", "--sp-3", "--sp-4", "--sp-5", "--sp-6",
    "--sp-7", "--sp-8", "--cv-ink", "--cv-ink-muted",
    "--cv-state-danger", "--cv-state-success", "--cv-state-warning",
    "--cv-border", "--bd", "--bd-0", "--bd-strong", "--sh-sm",
    "--sh-md", "--sh-lg", "--sh-none", "--cv-surface-page",
    "--cv-surface-card", "--cv-surface-block", "--cv-surface",
    "--cv-surface-next", "--color-accent", "--on-accent", "--accent-tint",
})

GEOMETRY_VALUE_LIMITS = {
    "border-radius": 6,
    "padding": 8,
    "margin": 8,
    "border": 3,
    "box-shadow": 4,
}

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
    def test_novo30_phase3_uses_only_the_canonical_custom_property_vocabulary(self):
        """NOVO-30/3: aliases temporarios morreram e componentes nao declaram tokens."""
        definitions_outside_layers: list[str] = []
        unknown_references: list[str] = []

        for path in sorted(CSS_DIR.rglob("*.css")):
            if path.name.endswith(".bundle.css"):
                continue
            text = path.read_text(encoding="utf-8")
            without_comments = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
            rel = _rel_css(path)
            definitions = set(
                re.findall(r"^\s*(--[\w-]+)\s*:", without_comments, re.M)
            )
            if path.name not in {"00-palette.css", "01-tokens.css"}:
                definitions_outside_layers.extend(
                    f"{rel}: {name}" for name in sorted(definitions)
                )
            for name in re.findall(r"var\(\s*(--[\w-]+)", without_comments):
                if name not in CANONICAL_CUSTOM_PROPERTIES and not name.startswith("--bs-"):
                    unknown_references.append(f"{rel}: {name}")

        token_definitions = set(
            re.findall(
                r"^\s*(--[\w-]+)\s*:",
                (CSS_DIR / "01-tokens.css").read_text(encoding="utf-8"),
                re.M,
            )
        )
        expected_token_definitions = CANONICAL_CUSTOM_PROPERTIES - {
            "--cv-surface-page", "--cv-surface-card", "--cv-surface-block",
            "--cv-surface", "--cv-surface-next", "--color-accent",
            "--on-accent", "--accent-tint",
        }
        self.assertEqual(token_definitions, expected_token_definitions)
        self.assertEqual(definitions_outside_layers, [])
        self.assertEqual(sorted(set(unknown_references)), [])

    def test_novo30_phase3_geometry_uses_the_closed_scales(self):
        """Gate literal do plano: cada propriedade cabe no teto da escala fechada."""
        for prop, limit in GEOMETRY_VALUE_LIMITS.items():
            values: set[str] = set()
            for path in CSS_DIR.rglob("*.css"):
                if path.name == "shell.bundle.css":
                    continue
                values.update(
                    re.findall(
                        rf"{prop}:\s*([^;]+)",
                        path.read_text(encoding="utf-8"),
                    )
                )
            with self.subTest(property=prop):
                self.assertLessEqual(
                    len(values),
                    limit,
                    f"{prop} fora da escala ({len(values)} > {limit}): {sorted(values)}",
                )

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
