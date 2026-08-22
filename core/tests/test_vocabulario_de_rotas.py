"""Nome de rota segue o vocabulário do `PADRAO_APP.md` (`BE-23`).

`docs/PADRAO_APP.md:12` manda `*_index`, `*_create`, `*_update`, `*_delete`. Cinco
apps usavam o par português (`_novo`/`_editar`/`_excluir`) — e, ao contrário do que
o catálogo dizia, **misturavam internamente**: `planos_trabalho` tinha 4 nomes em
inglês e 11 em português, `justificativas` 1 e 7, `oficios` 1 e 3,
`prestacoes_contas` 1 e 4, `eventos` 1 e 2.

As 28 foram renomeadas. Esta é a catraca que impede a divergência de voltar no
primeiro `urls.py` novo.

**Por que ler o arquivo e não o resolver.** Parte das rotas de `core` só é
registrada sob `settings.DEBUG` (`core/urls.py:18`), então o resolver de teste não
as enxerga: das 28 em português, 27 apareciam nele e uma —
`core:ui_lab_eventos_lista` — não. Um teste baseado no resolver teria deixado
exatamente essa passar.

O que **não** é assunto deste ID: o nome da *view* (`def modelo_excluir`) e o
caminho da URL (`modelos/<pk>/excluir/`). O primeiro é outra camada; o segundo é
link que alguém pode ter salvo. Só o `name=` mudou.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
IGNORADOS = {".venv", ".git", "__pycache__", "staticfiles", "historico", "migration_backups"}

SUFIXOS_PT = ("_novo", "_editar", "_excluir", "_lista", "_listar")
SUFIXOS_EN = ("_index", "_create", "_update", "_delete")

#: Catraca: este número só sobe. 70 em 06/08/2026, depois do `BE-23`.
#: 69 → 68 em 22/08/2026: `prestacoes_contas:modelo_create` saiu junto com a página
#: "novo modelo de texto", substituída pelo quick add — a rota morreu sem referência
#: viva, não foi rebatizada em português. Queda legítima, prevista na mensagem abaixo.
PISO_EN = 68

#: Tradução sugerida na mensagem de falha — o mesmo mapa usado na renomeação.
EQUIVALENTE = {"_novo": "_create", "_editar": "_update", "_excluir": "_delete", "_lista": "_index"}


def _nomes_de_rota():
    """`(arquivo, nome)` de todo `name=` declarado em algum `urls.py`."""
    for caminho in sorted(RAIZ.rglob("urls.py")):
        relativo = caminho.relative_to(RAIZ)
        if any(parte in IGNORADOS for parte in relativo.parts):
            continue
        fonte = caminho.read_text(encoding="utf-8")
        for achado in re.finditer(r"""name\s*=\s*["']([^"']+)["']""", fonte):
            yield relativo, achado.group(1)


class VocabularioDeRotasTests(SimpleTestCase):
    def test_nenhuma_rota_usa_o_sufixo_em_portugues(self):
        fora = [
            "%s: %s → %s"
            % (
                arquivo,
                nome,
                next(
                    nome[: -len(pt)] + en
                    for pt, en in EQUIVALENTE.items()
                    if nome.endswith(pt)
                ),
            )
            for arquivo, nome in _nomes_de_rota()
            if nome.endswith(SUFIXOS_PT)
        ]

        self.assertEqual(
            fora,
            [],
            "o `PADRAO_APP.md` manda sufixo em inglês; estes voltaram ao "
            "português:\n  " + "\n  ".join(fora),
        )

    def test_a_contagem_de_sufixos_em_ingles_nao_desce(self):
        """Catraca. Impede 'padronizar' apagando o sufixo em vez de traduzi-lo."""
        com_en = [nome for _, nome in _nomes_de_rota() if nome.endswith(SUFIXOS_EN)]

        self.assertGreaterEqual(
            len(com_en),
            PISO_EN,
            f"nomes com sufixo do padrão caíram de {PISO_EN} para {len(com_en)}; "
            "se a queda for legítima (rota removida), baixe o piso no mesmo PR e "
            "explique no corpo",
        )
