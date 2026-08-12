#!/usr/bin/env python3
"""`DB-02`: quantas linhas existentes violariam o `NOT NULL` de `area`.

Existe pelo limite 4 do `AGENTS.md` — "não crie migração sem checar dados".
Cada migração `*_area_obrigatoria` traz a própria query no docstring, mas oito
queries soltas em oito arquivos não é procedimento operável: **este script é o
procedimento**. Rode contra o banco de produção antes do deploy; ele sai com
código 1 se qualquer tabela do grupo operacional tiver linha com
`area_id IS NULL`, e diz quantas e onde.

A lista é a mesma verdade que o deploy usa: `core.checks._OPERATIONAL_MODELS`,
os oito modelos que o `core.E001` bloqueia. Não redigitar a lista aqui é o que
mantém script e check medindo a mesma coisa — se o grupo 1 crescer, os dois
crescem juntos.

Linha encontrada? `python manage.py backfill_legacy_areas --area SIGLA
--commit`, com backup antes (o `deploy.yml` já o faz sozinho, antes do
checkout). O `check --deploy` do `NOVO-12` roda esta mesma conta no início de
todo deploy, então a migração nunca encontra NULL — este script serve para
medir fora do deploy, sem esperar um.

Uso:
    python scripts/validar_not_null_db02.py                  # banco do settings
    DJANGO_SETTINGS_MODULE=config.settings.prod python scripts/validar_not_null_db02.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _preparar_django():
    """Sobe o registro de apps. `test` como padrão, pela mesma razão do `DB-07`."""
    sys.path.insert(0, str(RAIZ))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
    import django

    django.setup()


def main() -> int:
    _preparar_django()

    from django.apps import apps

    from core.checks import _OPERATIONAL_MODELS

    violacoes = 0
    print("== DB-02: linhas com area_id IS NULL no grupo operacional ==")
    for label in _OPERATIONAL_MODELS:
        modelo = apps.get_model(label)
        # `_base_manager` de propósito: nenhum recorte de área nem filtro de
        # manager pode esconder linha desta conta.
        quantidade = modelo._base_manager.filter(area__isnull=True).count()
        situacao = "OK" if not quantidade else "VIOLA"
        print(f"  {modelo._meta.db_table:40s} {quantidade:6d}  {situacao}")
        violacoes += quantidade

    if violacoes:
        print(
            f"\nERRO: {violacoes} linha(s) sem área. Rode "
            "`python manage.py backfill_legacy_areas --area SIGLA --commit` "
            "com backup antes; a migração NOT NULL falharia agora.",
        )
        return 1
    print("\nNenhuma violação: as oito migrações `*_area_obrigatoria` aplicam limpas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
