"""HT-06/NOVO-74: todo componente Cotton tem consumidor de produção."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


ROOT = Path(settings.BASE_DIR)
COTTON = ROOT / "templates" / "cotton"
SEARCH_SUFFIXES = {".html", ".py", ".js"}

# As duas listas abaixo são travas de regressão, não inventário: nomeiam componentes que
# o projeto apagou pagando a prova de grep do `AGENTS.md` §3.6. O guarda de órfão pega um
# deles se voltar sem consumidor; estas listas pegam o caso que ele não vê — voltar
# **e ser usado**, que é como componente morto reaparece na prática.
APAGADOS_PELO_HT06 = (
    "perfil/gdrive_card.html",
    "perfil/partials/_gdrive_card_header_meta.html",
    "ui/filters/advanced_filters.html",
    "ui/filters/search_input.html",
    "ui/lists/list_card_actions.html",
    "lists/main_list_card.html",
    "lists/list_filters.html",  # órfão em cascata do anterior
)

APAGADOS_COM_O_LAB = (
    "ui/buttons/field_action_button.html",
    "ui/buttons/floating_primary_action.html",
    "ui/buttons/footer_action.html",
    "ui/forms/dropdown.html",
    "ui/layouts/collection_header.html",
    "lists/list_grid.html",
    "ui/tables/data_table.html",
    # Segunda ordem: os citadores dele eram `list_grid.html` (acima) e `ui_lab2/views.py`
    # (PR #247). O `HT-06` o mediu vivo porque ambos ainda existiam.
    "cards/document_card.html",
)


def _sources() -> list[Path]:
    ignored = {".git", ".venv", "__pycache__"}
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix in SEARCH_SUFFIXES
        and not ignored.intersection(path.parts)
    )


def _is_test(path: Path) -> bool:
    return "tests" in path.parts or path.name.startswith("test_")


class NenhumComponenteOrfaoTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sources = {
            path: path.read_text(encoding="utf-8-sig", errors="replace")
            for path in _sources()
        }

    def components(self) -> list[Path]:
        return sorted(COTTON.rglob("*.html"))

    def citations(self, component: Path) -> list[Path]:
        relative = component.relative_to(COTTON)
        template_path = f"cotton/{relative.as_posix()}"
        tag = "<c-" + ".".join(relative.with_suffix("").parts)
        return [
            path
            for path, source in self.sources.items()
            if path != component and (template_path in source or tag in source)
        ]

    def test_todo_componente_tem_quem_o_renderize(self):
        orphaned = [
            str(path.relative_to(COTTON))
            for path in self.components()
            if not self.citations(path)
        ]
        self.assertEqual(orphaned, [], "componente Cotton sem consumidor")

    def test_nenhum_componente_vive_so_de_teste(self):
        test_only = []
        for component in self.components():
            citations = self.citations(component)
            if citations and all(_is_test(path) for path in citations):
                test_only.append(str(component.relative_to(COTTON)))
        self.assertEqual(test_only, [], "componente citado somente por teste")

    def test_namespace_unico_tem_o_inventario_atual(self):
        self.assertEqual(list((ROOT / "templates" / "components").rglob("*.*")), [])
        # NOVO-120: 115 = 121 - os 6 componentes do lab v1 (), apagados
        # com a prévia antiga. Dentro deles estão os do sistema v2
        # (`cotton/v2/`), cujo consumidor de produção é a galeria do UI Lab.
        # `forms/select.html` saiu, fundido no select global.
        #
        # 116: entrou `v2/destinations.html`, a seção que gerencia as linhas de
        # destino. O `destination_row` sozinho era só desenho — não adicionava,
        # não removia e não cascateava estado → cidade.
        #
        # 124 (2026-08-16): entrou `v2/download_picker.html`. Um termo vira
        # vários documentos (genérico, viatura, um por servidor) e o botão de
        # baixar entregava sempre o pacote inteiro fundido; o seletor é quem
        # pergunta o que se quer e baixa em fila.
        #
        # 126 (2026-08-16): `v2/fact.html` e `v2/itinerary.html`. São as peças
        # que faltavam para o cartão do v2 dizer o que o de ofício já dizia —
        # placa, valor, trechos. Os nomes de classe são novos (`fact`,
        # `route-legs`) porque `fact-block` e `itinerary` ainda estão vivos nas
        # telas não migradas: declarar os mesmos repintaria a lista de ofícios.
        #
        # 127 (2026-08-16): entrou `v2/quick_add.html`. O legado fazia criação
        # inline dentro de um componente de ~50 variáveis que montava a tela
        # inteira (`lists/list_page_quick_add.html`); aqui o painel é só o painel,
        # e a lista o recebe pelo slot `quick_add` do `list_page`.
        #
        # 126 (2026-08-16): saiu `v2/menu_header.html`. Nenhum menu do sistema
        # leva cabeçalho — ele repetia o que o gatilho e o cartão atrás já diziam.
        #
        # 128 (2026-08-16): `v2/cancel_modal.html` e `v2/confirm_modal.html`, os
        # dois diálogos de ação que faltavam para migrar uma lista real sem peça
        # legada. Os ganchos são os do `overlay.js` e vêm do legado na letra.
        #
        # 129 (2026-08-16): `v2/attach_signed_modal.html`, o terceiro e maior dos
        # dialogos de acao -- treze ganchos do `attach-signed-modal.js`, upload e o
        # estado "ja existe um assinado". O `file_picker` dentro dele segue legado
        # de proposito: e motor de upload, nao peca de desenho.
        #
        # 130 (2026-08-16): `v2/file_picker.html`. O legado punha escolher, nome e
        # anexar na MESMA faixa, e o botao cobria o nome do arquivo. Aqui os tres
        # sao blocos empilhados, na ordem da tarefa. Os ganchos do
        # `file-picker.js` vem do legado na letra, template de clone incluido.
        self.assertEqual(len(self.components()), 130)

    def test_os_apagados_do_HT06_nao_voltaram(self):
        """Sete arquivos, com a prova por arquivo que o `AGENTS.md` §3.6 exige.

        A E5 apagou esta trava junto com o diretório `templates/components/`: quando o
        diretório inteiro sumiu, `(COMPONENTES / rel).exists()` virou vacuamente
        verdadeira e o teste foi removido em vez de reapontado (`NOVO-80`). O caminho
        mudou; a lista, não — a E4 preservou a forma da árvore ao mover para
        `templates/cotton/`.
        """
        voltaram = [rel for rel in APAGADOS_PELO_HT06 if (COTTON / rel).exists()]
        self.assertEqual(voltaram, [], "componente apagado pelo HT-06 voltou")

    def test_os_apagados_da_cascata_do_be25_nao_voltaram(self):
        """Idem para a cascata do `NOVO-44` e para o que caiu com o UI Lab (PR #247)."""
        voltaram = [rel for rel in APAGADOS_COM_O_LAB if (COTTON / rel).exists()]
        self.assertEqual(voltaram, [], "componente apagado com o lab voltou")

    def test_as_travas_nomeadas_pegam_o_que_o_guarda_de_orfao_nao_ve(self):
        """O buraco do `NOVO-80` foi medido, não suposto.

        Ressuscitando `ui/forms/dropdown.html`:

          volta sem consumidor -> guarda de órfão pega, trava nomeada pega
          volta COM consumidor -> guarda de órfão passa, trava nomeada pega

        A segunda linha é o defeito, e é como componente morto reaparece na prática:
        alguém copia de branch antiga e já sai usando. Este teste prende a razão de as
        duas listas existirem, para que a próxima etapa não as apague de novo achando
        que o guarda de órfão já cobre o caso.
        """
        nomeados = set(APAGADOS_PELO_HT06) | set(APAGADOS_COM_O_LAB)
        vivos = {str(path.relative_to(COTTON)) for path in self.components()}
        self.assertEqual(nomeados & vivos, set())
        # com consumidor, o guarda de órfão não teria o que reclamar — só a lista pega
        self.assertIn("ui/forms/dropdown.html", nomeados)
