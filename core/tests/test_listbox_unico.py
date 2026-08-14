"""A lista de opções é um modelo global: as duas implementações não divergem.

O sistema tem duas listas que são a mesma coisa para quem usa — o menu do
select (`custom-select__menu--v2`) e o dropdown do picker
(`search-picker__dropdown--v2`). Enquanto cada componente descrevia a sua na
própria folha, elas divergiram em quinze propriedades ao mesmo tempo: raio,
recuo, altura do item, peso e cor do rótulo, sombra, fita da escolhida, animação
de entrada e barra de rolagem.

Nenhuma daquelas diferenças foi decidida. Todas nasceram de uma folha declarar
o que a outra não declarava, deixando o CSS legado preencher a lacuna — e
nenhuma aparecia em revisão de código, porque cada arquivo, lido sozinho,
parecia correto.

Estes testes tornam a convergência estrutural: a descrição da lista mora em UM
arquivo, e lá dentro toda regra de aparência precisa valer para as DUAS.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "static" / "css" / "v2"
LISTBOX = V2 / "listbox.css"

SELECT = "custom-select__menu--v2"
PICKER = "search-picker__dropdown--v2"

# Regras que tratam do que existe só num dos dois lados: o invólucro extra que o
# `picker.js` cria entre a caixa e as opções, as duas peças decorativas que ele
# põe em cada opção e o aviso de lista vazia. O select não tem equivalente, e
# exigir simetria aqui seria exigir markup que não existe.
SO_DO_PICKER = (
    "search-picker__list",
    "search-picker__option-marker",
    "search-picker__option-visual",
    "search-picker__empty",
)


def _regras(css: str) -> list[str]:
    """Devolve o seletor de cada regra, sem comentários."""
    sem_comentario = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    return [
        bloco.split("}")[-1].strip()
        for bloco in sem_comentario.split("{")[:-1]
        if bloco.split("}")[-1].strip()
    ]


class ListboxEhModeloGlobalTests(SimpleTestCase):
    def test_a_lista_mora_num_arquivo_so(self):
        self.assertTrue(LISTBOX.is_file(), "static/css/v2/listbox.css sumiu")

    def test_nenhuma_outra_folha_v2_descreve_a_lista(self):
        """Descrever a lista fora daqui é como as duas divergiram."""
        intrusos = []
        for folha in sorted(V2.glob("*.css")):
            if folha.name == "listbox.css":
                continue
            texto = folha.read_text(encoding="utf-8")
            sem_comentario = re.sub(r"/\*.*?\*/", "", texto, flags=re.DOTALL)
            for marca in (SELECT, PICKER):
                if marca in sem_comentario:
                    intrusos.append(f"{folha.name} descreve `{marca}`")
        self.assertEqual(
            intrusos,
            [],
            "a aparência da lista de opções só pode ser descrita em v2/listbox.css",
        )

    def test_toda_regra_de_aparencia_vale_para_as_duas_listas(self):
        css = LISTBOX.read_text(encoding="utf-8")
        assimetricas = []
        for seletor in _regras(css):
            if any(marca in seletor for marca in SO_DO_PICKER):
                continue
            if (SELECT in seletor) != (PICKER in seletor):
                assimetricas.append(" ".join(seletor.split())[:120])
        self.assertEqual(
            assimetricas,
            [],
            "regra que alcança uma lista e não a outra — é assim que elas divergem",
        )

    def test_a_folha_esta_registrada_na_entrega(self):
        builder = (ROOT / "scripts" / "build_shell_bundles.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"css/v2/listbox.css"', builder)
        bundle = (ROOT / "static" / "css" / "ui.bundle.css").read_text(encoding="utf-8")
        self.assertIn("v2/listbox.css", bundle)

    def test_a_lista_nao_escreve_cor_literal(self):
        """Cor literal aqui é cor que não acompanha o tema."""
        css = re.sub(r"/\*.*?\*/", "", LISTBOX.read_text(encoding="utf-8"), flags=re.DOTALL)
        literais = re.findall(r"#[0-9a-fA-F]{3,8}\b|\brgba?\([^)]*\)", css)
        self.assertEqual(
            literais, [], "use os tokens de `v2/tokens.css`, não cor literal"
        )
