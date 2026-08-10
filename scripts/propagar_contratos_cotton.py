"""Propaga contratos Cotton pelos componentes compostos (HT-14)."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
COTTON = TEMPLATES / "cotton"
DECLARATION = re.compile(r"^{%\s+cotton:vars(?P<vars>(?:\s+[A-Za-z_]\w*)*)\s+%}$")
TAG = re.compile(
    r"<c-(?P<name>[A-Za-z_][\w.]*)\b(?P<attrs>[^<>]*?)(?P<close>/?)>",
    re.DOTALL,
)
ATTR = re.compile(r"(?:^|\s)(?::|::)?(?P<name>[A-Za-z_][\w-]*)(?:\s*=|(?=\s|$))")
SLOT_NAMES = {"slot", "actions", "body", "footer", "meta"}


def contracts() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for path in COTTON.rglob("*.html"):
        lines = path.read_text(encoding="utf-8").splitlines()
        declarations = [DECLARATION.fullmatch(line) for line in lines[:2]]
        match = next((item for item in declarations if item), None)
        if match:
            name = ".".join(path.relative_to(COTTON).with_suffix("").parts)
            result[name] = match.group("vars").split()
    return result


def propagate_text(source: str, known: dict[str, list[str]]) -> str:
    def replace(match: re.Match[str]) -> str:
        declared = known.get(match.group("name"))
        if not declared:
            return match.group(0)
        attrs = match.group("attrs")
        existing = {item.group("name").replace("-", "_") for item in ATTR.finditer(attrs)}
        if "only" in existing:
            return match.group(0)
        missing = [
            name
            for name in declared
            if name not in existing and name not in SLOT_NAMES
        ]
        forwarded = "".join(f' :{name}="{name}"' for name in missing)
        closing = " /" if match.group("close") else ""
        return f'<c-{match.group("name")}{attrs.rstrip()}{forwarded}{closing}>'

    return TAG.sub(replace, source)


def _prepare_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
    sys.path.insert(0, str(ROOT))
    import django

    django.setup()


def update_declarations() -> int:
    from scripts.converter_componentes_cotton import contrato

    changed = 0
    memo: dict[str, set[str]] = {}
    for path in sorted(COTTON.rglob("*.html")):
        expected = contrato(path, memo)
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        index = 1 if lines and re.match(r"^\s*{%\s*extends\b", lines[0]) else 0
        if len(lines) <= index or not DECLARATION.fullmatch(lines[index].rstrip("\r\n")):
            continue
        newline = "\r\n" if lines[index].endswith("\r\n") else "\n"
        declaration = "{% cotton:vars " + " ".join(expected) + " %}" if expected else "{% cotton:vars %}"
        replacement = declaration + newline
        if lines[index] != replacement:
            lines[index] = replacement
            path.write_text("".join(lines), encoding="utf-8", newline="")
            changed += 1
    return changed


def main() -> int:
    _prepare_django()
    total_files = 0
    for iteration in range(1, 20):
        known = contracts()
        changed_files = 0
        for path in sorted(TEMPLATES.rglob("*.html")):
            if path.is_relative_to(TEMPLATES / "components"):
                continue
            source = path.read_text(encoding="utf-8")
            converted = propagate_text(source, known)
            if converted != source:
                path.write_text(converted, encoding="utf-8", newline="")
                changed_files += 1
        changed_contracts = update_declarations()
        total_files += changed_files
        print(
            f"iteração {iteration}: {changed_files} arquivo(s), "
            f"{changed_contracts} contrato(s)"
        )
        if not changed_files and not changed_contracts:
            print(f"propagação estabilizada; {total_files} regravação(ões)")
            return 0
    raise SystemExit("propagação não estabilizou em 19 iterações")


if __name__ == "__main__":
    raise SystemExit(main())
