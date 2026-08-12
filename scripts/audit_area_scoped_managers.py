#!/usr/bin/env python3
"""Catraca do `BE-09`: quantos modelos com `area` ainda não têm o manager que recorta.

O `BE-09` é grande demais para um PR (28 modelos, ~288 chamadas de `.objects.`) e
sai em seis fatias. Sem uma régua, "quanto falta" viraria contagem à mão a cada
revisão, e um modelo esquecido não teria como aparecer.

Duas perguntas, e as duas por introspecção do registro de apps — não por regex sobre
o texto do arquivo. Um modelo pode declarar o manager numa classe base, e uma
varredura textual não veria:

1. **Cobertura.** Todo modelo com coluna `area` concreta precisa de `objects` do tipo
   `AreaScopedManager`, `all_objects` como `Manager` puro e
   `Meta.default_manager_name = "all_objects"`. Faltando qualquer um dos três, o
   modelo entra na conta e o `--max` reprova quando a conta sobe.

   O `default_manager_name` não é decoração: de `_default_manager` saem o admin, os
   campos de FK gerados por `ModelForm`, `validate_unique`, `UniqueConstraint.validate`,
   `dumpdata` e as relações reversas. Apontá-lo para o manager recortado neutralizaria
   o guarda m2m de `core/tenancy.py:116` e o check de deploy `core.E001` — sem
   nenhum teste ficar vermelho.

2. **`all_objects` em código de caminho de request.** É o gate literal de
   `docs/PLANO_BACKEND.md:88` ("a suíte inteira verde sem `all_objects` aparecer em
   código de request"). `all_objects` ali é legítimo às vezes — consulta
   deliberadamente global, como o piso de numeração de `oficios/models.py:200` — mas
   nunca é óbvio, e por isso exige um comentário na linha de cima ou na própria linha.
   Sem comentário, entra na conta.

Uso:
  python scripts/audit_area_scoped_managers.py            # lista
  python scripts/audit_area_scoped_managers.py --max 26   # falha se passar
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

#: Onde `all_objects` significa "estou num request e escolhi ver todas as áreas".
#: Comandos, tasks, scripts, migrações e testes ficam de fora de propósito: lá não
#: existe área ambiente e `all_objects` é redundante, não suspeito.
CAMINHO_DE_REQUEST = re.compile(r"(views|selectors|forms|presenters|services|view_helpers)\.py$")
IGNORA_DIRETORIO = re.compile(r"(^|/)(\.venv|\.git|migrations|tests|node_modules|scripts)(/|$)")
USO_DE_ALL_OBJECTS = re.compile(r"\ball_objects\b")

#: A tabela de vínculo não é dado de tenant. Recortá-la quebraria
#: `resolve_area_for_request` (`core/tenancy.py:31`), que a consulta para descobrir
#: qual é a área ativa — ninguém mais resolveria área nenhuma.
FORA_DO_RECORTE = {"usuarios.VinculoUsuarioArea"}


def _preparar_django():
    """Sobe o registro de apps. Este é o primeiro auditor que precisa do Django.

    O padrão é `config.settings.test`, e não `dev`, porque `dev` faz
    `load_dotenv()` e **estoura no import** sem `FIELD_ENCRYPTION_KEYS`
    (`config/settings/dev.py:41`). No CI não existe `.env`, então cair em `dev`
    trocaria a régua por um `RuntimeError` de bootstrap — vermelho que não fala
    do defeito que este script existe para medir. O `tests.yml` já trata `dev`
    como exceção que exige a chave explícita, num passo só.

    `test` serve porque a varredura é sobre `apps.get_models()` e nunca toca no
    banco; qual banco está configurado é irrelevante aqui.
    """
    sys.path.insert(0, str(RAIZ))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
    import django

    django.setup()


def modelos_sem_recorte():
    """Devolve `[(label, motivo), ...]` para todo modelo com `area` ainda descoberto."""
    from django.apps import apps
    from django.db import models

    from core.managers import AreaScopedManager

    pendentes = []
    for modelo in apps.get_models():
        label = modelo._meta.label
        if label in FORA_DO_RECORTE:
            continue
        if not any(f.name == "area" for f in modelo._meta.concrete_fields):
            continue

        managers = dict(modelo._meta.managers_map)
        objects = managers.get("objects")
        all_objects = managers.get("all_objects")

        if not isinstance(objects, AreaScopedManager):
            pendentes.append((label, "`objects` não é `AreaScopedManager`"))
        elif type(all_objects) is not models.Manager:
            pendentes.append((label, "falta `all_objects = models.Manager()`"))
        elif modelo._meta.default_manager_name != "all_objects":
            pendentes.append(
                (label, f'`default_manager_name` é {modelo._meta.default_manager_name!r}'),
            )
    return sorted(pendentes)


def all_objects_sem_justificativa():
    """Devolve `[(caminho:linha, trecho), ...]` de `all_objects` sem comentário perto."""
    achados = []
    for caminho in sorted(RAIZ.rglob("*.py")):
        relativo = caminho.relative_to(RAIZ).as_posix()
        if IGNORA_DIRETORIO.search(relativo) or not CAMINHO_DE_REQUEST.search(relativo):
            continue
        linhas = caminho.read_text(encoding="utf-8").splitlines()
        for numero, linha in enumerate(linhas, start=1):
            if not USO_DE_ALL_OBJECTS.search(linha):
                continue
            anterior = linhas[numero - 2].strip() if numero >= 2 else ""
            if "#" in linha or anterior.startswith("#"):
                continue
            achados.append((f"{relativo}:{numero}", linha.strip()))
    return achados


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max", type=int, default=None, help="teto de modelos pendentes")
    args = parser.parse_args(argv)

    _preparar_django()

    pendentes = modelos_sem_recorte()
    sem_justificativa = all_objects_sem_justificativa()

    print(f"Modelos com `area` ainda sem recorte no `objects`: {len(pendentes)}")
    for label, motivo in pendentes:
        print(f"  {label}: {motivo}")

    print(f"\n`all_objects` em caminho de request sem comentário: {len(sem_justificativa)}")
    for local, trecho in sem_justificativa:
        print(f"  {local}: {trecho}")

    falhou = False
    if args.max is not None and len(pendentes) > args.max:
        print(f"\nFALHOU: {len(pendentes)} pendentes passa do teto de {args.max}.")
        falhou = True
    if sem_justificativa:
        print(
            "\nFALHOU: `all_objects` em caminho de request precisa de um comentário "
            "dizendo por que aquela consulta é deliberadamente global.",
        )
        falhou = True
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
