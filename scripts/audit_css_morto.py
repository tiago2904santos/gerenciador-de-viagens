#!/usr/bin/env python3
"""CSS morto: regra cuja classe nenhum template, JS ou Python emite (NOVO-30 fase 5).

O QUE CONTA COMO MORTO

Uma regra e morta quando ela tem ao menos uma classe no seletor e **nenhuma**
das suas classes e emitida pelo produto. Basta uma classe viva para a regra
inteira ficar de pe — `.cv-btn .algo-morto` continua valendo porque `.cv-btn`
existe e o seletor pode casar amanha com outro filho.

Regra sem classe nenhuma (`article > p`, `:root`, `[hidden]`) nunca e apagada:
nao ha como decidir pelo nome.

A ARMADILHA DO NOME COMPOSTO

`f"cv-btn--{variante}"` nunca aparece inteiro no codigo — so o prefixo
`cv-btn--`. Por isso uma classe tambem conta como viva quando qualquer prefixo
dela terminado em `--` ou `__` aparece no codigo, e quando o codigo emite um
filho ou modificador dela. O vies e deliberado: **falso negativo (deixar CSS
morto de pe) custa bytes; falso positivo (apagar estilo em uso) apaga a tela** —
e nao quebra teste nenhum, porque a pagina responde 200 do mesmo jeito.

POR QUE UM PARSER E NAO UMA EXPRESSAO REGULAR

A versao anterior desta analise usava regex com lookbehind em `}`. Ela nao
enxergava a primeira regra de dentro de cada `@media`, o que deixava residuo
incoerente: a regra base apagada e o modificador dela de pe, dentro do media
query logo abaixo. Aqui a varredura conta chaves e trata bloco aninhado.

Este arquivo se exclui da varredura de fontes: ele fala de nome de classe em
prosa, e sem a exclusao qualquer classe citada aqui viraria "viva" — o auditor
inocentando o que ele mesmo deveria acusar.

`@keyframes` fica de fora — `0%`/`to` nao sao seletores de classe — e um
`@media` que fica vazio depois da poda vai junto.

Uso:
    python scripts/audit_css_morto.py                  # relatorio
    python scripts/audit_css_morto.py --max-regras 0   # catraca (CI)
    python scripts/audit_css_morto.py --aplicar        # remove
    python scripts/audit_css_morto.py --lista saida.txt
"""

from __future__ import annotations

import argparse
import collections
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
IGNORAR = {"staticfiles", ".venv", "legacy", "node_modules", "__pycache__", ".git"}
# Extensoes que podem emitir classe. `.md`/`.txt` ficam de fora de proposito:
# documento de auditoria *cita* nome de classe em prosa sem renderizar nada, e
# incluir a documentacao manteria viva toda classe ja descrita — inclusive a
# lista de classes mortas deste proprio auditor.
FONTES_DE_CLASSE = (".html", ".js", ".py", ".json", ".svg", ".xml")
# Gerado por scripts/build_shell_bundles.py a partir dos outros arquivos.
GERADOS = {"shell.bundle.css"}

_AT_SEM_SELETOR = re.compile(r"@(keyframes|font-face|counter-style|property|page)\b", re.I)
_CLASSE = re.compile(r"\.(-?[a-zA-Z_][\w-]*)")


def tokens_do_produto() -> set[str]:
    tk: set[str] = set()
    for f in RAIZ.rglob("*"):
        if not f.is_file() or f.suffix not in FONTES_DE_CLASSE:
            continue
        if any(p in IGNORAR for p in f.parts) or f == pathlib.Path(__file__).resolve():
            continue
        tk |= set(re.findall(r"[\w-]+", f.read_text(encoding="utf-8", errors="replace")))
    return tk


def viva(classe: str, tk: set[str]) -> bool:
    if classe in tk:
        return True
    # BEM: se o codigo emite um filho ou modificador (`roteiro-editor--oficio`),
    # o bloco base (`roteiro-editor`) costuma vir junto no mesmo `class=`.
    if any(t.startswith(classe) and len(t) > len(classe) and t[len(classe)] in "-_"
           for t in tk):
        return True
    # Composicao: `cv-btn--primary` vive se o codigo tem `cv-btn--` ou `cv-btn`.
    for corte in ("--", "__"):
        i = classe.rfind(corte)
        while i > 0:
            if classe[: i + len(corte)] in tk or classe[:i] in tk:
                return True
            i = classe.rfind(corte, 0, i)
    return False


def fontes_css() -> list[pathlib.Path]:
    return [f for f in sorted((RAIZ / "static/css").rglob("*.css"))
            if f.name not in GERADOS]


def _sem_comentario(texto: str) -> str:
    """Mesmo comprimento, comentarios virando espaco — offsets continuam validos."""
    return re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), texto, flags=re.S)


def regras(texto: str):
    """(inicio, fim, seletor, profundidade) de cada regra de estilo do arquivo.

    Percorre contando chaves. Um bloco cujo prelude comeca com `@` e container
    (`@media`, `@supports`) ou nao tem seletor de classe (`@keyframes`); no
    primeiro caso desce, no segundo pula o bloco inteiro.
    """
    limpo = _sem_comentario(texto)
    i, n, inicio_prelude, profundidade = 0, len(limpo), 0, 0
    while i < n:
        c = limpo[i]
        if c == "{":
            prelude = limpo[inicio_prelude:i].strip()
            if prelude.startswith("@"):
                if _AT_SEM_SELETOR.match(prelude):
                    i = _fecha(limpo, i)          # pula o bloco inteiro
                    inicio_prelude = i
                    continue
                profundidade += 1                  # @media/@supports: desce
                i += 1
                inicio_prelude = i
                continue
            fim = _fecha(limpo, i)
            yield inicio_prelude, fim, prelude, profundidade
            i = fim
            inicio_prelude = i
            continue
        if c == "}":
            profundidade = max(0, profundidade - 1)
            i += 1
            inicio_prelude = i
            continue
        if c == ";" and profundidade >= 0 and limpo[inicio_prelude:i].strip().startswith("@"):
            i += 1                                 # @import/@charset
            inicio_prelude = i
            continue
        i += 1


def _fecha(texto: str, i: int) -> int:
    """Indice logo depois do `}` que fecha a chave aberta em `i`."""
    nivel = 0
    while i < len(texto):
        if texto[i] == "{":
            nivel += 1
        elif texto[i] == "}":
            nivel -= 1
            if nivel == 0:
                return i + 1
        i += 1
    return len(texto)


def analisa():
    tk = tokens_do_produto()
    mortas: collections.Counter = collections.Counter()
    alvo: dict[pathlib.Path, list[tuple[int, int]]] = collections.defaultdict(list)
    for f in fontes_css():
        texto = f.read_text(encoding="utf-8")
        for ini, fim, seletor, _prof in regras(texto):
            classes = _CLASSE.findall(seletor)
            if not classes or any(viva(c, tk) for c in classes):
                continue
            alvo[f].append((ini, fim))
            for c in classes:
                mortas[c] += 1
    return alvo, mortas


def poda(texto: str, faixas: list[tuple[int, int]]) -> str:
    partes, pos = [], 0
    for a, b in faixas:
        partes.append(texto[pos:a])
        pos = b
    partes.append(texto[pos:])
    novo = "".join(partes)
    # `@media` que ficou sem nenhuma regra dentro nao tem por que existir.
    anterior = None
    while anterior != novo:
        anterior = novo
        novo = re.sub(r"@[a-zA-Z-]+[^{}]*\{\s*\}\s*", "", novo)
    return re.sub(r"\n{3,}", "\n\n", novo)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--max-regras", type=int, default=None,
                   help="falha se houver mais regras mortas que este teto")
    p.add_argument("--aplicar", action="store_true", help="remove as regras mortas")
    p.add_argument("--lista", help="grava 'ocorrencias<TAB>classe' neste arquivo")
    args = p.parse_args()

    alvo, mortas = analisa()
    total = sum(len(v) for v in alvo.values())
    linhas = sum(t[a:b].count("\n") + 1
                 for f, faixas in alvo.items()
                 for t in [f.read_text(encoding="utf-8")] for a, b in faixas)
    print(f"regras mortas: {total} em {len(alvo)} arquivos (~{linhas} linhas) "
          f"· classes distintas: {len(mortas)}")
    for f, faixas in sorted(alvo.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(faixas):4d}  {f.relative_to(RAIZ)}")

    if args.lista:
        pathlib.Path(args.lista).write_text(
            "\n".join(f"{n}\t{c}" for c, n in sorted(mortas.items())) + "\n")

    if args.aplicar:
        for f, faixas in alvo.items():
            f.write_text(poda(f.read_text(encoding="utf-8"), faixas), encoding="utf-8")
        print("APLICADO")
        return 0

    if args.max_regras is not None and total > args.max_regras:
        print(f"FALHA: teto e {args.max_regras}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
