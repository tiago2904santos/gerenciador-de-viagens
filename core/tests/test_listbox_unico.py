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
    # A variação de duas linhas: só o `picker.js` produz a segunda linha
    # (`--meta`) e as apresentações de pessoa e viatura. O select não tem
    # markup equivalente, e cobrar simetria seria cobrar o que não existe.
    "search-picker__option-meta",
    "search-picker__option--person",
    "search-picker__option--vehicle",
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


class VariacaoDeDuasLinhasTests(SimpleTestCase):
    """A opção com segunda linha — servidor e viatura.

    Uma linha só não distingue três Dusters do mesmo modelo nem dois servidores
    homônimos: é o combustível, a caracterização, o cargo e a unidade que
    desempatam. Cada asserção aqui corresponde a uma forma de a variação
    renderizar bonita e não informar nada.
    """

    def setUp(self):
        self.css = re.sub(
            r"/\*.*?\*/", "", LISTBOX.read_text(encoding="utf-8"), flags=re.DOTALL
        )

    def _bloco(self, marca: str) -> str:
        i = self.css.index(marca)
        return self.css[i : self.css.index("}", i)]

    def test_a_caixa_conta_o_item_mais_alto(self):
        """O teto de cinco itens é múltiplo da altura declarada.

        Sem trocá-la, a lista de duas linhas cortava no meio da sexta — a conta
        do teto continuava a de 40px.
        """
        bloco = self._bloco(":has(.search-picker__option-meta)")
        self.assertIn("--listbox-option-height: 52px;", bloco)

    def test_as_duas_linhas_empilham(self):
        bloco = self._bloco(
            ".search-picker__option:has(.search-picker__option-meta) .search-picker__option-content"
        )
        self.assertIn("display: grid;", bloco)
        self.assertIn("white-space: normal;", bloco)

    def test_a_segunda_linha_e_dado_de_apoio(self):
        """Em accent ela compete com o rótulo, e a linha inteira grita."""
        bloco = self._bloco(".search-picker__option-meta {")
        self.assertIn("color: var(--text-muted);", bloco)
        self.assertNotIn("var(--accent)", bloco)

    def test_a_segunda_linha_nao_acompanha_a_escolhida(self):
        marca = ".search-picker__option--selected .search-picker__option-meta"
        self.assertIn(marca, self.css)
        self.assertIn("color: var(--text-muted);", self._bloco(marca))

    def test_pessoa_e_viatura_tem_ancora_de_varredura(self):
        """O `picker.js` esconde o visual por padrão (é um "•", que é ruído).

        Nas duas apresentações com identidade ele volta, na mesma caixa do
        avatar da faixa de equipe.
        """
        for classe in (
            ".search-picker__option--person .search-picker__option-visual",
            ".search-picker__option--vehicle .search-picker__option-visual",
        ):
            self.assertIn(classe, self.css)
        bloco = self._bloco(".search-picker__option--vehicle .search-picker__option-visual")
        self.assertIn("display: inline-flex;", bloco)
        # 36px é a altura das DUAS linhas. No controle miúdo (28px) a âncora
        # ficava do tamanho de uma linha ao lado de um bloco com o dobro.
        self.assertIn("height: 36px;", bloco)

    def test_a_primeira_linha_lidera(self):
        """Cor e corpo sozinhos não separavam as duas: liam como um bloco só."""
        bloco = self._bloco(
            ".search-picker__option:has(.search-picker__option-meta) .search-picker__option-main"
        )
        self.assertIn("font-weight: var(--weight-strong);", bloco)

    def test_o_vao_horizontal_acompanha_o_vertical(self):
        """8px na horizontal com faixa de 52 lia como aperto de um lado só."""
        bloco = self._bloco(
            ".search-picker__option:has(.search-picker__option-meta) {"
        )
        self.assertIn("gap: var(--gap);", bloco)

    def test_a_variacao_se_liga_pela_segunda_linha_e_nao_pelo_nome(self):
        """`picker.js` monta `--meta` sempre que o item traz um segundo texto,
        inclusive fora de "people"/"vehicle". Ligar a regra ao nome da
        apresentação deixaria de fora casos que já são de duas linhas hoje."""
        self.assertIn(":has(.search-picker__option-meta)", self.css)
