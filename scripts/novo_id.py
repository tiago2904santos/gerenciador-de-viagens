#!/usr/bin/env python
"""Gera um ID de defeito novo sem depender de contador compartilhado (`NOVO-29`)."""

from __future__ import annotations

import secrets
from datetime import UTC
from datetime import datetime


def gerar_id(*, instante: datetime | None = None, sufixo: str | None = None) -> str:
    instante = instante or datetime.now(UTC)
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=UTC)
    instante = instante.astimezone(UTC)
    sufixo = sufixo or secrets.token_hex(6)
    if len(sufixo) != 12 or any(char not in "0123456789abcdef" for char in sufixo):
        raise ValueError("o sufixo deve ter doze caracteres hexadecimais minúsculos")
    return f"NOVO-{instante:%Y%m%d-%H%M%S}-{sufixo}"


def main() -> int:
    print(gerar_id())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
