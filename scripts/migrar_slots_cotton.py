"""Migra parciais dinâmicos de cards para slots Cotton explícitos (HT-14)."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
COMPONENTS = {"form.card", "ui.forms.form_block"}
SLOTS = {"actions", "body", "footer", "meta"}
TAG = re.compile(
    r"<c-(?P<name>form\.card|ui\.forms\.form_block)\b(?P<attrs>.*?)\s*/>",
    re.DOTALL,
)
TEMPLATE_ATTR = re.compile(
    r"(?P<space>\s+)(?P<dynamic>:?)(?P<slot>actions|body|footer|meta)_template="
    r"(?P<quote>[\"'])(?P<value>.*?)(?P=quote)",
    re.DOTALL,
)


def converter_tag(source: str) -> str:
    def replace(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        slots: list[tuple[str, str, str]] = []

        def extract(attr: re.Match[str]) -> str:
            slot = attr.group("slot")
            if slot not in SLOTS:
                return attr.group(0)
            if not attr.group("value"):
                return ""
            slots.append((slot, attr.group("dynamic"), attr.group("value")))
            return ""

        attrs = TEMPLATE_ATTR.sub(extract, attrs).rstrip()
        if not slots:
            if attrs != match.group("attrs").rstrip():
                return f'<c-{match.group("name")}{attrs} />'
            return match.group(0)

        body = []
        for slot, dynamic, value in slots:
            template = value if dynamic else f'"{value}"'
            body.append(
                f'<c-slot name="{slot}">{{% include {template} %}}</c-slot>'
            )
        return f'<c-{match.group("name")}{attrs}>' + "".join(body) + f'</c-{match.group("name")}>'

    return TAG.sub(replace, source)


def paths(inputs: list[str]) -> list[Path]:
    roots = [Path(item) for item in inputs] if inputs else [TEMPLATES]
    found: set[Path] = set()
    for root in roots:
        root = root if root.is_absolute() else ROOT / root
        if root.is_file() and root.suffix == ".html":
            found.add(root)
        elif root.is_dir():
            found.update(root.rglob("*.html"))
    return sorted(path for path in found if "templates/components" not in path.as_posix())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="*")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    changed: list[Path] = []
    for path in paths(args.inputs):
        source = path.read_text(encoding="utf-8")
        converted = converter_tag(source)
        if converted == source:
            continue
        changed.append(path)
        if not args.check:
            path.write_text(converted, encoding="utf-8", newline="")

    for path in changed:
        print(path.relative_to(ROOT))
    print(f"{len(changed)} arquivo(s) {'pendente(s)' if args.check else 'migrado(s)'}")
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
