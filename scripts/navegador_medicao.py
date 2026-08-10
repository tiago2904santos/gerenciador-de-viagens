#!/usr/bin/env python
"""Sobe o Chromium das reguas de frontend, aqui e no CI (`NOVO-84`).

`playwright.chromium.launch()` procura um build fixo, casado com a versao do
pacote pip. No CI isso funciona porque `tests.yml:391` roda
`python -m playwright install --with-deps chromium` e baixa o build certo.

Na sessao remota que o proprio projeto monta para os agentes, nao: a imagem traz
o Chromium ja instalado em `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, com um
build **diferente** do que o pacote espera, e o ambiente pede explicitamente para
nao rodar `playwright install`. O launch morre com

    Executable doesn't exist at .../chromium_headless_shell-<N>/...

e as duas reguas da E0 ficam sem rodar — justamente as que a E8 usa como prova.

Este modulo tenta o caminho normal primeiro e so cai para o build instalado
quando o esperado nao existe. No CI o primeiro caminho sempre funciona, entao o
comportamento la nao muda.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


# O headless_shell e mais leve, mas nem toda imagem o traz; o `chrome` completo
# serve para as duas reguas, que so leem estilo computado e uso de CSS.
CANDIDATOS = (
    "chromium-{n}/chrome-linux/chrome",
    "chromium_headless_shell-{n}/chrome-linux/headless_shell",
)


def _builds_instalados(raiz: Path) -> list[int]:
    numeros = set()
    for filho in raiz.iterdir():
        achado = re.fullmatch(r"chromium(?:_headless_shell)?-(\d+)", filho.name)
        if achado:
            numeros.add(int(achado.group(1)))
    return sorted(numeros, reverse=True)


def executavel_instalado() -> str | None:
    """Caminho de um Chromium que existe de fato, ou `None`.

    Prefere o build mais novo entre os instalados — quando ha mais de um, o mais
    novo e o que a imagem colocou por ultimo.
    """
    bruto = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if not bruto:
        return None
    raiz = Path(bruto)
    if not raiz.is_dir():
        return None
    for numero in _builds_instalados(raiz):
        for molde in CANDIDATOS:
            caminho = raiz / molde.format(n=numero)
            if caminho.is_file() and os.access(caminho, os.X_OK):
                return str(caminho)
    return None


def abrir_chromium(playwright, *, headless: bool = True):
    """`chromium.launch()` com queda para o build instalado no contexto remoto."""
    try:
        return playwright.chromium.launch(headless=headless)
    except Exception as erro:
        caminho = executavel_instalado()
        if not caminho or "doesn't exist" not in str(erro):
            raise
        return playwright.chromium.launch(headless=headless, executable_path=caminho)
