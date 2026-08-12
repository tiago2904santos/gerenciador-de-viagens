#!/usr/bin/env python3
"""Catraca da paleta: cores perceptualmente duplicadas no CSS.

Duas cores separadas por menos de ΔE2000 2,5 sao a MESMA decisao de design
escrita duas vezes. O sistema tinha 464 valores hex distintos e 255 deles eram
duplicata de outro — 26 brancos, 25 azuis palidos, 16 azuis-marinho.

O problema nao e o peso: e que ninguem consegue manter um sistema com 464 cores.
Trocar "o azul do cabecalho" vira uma cacada.

## O que este script NAO faz

Ele nao junta cores que distinguem ESTADO. Se a mesma propriedade, no mesmo
seletor-base, recebe duas cores diferentes em variantes (`:hover`, `.is-ativo`,
`--modificador`), essas duas estao trabalhando e ficam. Colapsa-las apagaria o
feedback de interacao sem nenhum teste reprovar: a pagina continua renderizando,
so para de responder ao mouse. Sao 207 pares protegidos assim.

Uso:
  python scripts/audit_paleta.py            # lista os grupos
  python scripts/audit_paleta.py --max 0    # falha se houver duplicata nova
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CSS = RAIZ / "static" / "css"
IGNORA = {"shell.bundle.css", "shell.form-components.bundle.css"}
CORTE = 2.5

RE_HEX = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
RE_BLOCO = re.compile(r"([^{}]+)\{([^{}]*)\}")
RE_ESTADO = re.compile(
    r"(:hover|:focus(-visible|-within)?|:active|:checked|:disabled|:target"
    r"|\.is-[\w-]+|\.has-[\w-]+|\[aria-[^\]]*\]|\[data-[^\]]*\]|--[\w-]+)"
)
RE_DECL = re.compile(r"([a-z-]+)\s*:\s*([^;]+)")


def normaliza(h: str) -> str:
    h = h.lower().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h


def lab(h: str):
    h = h.lstrip("#")
    def lin(c):
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(int(h[i : i + 2], 16)) for i in (0, 2, 4))
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    def f(t):
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t + 16 / 116)
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(c1: str, c2: str) -> float:
    """CIEDE2000."""
    L1, a1, b1 = lab(c1)
    L2, a2, b2 = lab(c2)
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cb**7 / (Cb**7 + 25**7))) if Cb else 0.5
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if (a1p or b1) else 0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if (a2p or b2) else 0
    dLp, dCp = L2 - L1, C2p - C1p
    if C1p * C2p == 0:
        dhp = 0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    else:
        dhp = h2p - h1p - 360 if h2p > h1p else h2p - h1p + 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp) / 2)
    Lbp, Cbp = (L1 + L2) / 2, (C1p + C2p) / 2
    if C1p * C2p == 0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbp = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hbp = (h1p + h2p + 360) / 2
    else:
        hbp = (h1p + h2p - 360) / 2
    T = (
        1
        - 0.17 * math.cos(math.radians(hbp - 30))
        + 0.24 * math.cos(math.radians(2 * hbp))
        + 0.32 * math.cos(math.radians(3 * hbp + 6))
        - 0.20 * math.cos(math.radians(4 * hbp - 63))
    )
    dTh = 30 * math.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(Cbp**7 / (Cbp**7 + 25**7)) if Cbp else 0
    Sl = 1 + (0.015 * (Lbp - 50) ** 2) / math.sqrt(20 + (Lbp - 50) ** 2)
    Sc = 1 + 0.045 * Cbp
    Sh = 1 + 0.015 * Cbp * T
    Rt = -math.sin(math.radians(2 * dTh)) * Rc
    return math.sqrt(
        (dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2
        + Rt * (dCp / Sc) * (dHp / Sh)
    )


def pares_de_estado() -> set:
    """Cores que convivem na mesma propriedade do mesmo seletor-base."""
    por_base: dict = {}
    for caminho in sorted(CSS.rglob("*.css")):
        if caminho.name in IGNORA:
            continue
        texto = re.sub(r"/\*.*?\*/", " ", caminho.read_text(encoding="utf-8"), flags=re.S)
        for sel, corpo in RE_BLOCO.findall(texto):
            base = RE_ESTADO.sub("", sel).strip()
            if not base:
                continue
            for prop, valor in RE_DECL.findall(corpo):
                achadas = {normaliza(x) for x in RE_HEX.findall(valor)}
                if achadas:
                    por_base.setdefault((base, prop), set()).update(achadas)
    pares = set()
    for cores in por_base.values():
        lista = sorted(cores)
        for i in range(len(lista)):
            for j in range(i + 1, len(lista)):
                pares.add((lista[i], lista[j]))
                pares.add((lista[j], lista[i]))
    return pares


def duplicatas():
    usos: dict = {}
    for caminho in sorted(CSS.rglob("*.css")):
        if caminho.name in IGNORA:
            continue
        for m in RE_HEX.findall(caminho.read_text(encoding="utf-8")):
            cor = normaliza(m)
            usos[cor] = usos.get(cor, 0) + 1
    protegidos = pares_de_estado()
    cores = sorted(usos, key=lambda c: -usos[c])
    achados, usada = [], set()
    for cor in cores:
        if cor in usada:
            continue
        usada.add(cor)
        grupo = []
        for outra in cores:
            if outra in usada or (cor, outra) in protegidos:
                continue
            d = delta_e(cor, outra)
            if d <= CORTE:
                grupo.append((outra, usos[outra], round(d, 2)))
                usada.add(outra)
        if grupo:
            achados.append((cor, usos[cor], grupo))
    return achados


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max", type=int, default=None, help="teto; falha se passar")
    args = ap.parse_args(argv)

    achados = duplicatas()
    for canonico, n, grupo in achados:
        dups = " ".join(f"{c}({u}x,d{d})" for c, u, d in grupo)
        print(f"  {canonico} ({n}x)  <-  {dups}")
    total = sum(len(g) for _, _, g in achados)
    print(f"\nCores duplicadas por percepcao (deltaE2000 <= {CORTE}): {total}")

    if args.max is not None and total > args.max:
        print(
            f"\nERRO: subiu para {total}; o teto e {args.max}.\n"
            "Voce escreveu uma cor que ja existe no sistema com outro valor hex.\n"
            "Use a que ja esta la — o script mostra qual e, na coluna da esquerda.\n"
            "Se a diferenca for proposital (um estado novo), ela precisa aparecer\n"
            "no mesmo seletor-base da cor original para o script reconhece-la.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
