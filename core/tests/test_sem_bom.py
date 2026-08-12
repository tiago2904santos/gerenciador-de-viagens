"""Nenhum arquivo de texto do repositório começa com BOM (`BE-22`).

BOM é marca de editor Windows, e em Python ele não é decorativo: lido como
`utf-8` (o que quase toda ferramenta faz), o `U+FEFF` vira caractere no início do
módulo e `ast.parse` recusa com

    SyntaxError: invalid non-printable character U+FEFF

Não é hipótese. Medido em 06/08/2026, antes de mexer: **11 arquivos** com BOM
UTF-8 — 10 `.py`, todos em `cadastros/`, mais `docs/REGRAS_DE_NEGOCIO.md`. E o
`cadastros/views.py` é **o único arquivo do repositório inteiro** que obrigava o
gate do `S-06` (`scripts/audit_django_architecture.py`) a ler com `utf-8-sig`:
o remendo estava lá, na régua, em vez de o defeito estar corrigido na origem.

O gate irmão (`P-05`, `drive_excepts_without_capture`) lia com `utf-8` puro e só
não quebrava porque nenhum arquivo do Drive tinha BOM — um arquivo de distância
de virar vermelho de bootstrap. Os dois passaram a ler `utf-8-sig`; este teste é
que impede o BOM de voltar.

Este teste nasceu com uma exceção para `.github/workflows/reparar-producao.yml`,
escrita na crença de que o `QA-11` seguia aberto. **Seguia aberto só no catálogo:**
a correção tinha entrado em `993e14c`, em 05/08, e o plano mestre já marcava
`[x]`. A exceção era um buraco nesta rede por nada, e saiu.

Sobreposição deliberada com `core/tests/test_encoding_dos_workflows.py`, que é a
catraca do `QA-11`: aquele é fundo e estreito (os quatro workflows, e também
mojibake de dupla codificação); este é raso e largo (todo arquivo de texto do
repositório, só BOM). Nenhum dos dois substitui o outro.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)

#: Diretórios que não são fonte do projeto.
IGNORADOS = {".git", ".venv", "node_modules", "__pycache__", "staticfiles", ".ruff_cache"}

#: BOM UTF-8 e as duas variantes UTF-16. As de 16 aparecem separadas para a
#: mensagem de falha dizer qual é — são defeitos de origem diferente.
BOMS = {
    b"\xef\xbb\xbf": "UTF-8",
    b"\xff\xfe": "UTF-16 LE",
    b"\xfe\xff": "UTF-16 BE",
}

EXTENSOES = {".py", ".md", ".html", ".js", ".css", ".txt", ".json", ".yml", ".yaml", ".cfg", ".toml"}


class SemBomTests(SimpleTestCase):
    def test_nenhum_arquivo_de_texto_comeca_com_bom(self):
        encontrados = []
        for caminho in sorted(RAIZ.rglob("*")):
            if not caminho.is_file() or caminho.suffix.lower() not in EXTENSOES:
                continue
            relativo = caminho.relative_to(RAIZ)
            if any(parte in IGNORADOS for parte in relativo.parts):
                continue
            inicio = caminho.open("rb").read(4)
            for marca, nome in BOMS.items():
                if inicio.startswith(marca):
                    encontrados.append(f"{relativo} ({nome})")
                    break

        self.assertEqual(
            encontrados,
            [],
            "BOM voltou nestes arquivos; em `.py` isso derruba `ast.parse` com "
            "`invalid non-printable character U+FEFF` e leva junto os gates que "
            "leem o código como código:\n  " + "\n  ".join(encontrados),
        )
