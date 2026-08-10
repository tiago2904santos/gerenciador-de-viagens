#!/usr/bin/env python
"""Resolve a cascata de custom properties nos tres escopos raiz (`UI-03`).

Existe porque **nenhum gate do repositorio protege valor de token**:

  - `medir_divergencia_tema.py` filtra fora todo custom property e toda
    propriedade de cor (`scripts/medir_divergencia_tema.py:27-40`);
  - `audit_paleta.py` compara hex soltos, sem distinguir definicao de uso;
  - `core/tests/test_css_tokens.py` restringe literal de cor, nao local de
    declaracao.

Ou seja: dava para trocar uma cor no meio da E7 e o CI inteiro passar. Este
script foi escrito para provar que a dissolucao do `base/theme.css` nao mexeu
em cor nenhuma, e fica no repositorio porque a E8 (desenho unico) e a E9 (tema
escuro dissolvido em token) vao precisar da mesma prova.

Ele nao e catraca: nao tem teto e nao reprova sozinho. E um instrumento de
diff, para rodar antes e depois de uma mudanca de token:

    python scripts/resolver_tokens_css.py > /tmp/antes.json
    # ...mexer no CSS...
    python scripts/resolver_tokens_css.py > /tmp/depois.json
    diff /tmp/antes.json /tmp/depois.json

Saida: `declarado` (o que cada escopo declara, apos a cascata) e `computado`
(o mesmo com `:root` sobreposto pelo tema e `var()` expandido ate o literal).
E o `computado` que responde "a tela mudou de cor?".
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# o script mora no scratchpad, fora do projeto: a raiz vem do cwd
RAIZ = Path.cwd().resolve()
while not (RAIZ / "manage.py").exists():
    if RAIZ.parent == RAIZ:
        sys.exit("rode a partir da raiz do projeto (onde esta manage.py)")
    RAIZ = RAIZ.parent

CSS = RAIZ / "static" / "css"

# Os tres escopos raiz que carregam token global. Qualquer outro seletor e
# escopo de componente e nao entra na tabela — o que entra aqui e exatamente o
# que muda a pagina inteira.
ESCOPOS = (":root", 'html[data-theme="light"]', 'html[data-theme="dark"]')

COMENTARIO = re.compile(r"/\*.*?\*/", re.S)
DEFINICAO = re.compile(r"(--[\w-]+)\s*:\s*([^;}]+)")


def ordem_de_carga() -> list[Path]:
    """A ordem real: os @import de style.css, depois o resto de SHELL_CSS.

    style.css e a primeira entrada de SHELL_CSS
    (scripts/build_shell_bundles.py:24) e seus @import resolvem antes de
    qualquer regra propria, entao a ordem efetiva e: imports de style.css,
    style.css, e as demais entradas de SHELL_CSS na ordem declarada.
    """
    bundler = (RAIZ / "scripts" / "build_shell_bundles.py").read_text(encoding="utf-8")
    bloco = re.search(r"SHELL_CSS[^=]*=\s*\((.*?)\)", bundler, re.S).group(1)
    shell = [Path(m) for m in re.findall(r'"css/([^"]+)"', bloco)]

    style = CSS / "style.css"
    importados = [
        Path(m) for m in re.findall(r'@import\s+url\("\./([^"]+)"\)', style.read_text(encoding="utf-8"))
    ]

    ordenados = [*importados, Path("style.css"), *[p for p in shell if p != Path("style.css")]]

    # Os arquivos fora do bundle (pages/*.css carregados por template) entram
    # depois, em ordem estavel — nenhum deles define token de escopo raiz hoje,
    # mas se um passar a definir, o retrato precisa enxergar.
    ja = {p.as_posix() for p in ordenados}
    resto = sorted(
        p.relative_to(CSS) for p in CSS.rglob("*.css")
        if "bundle" not in p.name and p.relative_to(CSS).as_posix() not in ja
    )
    return [CSS / p for p in [*ordenados, *resto]]


def blocos(texto: str):
    """(seletor, corpo) de cada bloco de primeiro nivel, sem comentario.

    Ignora at-rules com corpo aninhado (@media, @supports) descendo um nivel:
    o seletor efetivo continua sendo o de dentro, que e o que interessa.
    """
    texto = COMENTARIO.sub("", texto)
    profundidade = 0
    inicio_sel = 0
    sel = ""
    for i, ch in enumerate(texto):
        if ch == "{":
            if profundidade == 0:
                sel = texto[inicio_sel:i].strip()
            profundidade += 1
        elif ch == "}":
            profundidade -= 1
            if profundidade == 0:
                corpo = texto[texto.index("{", inicio_sel) + 1 : i]
                yield sel, corpo
                inicio_sel = i + 1


def normalizar(seletor: str) -> list[str]:
    """Um bloco pode servir varios escopos: `:root, html[data-theme="light"]`."""
    partes = [p.strip() for p in seletor.split(",")]
    achados = []
    for p in partes:
        # aspas simples e duplas sao equivalentes em CSS
        p = p.replace("'", '"')
        for escopo in ESCOPOS:
            if p == escopo:
                achados.append(escopo)
    return achados


def resolver() -> dict[str, dict[str, str]]:
    tabela: dict[str, dict[str, str]] = {e: {} for e in ESCOPOS}
    for arquivo in ordem_de_carga():
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for seletor, corpo in blocos(texto):
            escopos = normalizar(seletor)
            if not escopos:
                continue
            for nome, valor in DEFINICAO.findall(corpo):
                valor = " ".join(valor.split())
                for escopo in escopos:
                    # a ultima definicao vence, que e a regra da cascata para
                    # seletores de mesma especificidade
                    tabela[escopo][nome] = valor
    return tabela


VAR = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,\s*(.*?))?\)$|var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*(?:\([^()]*\)[^()]*)*))?\)")


def expandir(valor: str, tabela: dict[str, str], visitados: frozenset[str] = frozenset()) -> str:
    """Substitui `var(--x, fallback)` pelo valor de `--x` no mesmo escopo.

    Custom property resolve na hora do USO, contra a tabela final do elemento —
    por isso a expansao roda depois da cascata, nunca durante. Ciclo devolve o
    texto cru em vez de estourar a pilha: CSS trata como invalido, e o que este
    script precisa e so que antes e depois sejam iguais.
    """

    def troca(m: re.Match) -> str:
        nome = m.group(1) or m.group(3)
        fallback = m.group(2) if m.group(1) else m.group(4)
        if nome in visitados:
            return m.group(0)
        if nome in tabela:
            return expandir(tabela[nome], tabela, visitados | {nome})
        if fallback is not None:
            return expandir(fallback.strip(), tabela, visitados | {nome})
        return m.group(0)

    anterior = None
    atual = valor
    for _ in range(20):  # profundidade medida hoje e 4; 20 e folga com fim garantido
        anterior, atual = atual, VAR.sub(troca, atual)
        if atual == anterior:
            break
    return " ".join(atual.split())


def efetivas(tabela: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """O que o elemento raiz REALMENTE computa em cada tema.

    `html[data-theme="light"]` (0,1,1) vence `:root` (0,1,0), mas nao apaga: o
    que so existe em `:root` continua valendo. Entao o efetivo de um tema e
    `:root` sobreposto pelo bloco do tema, e so depois o `var()` expande.
    """
    saida = {}
    for tema in ('html[data-theme="light"]', 'html[data-theme="dark"]'):
        combinado = {**tabela[":root"], **tabela[tema]}
        saida[tema] = {k: expandir(v, combinado) for k, v in sorted(combinado.items())}
    # o fallback sem JS: so `:root`
    saida["sem-tema (fallback)"] = {
        k: expandir(v, tabela[":root"]) for k, v in sorted(tabela[":root"].items())
    }
    return saida


def main() -> None:
    tabela = resolver()
    declarado = {escopo: dict(sorted(v.items())) for escopo, v in tabela.items()}
    computado = efetivas(tabela)
    print(json.dumps(
        {
            "resumo_declarado": {e: len(v) for e, v in declarado.items()},
            "resumo_computado": {e: len(v) for e, v in computado.items()},
            "declarado": declarado,
            "computado": computado,
        },
        indent=2,
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
