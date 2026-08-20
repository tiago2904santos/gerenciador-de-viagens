#!/usr/bin/env python3
"""Acha `var(--x)` sem declaração e sem fallback no CSS realmente entregue.

Quando uma folha legada é apagada ou deixa de ser carregada, as regras que a
citavam continuam no repositório e param de resolver em silêncio: o navegador
descarta a declaração inválida e o elemento fica sem o estilo, sem erro no
console e sem teste vermelho. Foi o que aconteceu com `--re-accent-border` e
`--re-choice-ring`, que morreram junto com `pages/roteiros.css` e deixaram
`.related-route-item.is-active` (v2/picker.css) sem nenhum efeito visual.

A régua olha o que o navegador de fato recebe: os dois bundles do `base.html`,
com os `@import` expandidos — o `_concat` de `build_shell_bundles.py` mantém a
linha `@import`, então o token de `base/tokens.css` só aparece depois da
expansão. Contar sem expandir superestima o problema em mais de duas vezes.

Uma variável com fallback (`var(--x, 1rem)`) NÃO entra: o fallback é a decisão
explícita de quem escreveu, e a regra continua resolvendo.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC_CSS = ROOT / "static" / "css"
ENTRY_POINTS = ("shell.bundle.css", "ui.bundle.css")

_IMPORT = re.compile(r'@import\s+url\(["\']?([^"\')]+)["\']?\)\s*;')
_DECL = re.compile(r"(--[A-Za-z0-9_-]+)\s*:")
_VAR = re.compile(r"var\(\s*(--[A-Za-z0-9_-]+)\s*(,?)")
_COMMENT = re.compile(r"/\*.*?\*/", re.S)


def without_comments(css: str) -> str:
    """Comentário não entrega estilo — e este repositório comenta em CSS.

    Sem isto, a prosa que cita `var(--color-*)` para explicar a decisão vira
    uma variável órfã chamada `--color-`.
    """
    return _COMMENT.sub("", css)


def expanded(path: Path, seen: set[Path] | None = None) -> str:
    """Texto da folha com os `@import` locais embutidos, sem repetir arquivo."""
    seen = set() if seen is None else seen
    resolved = path.resolve()
    if resolved in seen or not resolved.is_file():
        return ""
    seen.add(resolved)

    def replace(match: re.Match[str]) -> str:
        target = match.group(1)
        if target.startswith(("http://", "https://", "data:")):
            return ""
        return expanded(resolved.parent / target, seen)

    return _IMPORT.sub(replace, resolved.read_text(encoding="utf-8", errors="replace"))


def delivered_css() -> str:
    return without_comments(
        "\n".join(expanded(STATIC_CSS / name) for name in ENTRY_POINTS)
    )


def orphan_variables(css: str) -> dict[str, int]:
    """Variáveis sem declaração, contando só os usos que não têm fallback."""
    declared = set(_DECL.findall(css))
    orphans: dict[str, int] = {}
    for name, comma in _VAR.findall(css):
        if name in declared or comma:
            continue
        orphans[name] = orphans.get(name, 0) + 1
    return orphans


def declared_in_page_sheets(names: set[str]) -> dict[str, list[str]]:
    """Onde cada órfã ainda é declarada fora do CSS global.

    Declarar numa folha de PÁGINA não salva a regra: quem usa a variável é uma
    folha global, que casa em rota que não carrega aquela página. O dado serve
    para separar os dois consertos possíveis — promover o token ao vocabulário
    global, ou apagar a regra que ficou sem dono.
    """
    found: dict[str, list[str]] = {}
    for sheet in sorted(STATIC_CSS.rglob("*.css")):
        if ".bundle." in sheet.name or sheet.parent.name == "profiles":
            continue
        text = without_comments(sheet.read_text(encoding="utf-8", errors="replace"))
        for name in names.intersection(_DECL.findall(text)):
            found.setdefault(name, []).append(
                sheet.relative_to(STATIC_CSS).as_posix()
            )
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max",
        type=int,
        default=0,
        help="teto de variáveis órfãs distintas; a catraca só desce",
    )
    args = parser.parse_args(argv)

    orphans = orphan_variables(delivered_css())
    elsewhere = declared_in_page_sheets(set(orphans))
    for name in sorted(orphans):
        origem = elsewhere.get(name)
        sufixo = f" — declarada só em {', '.join(origem)}" if origem else ""
        print(f"  {name} — {orphans[name]} uso(s) sem fallback{sufixo}")
    total = len(orphans)
    print(f"Variáveis CSS órfãs no CSS entregue: {total} (teto {args.max})")
    if total > args.max:
        print(
            "ERRO: regra que cita variável inexistente é descartada pelo navegador "
            "e o elemento fica sem estilo, sem erro visível."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
