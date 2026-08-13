#!/usr/bin/env python3
"""Catraca do `HT-01`: CSS que apaga o foco de teclado sem por nada no lugar.

Por que um script proprio e nao uma regra no `audit_frontend_standards.py`:
aquele e por **linha** e so varre `static/css/*.css` — nao entra em
`components/`, onde mora quase metade do problema. Este e por **bloco**, porque
a pergunta nao e "esta linha zera o outline" e sim "este bloco zera o foco e
**nao** poe nada no lugar". A diferenca importa: `outline: none` acompanhado de
um `box-shadow` visivel e um estilo legitimo, nao um defeito.

Uma armadilha que custou uma versao errada deste script: analisar o corpo do
bloco com um regex do tipo `outline:\\s*(?!none)` **nao funciona**. O `\\s*`
retrocede, casa zero espacos, e o lookahead passa a olhar " none" — que nao
comeca com "none". Resultado: `outline: none` era contado como se fosse um anel
declarado, e o script dizia "0 defeitos" com 52 na frente dele. Aqui a analise e
declaracao a declaracao, com o valor normalizado.

Uso:
  python scripts/audit_foco_visivel.py                   # lista
  python scripts/audit_foco_visivel.py --max 52          # falha se passar
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CSS = RAIZ / "static" / "css"

# So interessa foco de coisa que recebe foco de teclado.
CONTROLE = re.compile(
    r"input|textarea|select|button|field__control|form-control|auth-field"
    r"|picker__input|picker__trigger|__toggle|a\[href\]|tabindex",
    re.I,
)
# Valores que NAO desenham nada.
NULO = {"none", "0", "0px", "transparent", "initial", "unset", "revert"}
BLOCO = re.compile(r"([^{}]*)\{([^{}]*)\}")
COMENTARIO = re.compile(r"/\*.*?\*/", re.S)
# `:focus:not(:focus-visible)` e o idioma CERTO, nao o defeito: diz "sem anel
# para quem clicou com o mouse", e deixa o teclado em paz. Um bloco em que
# *todos* os seletores usam essa forma esta correto e nao entra na conta.
PONTEIRO = re.compile(r":focus:not\(\s*:focus-visible\s*\)")


def declaracoes(corpo: str):
    for parte in corpo.split(";"):
        propriedade, sep, valor = parte.partition(":")
        if not sep:
            continue
        yield (
            propriedade.strip().lower(),
            valor.replace("!important", "").strip().lower(),
        )


def supressores() -> list[tuple[str, str]]:
    """Blocos que apagam o foco de um controle sem substituto no mesmo bloco."""
    achados = []
    for arquivo in sorted(CSS.rglob("*.css")):
        if arquivo.name.endswith(".bundle.css") or arquivo.parent == CSS / "profiles":
            continue
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        for bloco in BLOCO.finditer(texto):
            seletor = COMENTARIO.sub("", bloco.group(1)).strip()
            if "focus" not in seletor.lower() or not CONTROLE.search(seletor):
                continue
            partes = [p.strip() for p in seletor.split(",") if p.strip()]
            if partes and all(PONTEIRO.search(p) for p in partes):
                continue
            decls = list(declaracoes(bloco.group(2)))
            apaga = any(p == "outline" and v in NULO for p, v in decls)
            if not apaga:
                continue
            poe = any(
                p in ("outline", "outline-color", "box-shadow", "border-color", "border")
                and v not in NULO
                for p, v in decls
            )
            if poe:
                continue
            linha = texto[: bloco.start()].count("\n") + 1
            achados.append(
                (f"{arquivo.relative_to(CSS)}:{linha}", " ".join(seletor.split())[:90])
            )
    return achados


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max", type=int, default=None, help="teto; falha se passar")
    args = parser.parse_args(argv)

    achados = supressores()
    for onde, seletor in achados:
        print(f"  {onde:48s} {seletor}")
    print(f"\nBlocos que apagam foco de controle sem substituto: {len(achados)}")

    if args.max is not None and len(achados) > args.max:
        print(
            f"\nERRO: subiu para {len(achados)}; o teto e {args.max}.\n"
            "O piso de `:focus-visible` em base.css/pages/auth.css neutraliza os que ja\n"
            "existem, mas esta conta so desce (AGENTS.md, regra 5): cada bloco novo\n"
            "e um lugar a mais onde alguem vai ter de lembrar do piso.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
