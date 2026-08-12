#!/usr/bin/env python
"""Migra botões HTML de templates de aplicação para o componente Cotton global."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUTTON = re.compile(r"<button(?P<attrs>\b.*?)>(?P<body>.*?)</button>", re.IGNORECASE | re.DOTALL)
CLASS_ATTR = re.compile(r"(?<![\w:-])class(?=\s*=)", re.IGNORECASE)
GENERIC_COMPONENT = re.compile(r"<c-ui\.buttons\.button(?P<attrs>\b.*?)>", re.DOTALL)
PUBLIC_TEMPLATES = {"core/login.html"}


def targets() -> list[Path]:
    result = []
    for path in (ROOT / "templates").rglob("*.html"):
        relative = path.relative_to(ROOT / "templates")
        if relative.parts[0] in {"cotton", "dev"}:
            continue
        if any("ui_lab" in part for part in relative.parts):
            continue
        result.append(path)
    return sorted(result)


def component_for(path: Path) -> str:
    relative = path.relative_to(ROOT / "templates").as_posix()
    if relative in PUBLIC_TEMPLATES or relative.startswith("prestacoes_contas/assinatura/"):
        return "ui.buttons.plain_button"
    return "ui.buttons.button"


def convert(source: str, *, component: str = "ui.buttons.button") -> tuple[str, int]:
    def replacement(match: re.Match[str]) -> str:
        attrs = CLASS_ATTR.sub("class_name", match.group("attrs"), count=1).rstrip()
        return (
            f"<c-{component}{attrs} only>"
            f"{match.group('body')}"
            f"</c-{component}>"
        )

    return BUTTON.subn(replacement, source)


def normalize_component_attrs(source: str) -> tuple[str, int]:
    normalized = 0

    def replacement(match: re.Match[str]) -> str:
        nonlocal normalized
        attrs = match.group("attrs")
        attrs, aria_count = re.subn(
            r"(?<![\w:-])aria-label(?=\s*=)", "aria_label", attrs
        )
        attrs, src_count = re.subn(
            r"(?<![\w:-])data-overlay-src(?=\s*=)", "data_overlay_src", attrs
        )
        normalized += aria_count + src_count
        return f"<c-ui.buttons.button{attrs}>"

    converted = GENERIC_COMPONENT.sub(replacement, source)
    return converted, normalized


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    changed = 0
    migrated = 0
    for path in targets():
        source = path.read_text(encoding="utf-8")
        component = component_for(path)
        converted, raw_count = convert(source, component=component)
        rehomed = 0
        if component == "ui.buttons.plain_button":
            converted, rehomed = re.subn(
                r"(<\/?c-)ui\.buttons\.button(?=[\s>])",
                r"\1ui.buttons.plain_button",
                converted,
            )
        converted, attr_count = normalize_component_attrs(converted)
        count = raw_count + rehomed + attr_count
        if not count:
            continue
        changed += 1
        migrated += count
        if not args.check:
            path.write_text(converted, encoding="utf-8")

    if args.check and migrated:
        print(f"ERRO: {migrated} botão(ões) cru(s) em {changed} arquivo(s)")
        return 1
    if args.check:
        print("OK: nenhum botão cru fora de templates/cotton")
    else:
        print(f"{migrated} botão(ões) migrado(s) em {changed} arquivo(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
