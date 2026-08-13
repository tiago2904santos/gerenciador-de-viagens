#!/usr/bin/env python
"""Inventário de componentes cotton e partials, lido do código-fonte.

Camada de dados da galeria de componentes. Não renderiza nada e não abre o
banco: tudo aqui sai de análise estática dos templates, porque a galeria precisa
listar peça que hoje ninguém usa — e peça sem uso nunca aparece num inventário
por rota renderizada (`inventariar_paginas.py`, que é o complemento deste).

Duas famílias, com tratamento diferente porque o problema é diferente:

- **cotton** (`templates/cotton/**`): declaram `{% cotton:vars … %}` na primeira
  linha, os 91 sem exceção. A lista de props é legível por máquina, então a
  galeria pode renderizar cada um de verdade. Aqui só extraímos o contrato.

- **partials** (`**/partials/**`, `**/includes/**`): leem o contexto de quem os
  incluiu. Renderizados soltos saem vazios ou estouram, então a galeria os trata
  como catálogo — quem inclui, quais variáveis o corpo lê, onde aparece. É essa
  referência cruzada que este script monta.

Uso:
  python scripts/inventariar_componentes.py                     # markdown no stdout
  python scripts/inventariar_componentes.py --json docs/x.json  # dados crus
  python scripts/inventariar_componentes.py --saida docs/x.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"

# `{% cotton:vars a b c %}` — o contrato de props, sempre na primeira linha.
VARS = re.compile(r"\{%\s*cotton:vars\s+(.*?)%\}", re.S)
# `<c-ui.buttons.button …>` — a forma canônica de invocação (1.156 no repo).
USO_COTTON = re.compile(r"<c-([a-z0-9_.-]+)")
# `<c-slot name="rodape">` — slot nomeado; `{{ slot }}` é o anônimo.
SLOT_NOMEADO = re.compile(r'<c-slot\s+name=["\']([\w-]+)["\']')
SLOT_ANONIMO = re.compile(r"\{\{\s*slot\s*\}\}")
INCLUDE = re.compile(r"""\{%\s*include\s+["']([^"']+)["']""")
# Um partial também é alcançado sem `{% include %}`: como string numa prop
# (`card_template="oficios/partials/oficio_list_card.html"`) e do Python
# (`render_to_string("…")`). Ignorar essas duas formas produz órfão falso — e
# poda de arquivo vivo. É o que o `AGENTS.md` §3.6 exige cobrir.
REFERENCIA_HTML = re.compile(r"""["']([\w./-]+\.html)["']""")
# Variáveis que o corpo lê. Heurística deliberada: pega o primeiro segmento de
# `{{ oficio.numero }}` e as condições de `{% if %}`/`{% for %}`.
INTERPOLACAO = re.compile(r"\{\{\s*([a-z_][\w]*)")
TAG_IF = re.compile(r"\{%\s*(?:if|elif)\s+(.+?)%\}")
TAG_FOR = re.compile(r"\{%\s*for\s+[\w\s,]+?\s+in\s+([a-z_][\w]*)")
NOME_PYTHON = re.compile(r"[a-z_][\w]*")

# Ruído do próprio Django/cotton, não é contexto que o partial espera receber.
IGNORADAS = {
    "and", "as", "block", "by", "csrf_token", "elif", "else", "empty", "endblock",
    "endfor", "endif", "endwith", "extends", "false", "for", "forloop", "if", "in",
    "include", "is", "load", "none", "not", "now", "only", "or", "request", "slot",
    "static", "trans", "true", "url", "user", "with",
}


def nome_do_cotton(caminho: Path) -> str:
    """`templates/cotton/ui/buttons/button.html` → `ui.buttons.button`."""
    return ".".join(caminho.relative_to(TEMPLATES / "cotton").with_suffix("").parts)


def relativo(caminho: Path) -> str:
    return caminho.relative_to(TEMPLATES).as_posix()


def normalizar(referencia: str) -> str:
    """Um mesmo template é citado com e sem o prefixo `templates/`.

    O Django resolve pelo caminho relativo à pasta de templates, mas testes e
    scripts abrem o arquivo direto (`Path("templates/oficios/partials/x.html")`).
    Sem colapsar as duas formas, a segunda não casa e o partial vira órfão falso.
    """
    return referencia[len("templates/") :] if referencia.startswith("templates/") else referencia


def variaveis_lidas(texto: str) -> list[str]:
    achadas: set[str] = set()
    achadas.update(INTERPOLACAO.findall(texto))
    achadas.update(TAG_FOR.findall(texto))
    for condicao in TAG_IF.findall(texto):
        achadas.update(NOME_PYTHON.findall(condicao))
    return sorted(n for n in achadas if n not in IGNORADAS)


def coletar() -> dict:
    todos = sorted(TEMPLATES.rglob("*.html"))
    fonte = {p: p.read_text(encoding="utf-8", errors="replace") for p in todos}

    # Grafo de uso: quem invoca cada cotton e quem alcança cada partial.
    usos_cotton: dict[str, list[str]] = defaultdict(list)
    usos_include: dict[str, list[str]] = defaultdict(list)
    referencias: dict[str, list[str]] = defaultdict(list)
    for caminho, texto in fonte.items():
        origem = relativo(caminho)
        for nome in set(USO_COTTON.findall(texto)):
            if nome != "slot":
                usos_cotton[nome].append(origem)
        for alvo in set(INCLUDE.findall(texto)):
            usos_include[alvo].append(origem)
        for alvo in {normalizar(a) for a in REFERENCIA_HTML.findall(texto)}:
            if alvo != origem:
                referencias[alvo].append(origem)

    # O Python também nomeia template: `render_to_string`, `template_name`,
    # `TemplateResponse`. Sem varrer aqui, todo card renderizado por view vira
    # órfão falso.
    for py in ROOT.rglob("*.py"):
        if any(parte in {".venv", "node_modules", "__pycache__"} for parte in py.parts):
            continue
        try:
            texto = py.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        origem = py.relative_to(ROOT).as_posix()
        for alvo in {normalizar(a) for a in REFERENCIA_HTML.findall(texto)}:
            referencias[alvo].append(origem)

    componentes = []
    for caminho in todos:
        if (TEMPLATES / "cotton") not in caminho.parents:
            continue
        texto = fonte[caminho]
        achado = VARS.search(texto)
        props = sorted(set(achado.group(1).split())) if achado else []
        nome = nome_do_cotton(caminho)
        # Arquivo com `_` no começo é peça interna do componente, não se invoca.
        interno = caminho.name.startswith("_")
        componentes.append(
            {
                "nome": nome,
                "arquivo": relativo(caminho),
                "familia": nome.split(".")[0],
                "interno": interno,
                "props": props,
                "slot_anonimo": bool(SLOT_ANONIMO.search(texto)),
                "slots_nomeados": sorted(set(SLOT_NOMEADO.findall(texto))),
                "usado_por": sorted(usos_cotton.get(nome, [])),
                "declara_contrato": achado is not None,
            }
        )

    partials = []
    for caminho in todos:
        if (TEMPLATES / "cotton") in caminho.parents:
            continue
        partes = caminho.relative_to(TEMPLATES).parts
        if not ({"partials", "includes"} & set(partes)):
            continue
        origem = relativo(caminho)
        incluido = sorted(usos_include.get(origem, []))
        referenciado = sorted(set(referencias.get(origem, [])) - set(incluido))
        partials.append(
            {
                "arquivo": origem,
                "app": partes[0],
                "variaveis": variaveis_lidas(fonte[caminho]),
                "incluido_por": incluido,
                "referenciado_por": referenciado,
                "alcancado": bool(incluido or referenciado),
                "inclui": sorted(set(INCLUDE.findall(fonte[caminho]))),
            }
        )

    return {"componentes": componentes, "partials": partials}


def markdown(dados: dict) -> str:
    componentes, partials = dados["componentes"], dados["partials"]
    orfaos = [c for c in componentes if not c["usado_por"] and not c["interno"]]
    sem_dono = [p for p in partials if not p["alcancado"]]

    saida: list[str] = []
    w = saida.append
    w("# Inventário de componentes e partials\n")
    w("**Gerado por `scripts/inventariar_componentes.py`.** Não editar à mão.\n")
    w(
        f"{len(componentes)} componentes cotton e {len(partials)} partials, lidos do "
        "código-fonte. Diferente do `INVENTARIO_PAGINAS.md`, que só enxerga o que "
        "alguma rota renderiza, aqui aparece também a peça que ninguém usa.\n"
    )

    familias = defaultdict(list)
    for c in componentes:
        familias[c["familia"]].append(c)

    w("\n## Componentes cotton\n")
    w("\n| família | componentes | com contrato | sem uso |\n|---|---|---|---|")
    for familia, itens in sorted(familias.items(), key=lambda kv: -len(kv[1])):
        com = sum(1 for c in itens if c["declara_contrato"])
        sem = sum(1 for c in itens if not c["usado_por"] and not c["interno"])
        w(f"| `{familia}` | {len(itens)} | {com} | {sem} |")

    for familia, itens in sorted(familias.items()):
        w(f"\n### Família `{familia}`\n")
        for c in sorted(itens, key=lambda c: c["nome"]):
            marca = " _(interno)_" if c["interno"] else ""
            w(f"\n#### `<c-{c['nome']}>`{marca}\n")
            w(f"`{c['arquivo']}`\n")
            if c["props"]:
                w(f"\n**Props ({len(c['props'])}):** " + ", ".join(f"`{p}`" for p in c["props"]))
            else:
                w("\n**Props:** nenhuma declarada")
            fatias = []
            if c["slot_anonimo"]:
                fatias.append("anônimo")
            fatias += [f"`{s}`" for s in c["slots_nomeados"]]
            if fatias:
                w(f"\n**Slots:** {', '.join(fatias)}")
            if c["usado_por"]:
                amostra = ", ".join(f"`{u}`" for u in c["usado_por"][:5])
                resto = f" … (+{len(c['usado_por']) - 5})" if len(c["usado_por"]) > 5 else ""
                w(f"\n**Usado por {len(c['usado_por'])}:** {amostra}{resto}")
            else:
                w("\n**Usado por:** ninguém")

    w("\n## Partials\n")
    w(
        "Não são renderizáveis isolados: leem o contexto de quem os incluiu. "
        "A coluna de variáveis é heurística — primeiro segmento de `{{ … }}`, "
        "condições de `{% if %}` e alvo de `{% for %}`.\n"
    )
    por_app = defaultdict(list)
    for p in partials:
        por_app[p["app"]].append(p)
    for app, itens in sorted(por_app.items(), key=lambda kv: -len(kv[1])):
        w(f"\n### `{app}` — {len(itens)} partials\n")
        w("\n| partial | variáveis lidas | include | por nome |\n|---|---|---|---|")
        for p in sorted(itens, key=lambda p: p["arquivo"]):
            nome = p["arquivo"].split("/")[-1]
            vs = ", ".join(f"`{v}`" for v in p["variaveis"][:6]) or "—"
            if len(p["variaveis"]) > 6:
                vs += f" … (+{len(p['variaveis']) - 6})"
            inc = len(p["incluido_por"]) or "—"
            ref = len(p["referenciado_por"]) or "—"
            alcance = "" if p["alcancado"] else " **⚠ sem alcance**"
            w(f"| `{nome}` | {vs} | {inc} | {ref}{alcance} |")

    w("\n## Pontas soltas\n")
    w(
        f"\n**{len(orfaos)} componentes sem nenhuma invocação** (candidatos a poda, "
        "com a prova de grep que o `AGENTS.md` §3.6 exige):\n"
    )
    for c in sorted(orfaos, key=lambda c: c["nome"]):
        w(f"- `<c-{c['nome']}>` — `{c['arquivo']}`")
    w(
        f"\n**{len(sem_dono)} partials sem nenhum alcance** — nem `{{% include %}}`, nem "
        "string em prop, nem nome citado no Python:\n"
    )
    for p in sorted(sem_dono, key=lambda p: p["arquivo"]):
        w(f"- `{p['arquivo']}`")

    return "\n".join(saida) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, help="grava o markdown")
    parser.add_argument("--json", type=Path, help="grava os dados crus")
    args = parser.parse_args()

    dados = coletar()
    if args.json:
        args.json.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"json em {args.json}")
    texto = markdown(dados)
    if args.saida:
        args.saida.write_text(texto, encoding="utf-8")
        print(f"markdown em {args.saida}")
    if not args.saida and not args.json:
        sys.stdout.write(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
