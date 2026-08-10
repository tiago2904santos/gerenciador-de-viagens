#!/usr/bin/env python
"""Converte componentes legados em Cotton sem alterar seus chamadores.

A E4 de ``docs/PLANO_RECONSTRUCAO_FRONT_2026-08.md`` mantém cada caminho
``templates/components/**`` como uma casca de compatibilidade. O markup original
vai para ``templates/cotton/**`` e recebe uma declaração ``cotton:vars`` gerada
a partir das variáveis livres do template.

O comando é deliberadamente incremental: uma família por execução/commit.
Use ``--check`` para imprimir o inventário e reprovar se uma casca ou contrato
já convertido divergir do que seria gerado.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "templates" / "components"
COTTON = ROOT / "templates" / "cotton"


def _preparar_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
    sys.path.insert(0, str(ROOT))
    import django

    django.setup()


def _raiz_da_variavel(variable: Any) -> str | None:
    lookups = getattr(variable, "lookups", None)
    if not lookups:
        return None
    root = lookups[0]
    if not isinstance(root, str) or not root.isidentifier():
        return None
    if root in {"True", "False", "None"}:
        return None
    return root


def _variaveis_em_expressao(obj: Any, *, vistos: set[int] | None = None) -> set[str]:
    """Extrai raízes de ``Variable``/``FilterExpression`` de uma expressão.

    Condições ``if`` usam a árvore de ``smartif``; filtros guardam argumentos
    fora de ``FilterExpression.var``. A caminhada por atributos cobre ambos sem
    depender de classes internas do Django.
    """

    from django.template.base import FilterExpression, Node, NodeList, Variable

    if vistos is None:
        vistos = set()
    if obj is None or isinstance(obj, (str, bytes, int, float, bool)):
        return set()
    if id(obj) in vistos:
        return set()
    vistos.add(id(obj))

    if isinstance(obj, Variable):
        root = _raiz_da_variavel(obj)
        return {root} if root else set()
    if isinstance(obj, FilterExpression):
        found = _variaveis_em_expressao(obj.var, vistos=vistos)
        for _func, args in obj.filters:
            for lookup, value in args:
                if lookup:
                    found.update(_variaveis_em_expressao(value, vistos=vistos))
        return found
    if isinstance(obj, (Node, NodeList)):
        return set()
    if isinstance(obj, dict):
        values: Iterable[Any] = obj.values()
    elif isinstance(obj, (list, tuple, set, frozenset)):
        values = obj
    elif hasattr(obj, "__dict__"):
        values = (
            value
            for key, value in vars(obj).items()
            if key not in {"token", "origin", "source", "extra_data", "engine"}
        )
    else:
        return set()

    found: set[str] = set()
    for value in values:
        found.update(_variaveis_em_expressao(value, vistos=vistos))
    return found


def _externas(expr: Any, bound: set[str]) -> set[str]:
    return _variaveis_em_expressao(expr) - bound


def _template_literal(expression: Any) -> str | None:
    variable = getattr(expression, "var", None)
    if variable is None or getattr(variable, "lookups", None):
        return None
    literal = getattr(variable, "literal", None)
    return literal if isinstance(literal, str) else None


def _contrato(template_name: str, memo: dict[str, set[str]], stack: set[str]) -> set[str]:
    from django.template.base import NodeList, VariableNode
    from django.template.defaulttags import (
        FirstOfNode,
        ForNode,
        IfNode,
        URLNode,
        WithNode,
    )
    from django.template.loader import get_template
    from django.template.loader_tags import BlockNode, ExtendsNode, IncludeNode

    if template_name.startswith("components/"):
        cotton_name = "cotton/" + template_name.removeprefix("components/")
        if (ROOT / "templates" / cotton_name).exists():
            template_name = cotton_name

    if template_name in memo:
        return set(memo[template_name])
    if template_name in stack:
        return set()
    stack = {*stack, template_name}
    template = get_template(template_name).template

    def nodelist_contract(nodelist: NodeList, initial_bound: set[str]) -> set[str]:
        found: set[str] = set()
        bound = set(initial_bound)

        for node in nodelist:
            if isinstance(node, VariableNode):
                found.update(_externas(node.filter_expression, bound))
                continue

            if isinstance(node, WithNode):
                for expression in node.extra_context.values():
                    found.update(_externas(expression, bound))
                found.update(
                    nodelist_contract(
                        node.nodelist,
                        bound | set(node.extra_context),
                    )
                )
                continue

            if isinstance(node, ForNode):
                found.update(_externas(node.sequence, bound))
                loop_bound = bound | set(node.loopvars) | {"forloop"}
                found.update(nodelist_contract(node.nodelist_loop, loop_bound))
                found.update(nodelist_contract(node.nodelist_empty, bound))
                continue

            if isinstance(node, IfNode):
                for condition, branch in node.conditions_nodelists:
                    found.update(_externas(condition, bound))
                    found.update(nodelist_contract(branch, bound))
                continue

            if isinstance(node, IncludeNode):
                template_literal = _template_literal(node.template)
                if template_literal is None:
                    found.update(_externas(node.template, bound))
                for expression in node.extra_context.values():
                    found.update(_externas(expression, bound))

                if template_literal and not node.isolated_context:
                    target = template_literal
                    if target.startswith("components/"):
                        nested = _contrato(target, memo, stack)
                        found.update(nested - set(node.extra_context) - bound)
                continue

            if isinstance(node, URLNode):
                found.update(_externas(node.view_name, bound))
                for expression in node.args:
                    found.update(_externas(expression, bound))
                for expression in node.kwargs.values():
                    found.update(_externas(expression, bound))
                if node.asvar:
                    bound.add(node.asvar)
                continue

            if isinstance(node, FirstOfNode):
                for expression in node.vars:
                    found.update(_externas(expression, bound))
                if node.asvar:
                    bound.add(node.asvar)
                continue

            if isinstance(node, BlockNode):
                found.update(nodelist_contract(node.nodelist, bound))
                continue

            if isinstance(node, ExtendsNode):
                found.update(_externas(node.parent_name, bound))
                found.update(nodelist_contract(node.nodelist, bound))
                continue

            # Os demais nós atuais são Text/Comment/Load/Verbatim/CsrfToken.
            # Ainda assim, percorremos expressões futuras guardadas no próprio nó.
            for key, value in vars(node).items():
                if key in {
                    "token",
                    "origin",
                    "source",
                    "extra_data",
                    "engine",
                    "nodelist",
                }:
                    continue
                found.update(_externas(value, bound))

        return found

    result = nodelist_contract(template.nodelist, set())
    memo[template_name] = result
    return set(result)


def contrato(path: Path, memo: dict[str, set[str]]) -> list[str]:
    template_name = path.relative_to(ROOT / "templates").as_posix()
    return sorted(_contrato(template_name, memo, set()))


def _newline(raw: bytes) -> str:
    del raw
    return "\n"


def _declaracao(params: list[str]) -> str:
    names = " ".join(params)
    return f"{{% cotton:vars {names} %}}" if names else "{% cotton:vars %}"


def _conteudo_cotton(source: Path, params: list[str]) -> bytes:
    raw = source.read_bytes()
    newline = _newline(raw)
    text = raw.decode("utf-8").replace("\r\n", "\n")
    declaration = _declaracao(params)

    # ``ExtendsNode`` precisa continuar sendo o primeiro nó. A declaração entra
    # logo depois dele e a casca legada vira um adaptador de herança.
    if re.match(r"^\s*{%\s*extends\b", text):
        first_line, separator, rest = text.partition("\n")
        if not separator:
            return (first_line + newline + declaration + newline).encode("utf-8")
        return (first_line + newline + declaration + newline + rest).encode("utf-8")

    return (declaration + newline + text).encode("utf-8")


def _casca(source: Path, component_name: str, params: list[str], newline: str) -> bytes:
    canonical = _target(source) if _target(source).exists() else source
    first_line = canonical.read_text(encoding="utf-8").splitlines()[0]
    if re.match(r"^\s*{%\s*extends\b", first_line):
        target_name = _target(source).relative_to(ROOT / "templates").as_posix()
        return f'{{% extends "{target_name}" %}}{newline}'.encode("utf-8")

    attrs = " ".join(f':{name}="{name}"' for name in params)
    spacing = " " if attrs else ""
    return f"<c-{component_name}{spacing}{attrs} />{newline}".encode("utf-8")


def _component_name(source: Path) -> str:
    relative = source.relative_to(COMPONENTS).with_suffix("")
    return ".".join(relative.parts)


def _target(source: Path) -> Path:
    return COTTON / source.relative_to(COMPONENTS)


def componentes_da_familia(family: str) -> list[Path]:
    base = COMPONENTS / family
    if base.is_file() and base.suffix == ".html":
        return [base]
    if not base.exists():
        candidate = base.with_suffix(".html")
        if candidate.exists():
            return [candidate]
        raise SystemExit(f"família/componente inexistente: {family}")
    return sorted(base.rglob("*.html"))


def _uso(template_name: str) -> int:
    needle_a = f'"{template_name}"'
    needle_b = f"'{template_name}'"
    total = 0
    for path in (ROOT / "templates").rglob("*.html"):
        if path.is_relative_to(COTTON):
            continue
        text = path.read_text(encoding="utf-8")
        total += text.count(needle_a) + text.count(needle_b)
    return total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("family", help="caminho relativo a templates/components")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--repair", action="store_true")
    args = parser.parse_args()

    _preparar_django()
    memo: dict[str, set[str]] = {}
    errors: list[str] = []

    for source in componentes_da_familia(args.family):
        params = contrato(source, memo)
        target = _target(source)
        template_name = source.relative_to(ROOT / "templates").as_posix()
        print(
            f"{template_name}: usos={_uso(template_name)} "
            f"params={','.join(params) or '-'}"
        )

        # Em --check, o alvo já contém a declaração. Compare a casca e apenas
        # valide que a declaração do alvo corresponde ao contrato recalculado.
        if args.check:
            if not target.exists():
                errors.append(f"alvo ausente: {target.relative_to(ROOT)}")
                continue
            target_text = target.read_text(encoding="utf-8")
            target_lines = target_text.splitlines()
            declaration_index = (
                1
                if target_lines and re.match(r"^\s*{%\s*extends\b", target_lines[0])
                else 0
            )
            actual_declaration = (
                target_lines[declaration_index]
                if len(target_lines) > declaration_index
                else ""
            )
            if actual_declaration != _declaracao(params):
                errors.append(
                    f"contrato divergente em {target.relative_to(ROOT)}: "
                    f"{actual_declaration!r}"
                )
            expected_wrapper = _casca(
                source,
                _component_name(source),
                params,
                _newline(source.read_bytes()),
            )
            if source.read_bytes() != expected_wrapper:
                errors.append(f"casca divergente: {source.relative_to(ROOT)}")
            continue

        if target.exists() and args.repair:
            target.write_text(
                target.read_text(encoding="utf-8").replace("\r\n", "\n"),
                encoding="utf-8",
                newline="\n",
            )
            source.write_bytes(_casca(source, _component_name(source), params, "\n"))
            continue
        if target.exists():
            errors.append(f"alvo já existe: {target.relative_to(ROOT)}")
            continue
        raw = source.read_bytes()
        try:
            cotton_content = _conteudo_cotton(source, params)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(cotton_content)
        source.write_bytes(_casca(source, _component_name(source), params, _newline(raw)))

    if errors:
        print("\nERRO:")
        for error in errors:
            print(f"- {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
