#!/usr/bin/env python3
"""`DB-07`: quantas linhas existentes violariam cada constraint nova.

Existe pelo limite 4 do `AGENTS.md` — "não crie migração sem checar dados". As
migrações trazem a query de cada uma no docstring, mas 24 queries soltas em sete
arquivos não é procedimento operável: **este script é o procedimento**. Rode
contra o banco de produção antes do deploy; ele sai com código 1 se qualquer
linha existente violar, e diz quantas e em qual campo.

O `ALTER TABLE ... ADD CONSTRAINT` aborta a migração inteira com uma linha só
fora da regra, e a mensagem do PostgreSQL nomeia a constraint mas **não** os
registros. Achar as linhas depois de o deploy ter falhado é pior do que antes.

A lista aqui é derivada da mesma verdade que os modelos — as constraints são
lidas de `Model._meta.constraints` por introspecção, não redigitadas. Uma
constraint nova nos modelos entra nesta régua sozinha; foi a única forma de a
régua não envelhecer em relação ao que ela mede.

Uso:
    python scripts/validar_constraints_db07.py                  # banco do settings
    DJANGO_SETTINGS_MODULE=config.settings.prod python scripts/validar_constraints_db07.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _preparar_django():
    """Sobe o registro de apps. `test` como padrão, pela mesma razão do `BE-09`.

    `config.settings.dev` faz `load_dotenv()` e estoura no import sem
    `FIELD_ENCRYPTION_KEYS` (`config/settings/dev.py:41`) — em produção quem roda
    isto passa `DJANGO_SETTINGS_MODULE=config.settings.prod` explicitamente, com
    o `.env` no lugar.
    """
    sys.path.insert(0, str(RAIZ))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
    import django

    django.setup()


def _violacoes(modelo, constraint):
    """Quantas linhas o `CHECK` reprovaria, com a semântica de nulo do SQL.

    Anota a condição como booleano e filtra por `False` **explícito**. É a única
    forma de reproduzir o `CHECK`: em SQL a condição vale `TRUE`, `FALSE` ou
    `NULL`, e só `FALSE` reprova.

    A primeira versão usava `filter(~constraint.condition)`, que parece a leitura
    óbvia de "quem não satisfaz" e **estava errada**: o ORM acrescenta
    `IS NOT NULL` ao negar uma comparação, para que `exclude()` se comporte de
    forma intuitiva em Python. O efeito aqui era acusar como violação toda linha
    com o campo em branco — 244 falsos positivos no banco de desenvolvimento,
    num banco onde a migração aplica sem erro. Régua que grita lobo é pior do que
    régua nenhuma: o operador ou "corrige" linha sã ou passa a ignorar o aviso.

    Usa `_base_manager` porque a pergunta é sobre a **tabela**: o `objects` de
    `PrestacaoServidor` esconde as linhas removidas da equipe (`DB-06`) e o dos
    modelos com área recorta pela área ativa — os dois falseariam a contagem para
    menos, que é o erro perigoso aqui.
    """
    from django.db.models import BooleanField
    from django.db.models import ExpressionWrapper

    return (
        modelo._base_manager.annotate(
            _satisfaz=ExpressionWrapper(
                constraint.condition, output_field=BooleanField(),
            ),
        )
        .filter(_satisfaz=False)
        .count()
    )


def main(argv=None) -> int:
    _preparar_django()

    from django.apps import apps
    from django.db.models import CheckConstraint

    achados = []
    total_constraints = 0
    for modelo in apps.get_models():
        for constraint in modelo._meta.constraints:
            if not isinstance(constraint, CheckConstraint):
                continue
            total_constraints += 1
            quantidade = _violacoes(modelo, constraint)
            if quantidade:
                achados.append((modelo._meta.label, constraint.name, quantidade))

    print(f"`CheckConstraint` verificadas: {total_constraints}")
    if not achados:
        print("Nenhuma linha existente viola. A migração aplica sem tocar em dado.")
        return 0

    print(f"\nLinhas que violam, por constraint ({len(achados)} constraint(s)):")
    for label, nome, quantidade in achados:
        print(f"  {label}.{nome}: {quantidade}")
    print(
        "\nFALHOU: corrija estas linhas **antes** de aplicar as migrações do `DB-07`. "
        "A query que localiza cada uma está no docstring da migração correspondente.",
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
