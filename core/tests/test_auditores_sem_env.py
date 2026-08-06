"""Gate NOVO-25 — auditor de área não pode depender do `.env` do desenvolvedor.

`scripts/audit_area_scoped_managers.py` sobe o Django de verdade (precisa de
`apps.get_models()`), e apontava para `config.settings.dev`. Esse módulo exige
`FIELD_ENCRYPTION_KEYS` no ambiente; o CI não define a chave. Resultado: o
auditor morria em `django.setup()` antes de olhar um modelo sequer e **reprovava
todo PR do repositório**, com um traceback de `RuntimeError` que não tem relação
nenhuma com o que o PR mudou.

Passava na máquina de quem escreveu porque lá existe `.env`. É o modo de falha
clássico de gate que sobe framework: verde no laptop, vermelho em qualquer lugar
limpo.

O teste roda o script num ambiente **cru** — `env -i`, sem `.env`, sem chave —
que é o que o runner do GitHub tem. Rodá-lo com o ambiente desta sessão não
provaria nada, porque aqui a chave existe.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
AUDITOR = RAIZ / "scripts" / "audit_area_scoped_managers.py"

#: O mínimo para o Python rodar. Sem `FIELD_ENCRYPTION_KEYS`, sem
#: `DJANGO_SETTINGS_MODULE`.
#:
#: `ENV_FILE` é o detalhe que faz este teste valer: `config/settings/base.py:16`
#: chama `load_dotenv(BASE_DIR / ENV_FILE)` com caminho **absoluto**, então
#: limpar variáveis de ambiente — ou mudar o cwd — não esconde o `.env` do
#: repositório. Apontando `ENV_FILE` para um arquivo que não existe, `load_dotenv`
#: vira no-op e o processo enxerga o mesmo que o runner do GitHub enxerga.
#: Sem isto o teste passa com o código defeituoso e não guarda nada — foi o que
#: aconteceu na primeira versão.
AMBIENTE_CRU = {
    "PATH": os.environ.get("PATH", ""),
    "HOME": os.environ.get("HOME", ""),
    "ENV_FILE": ".env.que-nao-existe-para-simular-o-ci",
}


class AuditorDeAreaRodaSemEnvTests(SimpleTestCase):
    def test_auditor_sobe_o_django_sem_chave_de_cifragem(self):
        resultado = subprocess.run(
            [sys.executable, str(AUDITOR), "--max", "26"],
            cwd=RAIZ,
            env=AMBIENTE_CRU,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotIn(
            "FIELD_ENCRYPTION_KEYS",
            resultado.stderr,
            "o auditor voltou a exigir a chave de cifragem — vai reprovar todo "
            "PR no CI, que não a define",
        )
        self.assertEqual(
            resultado.returncode,
            0,
            "auditor de área falhou em ambiente limpo:\n"
            f"stdout:\n{resultado.stdout}\nstderr:\n{resultado.stderr}",
        )

    def test_o_auditor_aponta_para_as_settings_de_teste(self):
        """A causa, fixada direto: `dev` exige chave, `test` gera a dela."""
        fonte = AUDITOR.read_text(encoding="utf-8")
        self.assertIn(
            'setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")', fonte
        )
        self.assertNotIn(
            'setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")', fonte
        )
