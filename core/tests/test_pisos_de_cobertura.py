"""`coverage-floors.json` e `COVERAGE_APPS` medem o mesmo conjunto (`BE-20`).

O gate de cobertura do `tests.yml` percorre as chaves de
`.github/coverage-floors.json` e **reprova quando um app não tem statement
medido**:

    {app}: no measured production statements

Ou seja: apagar um app e esquecer a chave derruba o CI inteiro, com uma mensagem
que fala de cobertura e não de app inexistente. E o contrário — app medido em
`COVERAGE_APPS` sem piso declarado — passa em silêncio, que é pior: a régua
existe e não mede nada ali.

Os dois lados ficaram fora de sincronia por um passo só ao remover o app-casca
`diario_bordo`. Este teste é o que transforma esse passo esquecido numa falha
local e barata, em vez de um vermelho no CI da `main`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
FLOORS = RAIZ / ".github" / "coverage-floors.json"
WORKFLOW = RAIZ / ".github" / "workflows" / "tests.yml"


def _apps_do_workflow() -> list[str]:
    achado = re.search(
        r'^\s*COVERAGE_APPS:\s*"([^"]+)"', WORKFLOW.read_text(encoding="utf-8"), re.MULTILINE
    )
    if achado is None:
        raise AssertionError("não achei `COVERAGE_APPS` em tests.yml — o gate mudou de forma")
    return [parte.strip() for parte in achado.group(1).split(",") if parte.strip()]


class PisosDeCoberturaTests(SimpleTestCase):
    def test_os_dois_lados_declaram_os_mesmos_apps(self):
        pisos = set(json.loads(FLOORS.read_text(encoding="utf-8")))
        medidos = set(_apps_do_workflow())

        self.assertEqual(
            sorted(pisos - medidos),
            [],
            "têm piso em coverage-floors.json mas não são medidos em COVERAGE_APPS; "
            "no CI isso vira `no measured production statements` e reprova",
        )
        self.assertEqual(
            sorted(medidos - pisos),
            [],
            "são medidos em COVERAGE_APPS mas não têm piso; a régua não mede nada "
            "para eles, e ninguém percebe",
        )

    def test_todo_app_com_piso_existe_no_disco(self):
        """Piso apontando para diretório que não existe é a forma silenciosa do mesmo erro."""
        ausentes = [
            app
            for app in json.loads(FLOORS.read_text(encoding="utf-8"))
            if not (RAIZ / app.replace(".", "/")).is_dir()
        ]
        self.assertEqual(ausentes, [], f"pisos sem app correspondente no disco: {ausentes}")
