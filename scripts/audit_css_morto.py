#!/usr/bin/env python3
"""Catraca do `UI-01`: bloco de CSS cujo seletor so cita classe que ninguem usa.

O `UI-01` mediu 981 blocos mortos e 168 KB. A poda foi feita a mao, arquivo por
arquivo, com prova de grep em cada PR. Este script existe para o depois: sem
catraca, a conta volta a subir sozinha, porque **apagar markup nao apaga o CSS
que o estilizava** — foi exatamente assim que os 981 nasceram. Cada refactor de
template deixa o rastro, ninguem ve, e um ano depois sao 168 KB de novo.

## O que conta como morto

Um bloco entra na conta quando **todas** as classes do seletor faltam no corpus
— templates, JS, Python, JSON e Markdown do repositorio inteiro. Basta uma
classe viva para o bloco inteiro ficar de fora: `.cv-card .lixo` continua vivo
enquanto `cv-card` existir, porque apagar esse bloco mudaria a aparencia do
`.cv-card`.

Seletor sem classe nenhuma (`body`, `:root`, `[data-state="x"]`) nao entra: a
pergunta deste script e sobre classe, e chutar sobre seletor de atributo foi um
buraco declarado no `UI-01` que continua declarado aqui.

## Por que classe citada por outro CSS conta como VIVA aqui

Ela e morta de verdade — nenhum template a usa —, mas apagar so um lado deixa
regra orfa do outro. A poda dessas foi feita por familia, tocando todos os
arquivos de uma vez. Para a catraca, contar so o lado unico mantem o numero
estavel: um PR que apaga metade de uma familia nao faz o numero *descer* e dar
a impressao de progresso.

## O risco deste script, e para que lado ele erra

Classe montada em tempo de execucao (`` `cv-chip--${tom}` ``) nao aparece
inteira no corpus. Se o prefixo nao estiver em `PREFIXOS_DINAMICOS`, o script
conta uma classe **viva** como morta.

Isso e ruim, mas erra para o lado seguro: o numero **sobe**, a catraca reprova o
PR e alguem vai olhar. O contrario — apagar CSS vivo — este script nao faz,
porque ele nao apaga nada. Ele conta.

Uso:
  python scripts/audit_css_morto.py             # lista por arquivo
  python scripts/audit_css_morto.py --detalhe   # lista classe por classe
  python scripts/audit_css_morto.py --max 107   # falha se passar
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CSS = RAIZ / "static" / "css"

#: Bundles sao concatenacao do que ja esta sob analise; conta-los dobraria tudo.
IGNORA_ARQUIVO = {"shell.bundle.css", "shell.bundle.js"}
IGNORA_DIR = {".venv", "node_modules", ".git", "staticfiles", "htmlcov", "__pycache__"}
SUFIXOS_CORPUS = {".html", ".js", ".py", ".txt", ".md", ".json", ".mjs"}

#: Prefixos de classe montada em tempo de execucao — o pedaco que aparece no
#: codigo antes da interpolacao. Sao 46, derivados no `UI-01` com duas correcoes
#: de metodo registradas no catalogo:
#:
#: 1. a primeira varredura so procurava `` `${` `` ancorado na aspa de abertura,
#:    e perdeu concatenacao com `+` e interpolacao no meio da string;
#: 2. a segunda tratava qualquer vizinhanca de `{% if %}` como composicao de
#:    sufixo, mas `class="x{% if c %} is-y{% endif %}"` emite `" is-y"` COM
#:    espaco: e classe separada, nao sufixo. Exigir que a interpolacao **cole**
#:    no token derrubou a lista de 160 para 41.
#:
#: Uma classe que comeca com qualquer um destes conta como viva. E deliberado que
#: a regra seja generosa: o custo de um falso vivo e um bloco a menos na conta;
#: o de um falso morto e alguem apagar estilo que existe.
PREFIXOS_DINAMICOS = (
    "alert-",
    "alert--",
    "app-wizard",
    "area-quick-add__toggle--",
    "asgn-fontchip--",
    "cv-action-menu__item-icon--",
    "cv-btn--",
    "cv-chip--",
    "cv-custom-select--disabled",
    "cv-custom-select--error",
    "cv-dialog__header--",
    "cv-dialog__icon--",
    "cv-field-side-action--",
    "cv-footer-action--",
    "cv-form-block--",
    "cv-icon-btn--",
    "cv-notice--",
    "cv-pendencias--",
    "cv-person-list--n",
    "cv-record-card--",
    "cv-record-card__info-value--wrap",
    "cv-search-picker--",
    "destination-row--single",
    "empty-state--",
    "is-checked",
    "is-disabled",
    "is-loading",
    "is-selected",
    "leaflet-base-layers_",
    "leaflet-marker-",
    "oficio-documentos-route-card--trechos-",
    "oficio-viatura-reason--",
    "prestacao-card-group--",
    "pt-resumo-grid--3",
    "related-route-item",
    "roteiro-list-card--faixa-",
    "roteiro-list-card--layout-",
    "roteiro-list-card--status-",
    "roteiro-list-card--trechos-",
    "sidebar-link--nested",
    "status-chip--",
    "ui-lab-status-pill--",
    "usuario-quick-add__toggle--",
    "viatura-sugestao-badge--",
    "viatura-sugestao-chip",
)

COMENTARIO = re.compile(r"/\*.*?\*/", re.S)
CLASSE = re.compile(r"\.(-?[_a-zA-Z][\w-]*)")


def corpus() -> str:
    """Todo o codigo do projeto, menos o historico datado e os bundles.

    **Este arquivo fica de fora do proprio corpus.** Ele cita nomes de classe na
    documentacao e em `PREFIXOS_DINAMICOS`; incluir-se faria cada nome citado
    contar como "usado em codigo" e sumir da conta. Uma classe morta ficaria viva
    por aparecer no auditor que deveria acusa-la.
    """
    eu = Path(__file__).resolve()
    partes = []
    for caminho in RAIZ.rglob("*"):
        if not caminho.is_file() or caminho.suffix not in SUFIXOS_CORPUS:
            continue
        if set(caminho.parts) & IGNORA_DIR or caminho.name in IGNORA_ARQUIVO:
            continue
        if "historico" in caminho.parts or caminho.resolve() == eu:
            continue
        partes.append(caminho.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(partes)


def blocos(css: str):
    """(inicio, fim, seletor) de cada bloco, respeitando aninhamento de `@media`."""
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j == -1:
            return
        profundidade, k = 1, j + 1
        while k < n and profundidade:
            if css[k] == "{":
                profundidade += 1
            elif css[k] == "}":
                profundidade -= 1
            k += 1
        yield i, k, COMENTARIO.sub(" ", css[i:j]).strip()
        i = k


def imports_quebrados() -> list[tuple[str, str]]:
    """`@import url("./x.css")` apontando para arquivo que nao existe.

    Um `@import` pendurado nao aparece em nenhum dos gates de CSS deste projeto:
    a poda olha bloco, o auditor de front olha linha, e nenhum dos dois resolve
    caminho. Quem pega e o `collectstatic` de producao — porque o WhiteNoise
    reescreve URL dentro de CSS e reprova com `MissingFileError` —, e ele roda so
    no passo 14 do CI, depois de tudo que interessa ja ter passado.

    Foi assim que o `NOVO-49` chegou vermelho: `dashboard.css` foi apagado com
    prova de grep em templates, JS e Python, e ninguem olhou o `@import` do
    `style.css`, que e CSS citando CSS.
    """
    quebrados = []
    for caminho in sorted(CSS.rglob("*.css")):
        if caminho.name in IGNORA_ARQUIVO:
            continue
        for alvo in re.findall(
            r"""@import\s+url\(\s*["']([^"')]+)["']\s*\)""",
            caminho.read_text(encoding="utf-8"),
        ):
            if alvo.startswith(("http://", "https://", "//", "data:")):
                continue
            if not (caminho.parent / alvo).resolve().is_file():
                quebrados.append((str(caminho.relative_to(RAIZ)), alvo))
    return quebrados


def mortos():
    codigo = corpus()
    arquivos = sorted(p for p in CSS.rglob("*.css") if p.name not in IGNORA_ARQUIVO)
    limpo = {p: COMENTARIO.sub(" ", p.read_text(encoding="utf-8")) for p in arquivos}
    cache: dict[str, bool] = {}

    def viva_no_codigo(classe: str) -> bool:
        if classe not in cache:
            cache[classe] = classe in codigo or any(
                classe.startswith(p) and classe != p for p in PREFIXOS_DINAMICOS
            )
        return cache[classe]

    def viva_em_outro_css(classe: str, alvo: Path) -> bool:
        return any(f".{classe}" in limpo[p] for p in arquivos if p != alvo)

    achados = []
    for caminho in arquivos:
        texto = caminho.read_text(encoding="utf-8")
        for inicio, fim, seletor in blocos(texto):
            if seletor.startswith("@"):
                continue
            classes = set(CLASSE.findall(seletor))
            if not classes or any(viva_no_codigo(c) for c in classes):
                continue
            if any(viva_em_outro_css(c, caminho) for c in classes):
                continue
            achados.append(
                (
                    str(caminho.relative_to(RAIZ)),
                    " ".join(seletor.split())[:90],
                    sorted(classes),
                    fim - inicio,
                )
            )
    return achados


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max", type=int, default=None, help="teto; falha se passar")
    parser.add_argument("--detalhe", action="store_true", help="lista bloco a bloco")
    args = parser.parse_args(argv)

    quebrados = imports_quebrados()
    for arquivo, alvo in quebrados:
        print(f"  IMPORT QUEBRADO  {arquivo} -> {alvo}", file=sys.stderr)

    achados = mortos()
    por_arquivo: dict[str, list] = {}
    for arquivo, seletor, classes, tamanho in achados:
        por_arquivo.setdefault(arquivo, []).append((seletor, classes, tamanho))

    for arquivo in sorted(por_arquivo, key=lambda a: -sum(x[2] for x in por_arquivo[a])):
        itens = por_arquivo[arquivo]
        peso = sum(x[2] for x in itens) / 1024
        print(f"  {arquivo:52s} {len(itens):4d} blocos  {peso:6.1f} KB")
        if args.detalhe:
            for seletor, _, _ in itens:
                print(f"      {seletor}")

    peso_total = sum(x[3] for x in achados) / 1024
    print(f"\nBlocos de CSS sem nenhuma classe viva: {len(achados)} ({peso_total:.1f} KB)")

    if quebrados:
        print(
            f"\nERRO: {len(quebrados)} `@import` apontando para arquivo inexistente.\n"
            "Isto reprova o `collectstatic` de producao (WhiteNoise, MissingFileError),\n"
            "mas so no passo 14 do CI. Aqui ele custa um segundo.",
            file=sys.stderr,
        )
        return 1

    if args.max is not None and len(achados) > args.max:
        print(
            f"\nERRO: subiu para {len(achados)}; o teto e {args.max}.\n"
            "Esta conta so desce (AGENTS.md, regra 5). Se o seu PR apagou markup,\n"
            "apague junto o CSS que o estilizava — foi acumular esse rastro que\n"
            "produziu os 168 KB do UI-01. Se a classe e montada em tempo de\n"
            "execucao, o prefixo dela vai em PREFIXOS_DINAMICOS, com a linha do\n"
            "codigo que a monta citada no PR.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
