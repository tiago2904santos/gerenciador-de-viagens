"""Arquivos de texto do projeto terminam linha com LF (`NOVO-18`).

O repositório tinha 164 arquivos com CRLF ou finais mistos. Qualquer editor que
normalizasse um deles ao salvar escondia a mudança real num diff de arquivo
inteiro. O recorte JavaScript foi normalizado primeiro; a fase 9 fechou os 103
arquivos restantes e ampliou a regra para todo texto reconhecido pelo Git.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
GITATTRIBUTES = RAIZ / ".gitattributes"

class FimDeLinhaDoRepositorioTests(SimpleTestCase):
    def test_nenhum_blob_versionado_tem_final_crlf_ou_misto(self):
        """Confere o índice, sem depender do `core.autocrlf` da máquina."""
        resultado = subprocess.run(
            ["git", "ls-files", "--eol"],
            cwd=RAIZ,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        nao_canonicos = [
            linha for linha in resultado.stdout.splitlines() if linha.startswith(("i/crlf", "i/mixed"))
        ]

        self.assertEqual(
            nao_canonicos,
            [],
            "estes blobs versionados voltaram a ter CRLF/finais mistos:\n  "
            + "\n  ".join(nao_canonicos),
        )

    def test_a_regra_global_do_gitattributes_continua_declarada(self):
        self.assertTrue(GITATTRIBUTES.exists(), "`.gitattributes` sumiu")
        self.assertIn(
            "* text=auto eol=lf",
            GITATTRIBUTES.read_text(encoding="utf-8"),
            "a regra global de LF foi removida",
        )
