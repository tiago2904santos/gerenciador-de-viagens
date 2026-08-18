#!/usr/bin/env python3
"""Gera bundles de entrega do shell (NOVO-12).

Concatena CSS/JS do shell na ordem canônica — a mesma que `templates/base.html`
usava antes do bundle — sem alterar as fontes. Os arquivos de origem continuam
sendo a unidade de edição; os bundles existem só para cortar o waterfall HTTP.

Uso:
  python scripts/build_shell_bundles.py          # gera
  python scripts/build_shell_bundles.py --check  # falha se desatualizado
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"

# Ordem = cascata histórica de templates/base.html (antes do NOVO-12).
# theme-shared.js / theme-init.js ficam fora do bundle JS (head, sem defer).
SHELL_CSS: tuple[str, ...] = (
    "css/style.css",
    "css/base/03-theme-dark.css",
    "css/base/utilities.css",
    "css/layout/page-shell.css",
    "css/actions/buttons.css",
    "css/fields/field.css",
    "css/actions/action-system.css",
    "css/lists/record-list.css",
    "css/lists/list-tabs.css",
    "css/lists/filter-header.css",
    "css/fields/form-panel.css",
    "css/fields/form-sections.css",
    "css/feedback/pendencias.css",
    "css/feedback/summary-items.css",
    "css/feedback/notice.css",
    "css/feedback/metric.css",
    "css/layout/app-shell.css",
    "css/lists/content-cards.css",
    "css/pages/document-viewer.css",
    "css/feedback/dialog.css",
    "css/feedback/document-download-loading.css",
    "css/components/theme-dark-components.css",
    "css/components/theme-shared-components.css",
    "css/lists/list-header.css",
)

FORM_COMPONENTS_CSS: tuple[str, ...] = (
    "css/fields/date-picker.css",
    "css/fields/file-picker.css",
)

# Famílias antes espalhadas em CSS de domínio precisam continuar depois de
# todo o shell global, como eram quando chegavam pelos blocos extra_css.
FORM_COMPONENTS_CSS_AFTER_SHELL: tuple[str, ...] = (
    "css/fields/related-route-picker.css",
)

FORM_COMPONENT_IMPORTS: tuple[tuple[str, str], ...] = (
    (
        '@import url("./lists/cards.css");',
        '@import url("./fields/search-picker.css");',
    ),
    (
        '@import url("./fields/select.css");',
        '@import url("./fields/custom-select.css");',
    ),
)

_FORM_CSS_INSERT_AT = SHELL_CSS.index("css/fields/field.css") + 1
SHELL_CSS_WITH_FORM_COMPONENTS: tuple[str, ...] = (
    SHELL_CSS[:_FORM_CSS_INSERT_AT]
    + FORM_COMPONENTS_CSS
    + SHELL_CSS[_FORM_CSS_INSERT_AT:]
    + FORM_COMPONENTS_CSS_AFTER_SHELL
)

SHELL_JS: tuple[str, ...] = (
    "js/theme-toggle.js",
    "js/core/http.js",
    "js/core/app.js",
    "js/core/component-loader.js",
    "js/autosave.js",
    "js/components/sidebar.js",
    "js/components/masks.js",
    "js/components/state-toggle.js",
    "js/components/collection.js",
    "js/components/icon-tooltips.js",
    "js/components/overlay.js",
    "js/components/fields-init.js",
    "js/components/document-download.js",
    "js/components/fit-text.js",
    "js/components/notice-auto-dismiss.js",
)

# HT-04: componentes pesados de formulario/documento saem do shell global. A
# fabrica vem antes dos dois renderers porque este bundle tambem pode ser
# carregado depois de DOMContentLoaded, quando registerEnhancer inicializa cada
# modulo imediatamente.
FORM_COMPONENTS_JS: tuple[str, ...] = (
    "js/components/picker-parts.js",
    "js/components/picker.js",
    "js/components/picker-select.js",
    "js/components/location-rows.js",
    "js/components/document-source.js",
    "js/components/document-search.js",
    "js/components/date-picker.js",
)

# Componentes globais (NOVO-120). `tokens.css` PRIMEIRO: os outros só o leem.
# A fonte continua um arquivo por componente; o bundle existe só para a
# entrega, pelo mesmo motivo do NOVO-12 — e para nao subir a contagem de
# <link> em template, que a catraca do `test_entity_card_styles` so deixa cair.
UI_CSS: tuple[str, ...] = (
    # v2 (NOVO-120) PRIMEIRO: é a fundação que as folhas seguintes leem. Entra
    # neste bundle, e não num <link> novo, porque este é o ponto de entrega que
    # NÃO passa pelo podador de `build_css_profiles.py` — e o orçamento de dois
    # arquivos do NOVO-12 fica preservado.
    "css/v2/tokens.css",
    "css/v2/base.css",
    "css/v2/button.css",
    "css/v2/input.css",
    "css/v2/field.css",
    "css/v2/form-block.css",
    "css/v2/header.css",
    "css/v2/rail.css",
    "css/v2/select.css",
    "css/v2/listbox.css",
    "css/v2/toggle.css",
    "css/v2/chip.css",
    "css/v2/panel.css",
    "css/v2/alert.css",
    "css/v2/menu.css",
    "css/v2/record.css",
    "css/v2/route-editor.css",
    "css/v2/person-row.css",
    "css/v2/choice-card.css",
    "css/v2/icon-button.css",
    "css/v2/modal.css",
    "css/v2/form-errors.css",
    "css/v2/card-footer.css",
    "css/v2/stepper.css",
    "css/v2/destination-row.css",
    "css/v2/destinations.css",
    "css/v2/picker.css",
    "css/v2/date-picker.css",
    "css/v2/pagination.css",
    "css/v2/file-picker.css",
    "css/v2/file-list.css",
    "css/v2/fab.css",
    "css/v2/quick-add.css",
    "css/v2/list-page.css",
    "css/v2/form-page.css",
    "css/v2/document-inline.css",
    "css/v2/fact.css",
    "css/v2/font-try.css",
    "css/v2/download-picker.css",
    "css/v2/tooltip.css",
    "css/v2/surface.css",
    "css/ui/tokens.css",
    "css/ui/header.css",
    "css/ui/sub-header.css",
    "css/ui/input.css",
    "css/ui/select.css",
    "css/ui/date-picker.css",
    "css/ui/button-secondary.css",
    "css/ui/segment-toggle.css",
    "css/ui/form-block.css",
    "css/ui/surface.css",
)

CSS_BUNDLE = STATIC / "css" / "shell.bundle.css"
FORM_CSS_BUNDLE = STATIC / "css" / "shell.form-components.bundle.css"
UI_CSS_BUNDLE = STATIC / "css" / "ui.bundle.css"
JS_BUNDLE = STATIC / "js" / "shell.bundle.js"
FORM_COMPONENTS_BUNDLE = STATIC / "js" / "form-components.bundle.js"
CSS_PROFILES_BUILDER = ROOT / "scripts" / "build_css_profiles.py"

BANNER = (
    "/* AUTO-GENERATED by scripts/build_shell_bundles.py — do not edit. "
    "Edit the source files listed below and re-run the script. */\n"
)


def _read(rel: str) -> str:
    path = STATIC / rel
    if not path.is_file():
        raise FileNotFoundError(f"fonte ausente: {rel}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _style_with_form_components() -> str:
    style = _read("css/style.css")
    for import_after, import_line in FORM_COMPONENT_IMPORTS:
        if import_line in style:
            raise ValueError("style.css voltou a importar componentes de formulario")
        if style.count(import_after) != 1:
            raise ValueError(
                "ponto de insercao dos imports de formulario ausente ou ambiguo"
            )
        style = style.replace(import_after, f"{import_after}\n{import_line}")
    return style


def _concat(
    sources: tuple[str, ...],
    kind: str,
    *,
    overrides: dict[str, str] | None = None,
) -> str:
    parts: list[str] = [BANNER, f"/* shell {kind} sources ({len(sources)}): */\n"]
    for rel in sources:
        parts.append(f"\n/* >>> {rel} >>> */\n")
        if overrides is not None and rel in overrides:
            parts.append(overrides[rel])
        else:
            parts.append(_read(rel))
        if not parts[-1].endswith("\n"):
            parts.append("\n")
        parts.append(f"/* <<< {rel} <<< */\n")
    return "".join(parts)


def build() -> tuple[str, str, str, str]:
    css = _concat(SHELL_CSS, "css")
    form_css = _concat(
        SHELL_CSS_WITH_FORM_COMPONENTS,
        "css with form components",
        overrides={"css/style.css": _style_with_form_components()},
    )
    js = _concat(SHELL_JS, "js")
    form_components = _concat(FORM_COMPONENTS_JS, "form components js")
    CSS_BUNDLE.parent.mkdir(parents=True, exist_ok=True)
    JS_BUNDLE.parent.mkdir(parents=True, exist_ok=True)
    CSS_BUNDLE.write_text(css, encoding="utf-8", newline="\n")
    UI_CSS_BUNDLE.write_text(_concat(UI_CSS, "css"), encoding="utf-8", newline="\n")
    FORM_CSS_BUNDLE.write_text(form_css, encoding="utf-8", newline="\n")
    JS_BUNDLE.write_text(js, encoding="utf-8", newline="\n")
    FORM_COMPONENTS_BUNDLE.write_text(
        form_components, encoding="utf-8", newline="\n"
    )
    subprocess.run([sys.executable, str(CSS_PROFILES_BUILDER)], cwd=ROOT, check=True)
    return css, form_css, js, form_components


def check() -> int:
    expected_css = _concat(SHELL_CSS, "css")
    expected_form_css = _concat(
        SHELL_CSS_WITH_FORM_COMPONENTS,
        "css with form components",
        overrides={"css/style.css": _style_with_form_components()},
    )
    expected_js = _concat(SHELL_JS, "js")
    errors: list[str] = []
    expected_ui = _concat(UI_CSS, "css")
    if not UI_CSS_BUNDLE.is_file():
        errors.append(f"ausente: {UI_CSS_BUNDLE.relative_to(ROOT).as_posix()}")
    elif UI_CSS_BUNDLE.read_text(encoding="utf-8") != expected_ui:
        errors.append(f"desatualizado: {UI_CSS_BUNDLE.relative_to(ROOT).as_posix()}")
    if not CSS_BUNDLE.is_file():
        errors.append(f"ausente: {CSS_BUNDLE.relative_to(ROOT).as_posix()}")
    elif CSS_BUNDLE.read_text(encoding="utf-8") != expected_css:
        errors.append(
            f"desatualizado: {CSS_BUNDLE.relative_to(ROOT).as_posix()} "
            "(rode python scripts/build_shell_bundles.py)"
        )
    if not FORM_CSS_BUNDLE.is_file():
        errors.append(f"ausente: {FORM_CSS_BUNDLE.relative_to(ROOT).as_posix()}")
    elif FORM_CSS_BUNDLE.read_text(encoding="utf-8") != expected_form_css:
        errors.append(
            f"desatualizado: {FORM_CSS_BUNDLE.relative_to(ROOT).as_posix()} "
            "(rode python scripts/build_shell_bundles.py)"
        )
    if not JS_BUNDLE.is_file():
        errors.append(f"ausente: {JS_BUNDLE.relative_to(ROOT).as_posix()}")
    elif JS_BUNDLE.read_text(encoding="utf-8") != expected_js:
        errors.append(
            f"desatualizado: {JS_BUNDLE.relative_to(ROOT).as_posix()} "
            "(rode python scripts/build_shell_bundles.py)"
        )
    expected_form_components = _concat(FORM_COMPONENTS_JS, "form components js")
    if not FORM_COMPONENTS_BUNDLE.is_file():
        errors.append(
            f"ausente: {FORM_COMPONENTS_BUNDLE.relative_to(ROOT).as_posix()}"
        )
    elif FORM_COMPONENTS_BUNDLE.read_text(encoding="utf-8") != expected_form_components:
        errors.append(
            f"desatualizado: {FORM_COMPONENTS_BUNDLE.relative_to(ROOT).as_posix()} "
            "(rode python scripts/build_shell_bundles.py)"
        )
    profiles = subprocess.run(
        [sys.executable, str(CSS_PROFILES_BUILDER), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if profiles.returncode:
        errors.append(profiles.stdout.strip() or profiles.stderr.strip())
    if errors:
        print("NOVO-12 shell bundles:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(
        f"OK: shell bundles atualizados "
        f"({len(SHELL_CSS)} css, {len(SHELL_JS)} js de shell, "
        f"{len(FORM_COMPONENTS_JS)} js de formulario)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="não escreve; exit 1 se bundles ausentes ou desatualizados",
    )
    args = parser.parse_args(argv)
    if args.check:
        return check()
    css, form_css, js, form_components = build()
    print(
        f"gerado {CSS_BUNDLE.relative_to(ROOT).as_posix()} "
        f"({len(css)} bytes), {FORM_CSS_BUNDLE.relative_to(ROOT).as_posix()} "
        f"({len(form_css)} bytes), {JS_BUNDLE.relative_to(ROOT).as_posix()} "
        f"({len(js)} bytes) e "
        f"{FORM_COMPONENTS_BUNDLE.relative_to(ROOT).as_posix()} "
        f"({len(form_components)} bytes)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
