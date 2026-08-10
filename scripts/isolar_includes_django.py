#!/usr/bin/env python
"""Torna explícito o contexto dos includes Django remanescentes (HT-14)."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOTS = (ROOT / "templates", ROOT / "prestacoes_contas" / "templates")
STATIC_INCLUDE = re.compile(
    r"{%\s*include\s+(?P<quote>[\"'])(?P<target>[^\"']+)(?P=quote)"
    r"(?P<tail>.*?)%}",
    re.DOTALL,
)
WITH_NAME = re.compile(r"(?:^|\s)(?P<name>[A-Za-z_]\w*)\s*=")
DYNAMIC_INCLUDE = re.compile(
    r"{%\s*include\s+(?P<target>[A-Za-z_]\w*)(?P<tail>.*?)%}",
    re.DOTALL,
)
COTTON_VARS = re.compile(r"^{%\s* cotton:vars(?P<vars>.*?)%}", re.DOTALL)
WITH_BLOCK_NAME = re.compile(r"{%\s*with\s+(?P<body>.*?)%}", re.DOTALL)
TEMPLATE_ATTR = re.compile(
    r"(?P<name>[A-Za-z_]\w*template)\s*=\s*[\"'](?P<target>[^\"']+\.html)[\"']"
)


def _prepare_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
    sys.path.insert(0, str(ROOT))
    import django

    django.setup()


def isolate_text(source: str, contracts: dict[str, list[str]]) -> str:
    def replace(match: re.Match[str]) -> str:
        tail = match.group("tail")
        target = match.group("target")
        declared = contracts.get(target)
        if declared is None:
            return match.group(0)
        tail = re.sub(r"\s+only\s*$", "", tail.rstrip())
        existing = {item.group("name") for item in WITH_NAME.finditer(tail)}
        missing = [name for name in declared if name not in existing]
        additions = " ".join(f"{name}={name}" for name in missing)
        stripped = tail.rstrip()
        if additions:
            if re.search(r"\bwith\b", stripped):
                stripped = f"{stripped} {additions}"
            else:
                stripped = f"{stripped} with {additions}"
        return f'{{% include "{target}"{stripped} only %}}'

    return STATIC_INCLUDE.sub(replace, source)


def isolate_dynamic_cotton(
    source: str,
    dynamic_contracts: dict[str, list[str]] | None = None,
) -> str:
    """Isola includes dinâmicos com todo o contexto declarado do componente."""

    declaration = COTTON_VARS.search(source)
    if not declaration:
        return source
    available = declaration.group("vars").split()
    for with_block in WITH_BLOCK_NAME.finditer(source):
        available.extend(
            item.group("name") for item in WITH_NAME.finditer(with_block.group("body"))
        )
    available = list(dict.fromkeys(available))

    def replace(match: re.Match[str]) -> str:
        tail = match.group("tail")
        tail = re.sub(r"\s+only\s*$", "", tail.rstrip())
        existing = {item.group("name") for item in WITH_NAME.finditer(tail)}
        target_contract = (dynamic_contracts or {}).get(match.group("target"), [])
        wanted = list(dict.fromkeys([*available, *target_contract]))
        missing = [name for name in wanted if name not in existing]
        additions = " ".join(f"{name}={name}" for name in missing)
        stripped = tail
        if additions:
            stripped = (
                f"{stripped} {additions}"
                if re.search(r"\bwith\b", stripped)
                else f"{stripped} with {additions}"
            )
        return f"{{% include {match.group('target')}{stripped} only %}}"

    return DYNAMIC_INCLUDE.sub(replace, source)


def main() -> int:
    _prepare_django()
    from scripts.converter_componentes_cotton import contrato_template

    memo: dict[str, set[str]] = {}
    contracts: dict[str, list[str]] = {}
    dynamic_targets: dict[str, set[str]] = {}
    targets: set[str] = set()
    paths: list[Path] = []
    for root in TEMPLATE_ROOTS:
        if root.exists():
            paths.extend(sorted(root.rglob("*.html")))
    for path in paths:
        source = path.read_text(encoding="utf-8")
        targets.update(match.group("target") for match in STATIC_INCLUDE.finditer(source))
        for match in TEMPLATE_ATTR.finditer(source):
            name = match.group("name")
            dynamic_targets.setdefault(name, set()).add(match.group("target"))
            if name.startswith("destination_"):
                dynamic_targets.setdefault(name.removeprefix("destination_"), set()).add(
                    match.group("target")
                )
    for target in sorted(targets):
        contracts[target] = contrato_template(target, memo)
    from django.template import TemplateDoesNotExist

    dynamic_contracts: dict[str, list[str]] = {}
    for name, target_names in dynamic_targets.items():
        variables: set[str] = set()
        for target in target_names:
            try:
                variables.update(contrato_template(target, memo))
            except TemplateDoesNotExist:
                continue
        dynamic_contracts[name] = sorted(variables)

    changed = 0
    for path in paths:
        source = path.read_text(encoding="utf-8")
        converted = isolate_text(source, contracts)
        if path.is_relative_to(ROOT / "templates" / "cotton"):
            converted = isolate_dynamic_cotton(converted, dynamic_contracts)
        if converted != source:
            path.write_text(converted, encoding="utf-8", newline="")
            changed += 1
    print(f"{changed} arquivo(s) com includes isolados")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
