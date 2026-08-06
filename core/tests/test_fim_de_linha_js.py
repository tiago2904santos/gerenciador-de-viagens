"""Todo `.js` do repositório termina linha com LF (`NOVO-18`).

O repositório mistura CRLF e LF. O estrago não é estético: qualquer editor que
normalize ao salvar reescreve o arquivo inteiro, e a troca de **uma** linha vira
um diff de 1.206 — a mudança real some no meio da revisão. Aconteceu duas vezes
e as duas foram desfeitas editando byte a byte.

Medido em 06/08/2026, antes de mexer: **164 arquivos** com CRLF no repositório
(101 `.py`, 21 `.md`, 18 `.html`, 14 `.js`, 7 `.css`, e alguns soltos) — o
enunciado original do `NOVO-18` contava 8, porque olhou só os arquivos que a
etapa tinha tocado. Este PR normaliza o recorte `.js`; o resto espera o sweep da
fase 9, que precisa de fila vazia.

`.gitattributes` é quem impede a volta no caminho normal (commit vindo de uma
máquina Windows, por exemplo). Este teste é a rede para o caminho anormal — um
arquivo entrando por fora da regra, ou a regra sendo removida sem querer.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
GITATTRIBUTES = RAIZ / ".gitattributes"

#: Diretórios que não são código do projeto nem entram no diff de revisão.
IGNORADOS = {".git", ".venv", "node_modules", "__pycache__", "staticfiles"}


def _arquivos_js():
    for caminho in sorted(RAIZ.rglob("*.js")):
        if any(parte in IGNORADOS for parte in caminho.relative_to(RAIZ).parts):
            continue
        yield caminho


class FimDeLinhaDoJavaScriptTests(SimpleTestCase):
    def test_nenhum_js_tem_retorno_de_carro(self):
        com_cr = []
        for caminho in _arquivos_js():
            conteudo = caminho.read_bytes()
            if b"\r" in conteudo:
                com_cr.append(
                    "%s (%d de %d linhas)"
                    % (
                        caminho.relative_to(RAIZ),
                        conteudo.count(b"\r\n"),
                        conteudo.count(b"\n"),
                    )
                )

        self.assertEqual(
            com_cr,
            [],
            "estes `.js` voltaram a ter CRLF; o próximo editor que normalizar "
            "vai produzir um diff de arquivo inteiro:\n  " + "\n  ".join(com_cr),
        )

    def test_a_regra_do_gitattributes_continua_declarada(self):
        """Sem a regra, o teste acima vira trabalho manual eterno."""
        self.assertTrue(GITATTRIBUTES.exists(), "`.gitattributes` sumiu")
        self.assertIn(
            "*.js text eol=lf",
            GITATTRIBUTES.read_text(encoding="utf-8"),
            "é a regra que normaliza no commit; o teste sozinho só avisa depois "
            "que o estrago já está no diff",
        )
