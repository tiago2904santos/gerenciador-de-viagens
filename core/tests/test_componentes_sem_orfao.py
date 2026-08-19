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

# Migração dos cadastros para o v2 (2026-08-18): as duas telas que ainda
# chamavam a lista padrão legada — servidores e viaturas — passaram ao
# `c-v2.list_page`, e o alternador de abas virou o `toggle` do sistema. Sem
# consumidor, os dois saíram; a prova de grep está no PR.
APAGADOS_COM_OS_CADASTROS = (
    "lists/list_page_standard.html",
    "lists/list_toggle.html",
)


# Migração de Ofícios para o v2 (NOVO-20260818-213853-fab772ef1b6e): o segment
# toggle legado perdeu o último consumidor quando o par SERVIDOR × MANUAL do
# motorista virou `c-v2.driver_mode_toggle`. Prova de grep no PR: zero
# ocorrências de `segment_toggle` e `c-ui.segment_toggle` em `templates/`,
# `static/js/` e `*.py`.
APAGADOS_COM_OS_OFICIOS = ("ui/segment_toggle.html",)


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

# NOVO-20260819-024829-01844001d431: componentes substituídos pelo v2.
APAGADOS_NA_ERRADICACAO_V2 = (
    "documents/partials/_signature_card_body.html",
    "documents/partials/_signature_card_header_meta.html",
    "documents/signature_card.html",
    "feedback/alerts.html",
    "feedback/confirm_delete_block.html",
    "feedback/module_placeholder.html",
    "form/card.html",
    "lists/list_empty.html",
    "lists/list_page_cards.html",
    "lists/list_page_quick_add.html",
    "lists/list_tabs.html",
    "lists/simple_list.html",
    "lists/simple_list_row.html",
    "travel/destination_row.html",
    "travel/destination_section.html",
    "travel/destinations/city_select.html",
    "travel/destinations/errors.html",
    "travel/destinations/row_template.html",
    "travel/destinations/rows.html",
    "travel/destinations/state_select.html",
    "travel/period_destinations_section.html",
    "travel/route_segments.html",
    "travel/travel_allowance_calculator.html",
    "ui/badges/chip.html",
    "ui/badges/status_badge.html",
    "ui/buttons/button.html",
    "ui/buttons/field_manage_button.html",
    "ui/buttons/floating_action.html",
    "ui/buttons/icon_button.html",
    "ui/feedback/alert.html",
    "ui/feedback/empty_state.html",
    "ui/feedback/field_error.html",
    "ui/feedback/form_errors.html",
    "ui/feedback/pendencias_card.html",
    "ui/forms/_date_picker_icon.html",
    "ui/forms/_field_control.html",
    "ui/forms/card_toggle.html",
    "ui/forms/date_picker.html",
    "ui/forms/document_number_field.html",
    "ui/forms/field.html",
    "ui/forms/file_picker.html",
    "ui/forms/form_block.html",
    "ui/forms/multiselect.html",
    "ui/forms/related_picker.html",
    "ui/header.html",
    "ui/headers/filter_page_header.html",
    "ui/headers/page_header.html",
    "ui/headers/wizard_page_header.html",
    "ui/input.html",
    "ui/layouts/card_footer_actions.html",
    "ui/layouts/card_footer_section.html",
    "ui/lists/entity_card.html",
    "ui/lists/entity_card_footer.html",
    "ui/lists/entity_card_header.html",
    "ui/lists/entity_card_menu.html",
    "ui/lists/entity_card_menu_body.html",
    "ui/lists/file_list.html",
    "ui/lists/itinerary.html",
    "ui/lists/pagination.html",
    "ui/menus/rich_menu_header.html",
    "ui/menus/rich_menu_link.html",
    "ui/modals/attach_signed_modal.html",
    "ui/modals/cancel_reason_modal.html",
    "ui/modals/confirm_action_modal.html",
    "ui/modals/confirm_delete.html",
    "ui/modals/delete_confirm_modal.html",
    "ui/modals/dialog_header.html",
    "ui/navigation/page_stepper.html",
    "ui/select.html",
    "ui/sub_header.html",
)

# Não são componentes antigos com substituto visual disponível. São as
# fronteiras que continuam fora de `v2/`: infraestrutura do shell/fluxo,
# renderização de PDF, primitiva sem decoração, sprite de ícones e a integração
# específica com o Google Drive. A igualdade exata impede que um novo namespace
# paralelo volte a crescer silenciosamente.
SEM_EQUIVALENTE_V2 = frozenset(
    {
        "create_draft.html",
        "documents/pdf_viewer.html",
        "layout/sidebar.html",
        "page/flow_base.html",
        "partials/_create_draft_body.html",
        "perfil/partials/_gdrive_card_body.html",
        "perfil/partials/_gdrive_conta_actions.html",
        "perfil/partials/_gdrive_conta_body.html",
        "perfil/partials/_gdrive_diretorio_body.html",
        "perfil/partials/_gdrive_pendencias_body.html",
        "perfil/partials/_gdrive_pendencias_meta.html",
        "ui/buttons/plain_button.html",
        "ui/icons/_sprite.html",
        "ui/icons/icon.html",
    }
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
        #
        # 131 (2026-08-17): `v2/delete_modal.html`, o QUARTO e último diálogo de
        # ação. Sem ele o botão de excluir do v2 apontava para um diálogo que só
        # existia em legado — na galeria, para nenhum: o clique não fazia nada.
        #
        # 134 (2026-08-17): `v2/map.html`, `v2/route_segments.html` e
        # `v2/travel_allowance.html` — os três motores do editor de roteiro, a
        # última tela de formulário presa ao legado fora do wizard de ofício. Os
        # ganchos de JS vêm na letra (Leaflet, editor de trechos, cálculo de
        # diárias); o que mudou foi a marcação em volta deles.
        #
        # 137 (2026-08-17): `v2/state_toggle.html`, `v2/time_stepper.html` e
        # `v2/route_mode_toggle.html`. Os três nasceram do contrato de botão: o
        # `test_templates_de_aplicacao_nao_reimplementam_button` proíbe `<button>`
        # cru em template de aplicação, e os três casos do editor de roteiro
        # (interruptor de estado, ajuste de 15 minutos, modo do roteiro) precisam
        # de `id` e de `data-*` COM VALOR, que não cabem no `hook` do
        # `c-v2.button`. Dentro de `templates/cotton/` o botão cru é o caminho
        # previsto — é o diretório que o scanner exclui.
        #
        # 140 (2026-08-18): +5 das peças de CATÁLOGO, -2 da lista legada e do
        # alternador de abas, que ficaram sem consumidor quando servidores e
        # viaturas migraram, -1 do rodapé de formulário da configuração.
        # As cinco peças de catálogo são —
        # `v2/catalog_page.html` (a tela inteira), `v2/catalog_row.html` (a
        # linha), `v2/form_field.html` (um `BoundField` do Django no desenho do
        # v2) e os dois botões de ação da linha, `v2/quick_edit_button.html` e
        # `v2/set_default_button.html`. Os quinze catálogos do sistema chamavam
        # `list_page_quick_add` com ~50 atributos cada; agora cada tela declara
        # só o que tem de próprio.
        #
        # 141 (2026-08-18): `v2/prestacao_card.html`. É o cartão mais denso do
        # sistema — um formulário com autosave por servidor, dois menus por
        # linha (um deles com seis `data-wa-*`) e o anexar-assinado no rodapé —,
        # e mora em componente porque quase toda ação dele é `<button>` cru com
        # `data-*` COM VALOR, que não cabe no `hook` do `c-v2.button`.
        #
        # 142 (2026-08-18): `v2/os_role_toggle.html`. O toggle de função da
        # equipe da OS (Condução / Técnico / Apoio) era o `segment-toggle`
        # legado escrito no template da tela; virou o `toggle--fill` do sistema.
        # Mora em componente porque `data-os-role-mode` carrega VALOR, e valor
        # dentro do `hook` do `c-v2.button` sai escapado.
        #
        # 143 (NOVO-20260818-161641-9c71598641c6): entrou a página única de
        # confirmação de exclusão. O `module_card` apenas mudou do namespace
        # `cards` para `v2`, com os dois consumidores migrados no mesmo corte.
        #
        # 144 (2026-08-18): `v2/attach_signed_button.html`. Irmão do
        # `menu_attach_signed`: os mesmos ganchos do `attach-signed-modal.js`,
        # num botão de linha em vez de item de menu. Nasceu quando o cartão de
        # termo perdeu o menu "Documentos" — anexar o assinado é a única ação
        # dali que não é "baixar", e ficava escondida dois cliques abaixo.
        #
        # 146 (2026-08-18): as duas peças que faltavam ao painel do evento —
        # `v2/file_list.html` (a lista de arquivos anexados: nome, ver e
        # excluir, que não é um `record` porque um arquivo não tem título, selo
        # e meta) e `v2/evento_doc_toggle.html` (os cinco tipos de documento
        # vinculável, botão cru porque `data-doc-tab-target` carrega valor).
        #
        # 147 (2026-08-18): `v2/fab.html`, a ação flutuante. As etapas do painel
        # do evento são listas longas, e a ação no cabeçalho do painel some na
        # primeira rolagem — quem chega ao fim da lista voltaria ao topo para
        # criar o próximo item.
        #
        # 148 (NOVO-20260818-200724-685b186c033b): `v2/quick_add_section.html`,
        # o `<fieldset>` de um grupo do quick add. O painel é UM POST e ficou
        # visualmente neutro; a superfície passou para a seção, e ela mora em
        # componente porque as quinze telas de cadastro rápido repetiam a mesma
        # casca de grupo. A vitrine só ganhou o consumidor agora
        # (NOVO-20260818-213141-764248d0a297) — o corte que criou o componente
        # deixou este contrato e o da galeria vermelhos.
        #
        # 149 (NOVO-20260818-213141-00cd8bcc960a): `v2/related_row.html`, a
        # linha do picker de documento vinculado. É o gêmeo declarativo de
        # `CV.pickerParts.createRelatedCard`: nas telas reais o script monta a
        # linha, e onde ela é conhecida no servidor — a vitrine — era escrita à
        # mão em `<button>` cru, contra o `HT-08`. Mora em componente pela razão
        # de sempre: `data-route-id` carrega VALOR, e valor no `hook` do
        # `c-v2.button` sai escapado.
        #
        # 155 (NOVO-20260818-213853-fab772ef1b6e): as seis peças que faltavam
        # para Ofícios não chamar mais nada de fora do v2.
        #
        # Quatro são de conteúdo: `v2/document_inline.html` (o PDF aberto na
        # própria página — a folha `v2/document-inline.css` já viajava no bundle
        # SEM componente, e a marcação era copiada à mão em nove telas),
        # `v2/alert_list.html` (a pendência de etapa, que no sistema anterior era
        # um QUARTO desenho de "atenção", com caixa e marcador próprios),
        # `v2/document_number.html` (o par número/ano — último campo a desenhar a
        # própria moldura em vez de usar o `field`) e `v2/suggestions.html` (a
        # faixa de atalhos do formulário, cujos dois ganchos se separavam quando
        # escritos soltos no template).
        #
        # Duas são de ação, e existem pela razão de sempre — `<button>` cru com
        # `data-*` só é permitido dentro de `templates/cotton/`:
        # `v2/driver_mode_toggle.html` (o segmento SERVIDOR × MANUAL do
        # motorista, escrito à mão em duas etapas do ofício, irmão do
        # `os_role_toggle` e do `route_mode_toggle`) e `v2/menu_button.html` (o
        # item de menu que EXECUTA em vez de navegar — "Visualizar termos"; como
        # link ele precisaria de um destino falso).
        #
        # 154 (mesmo corte): saiu `ui/segment_toggle.html`. Era o último
        # componente do sistema anterior vivo em Ofícios, e o `toggle` do v2 já
        # fazia as duas variantes dele.
        #
        # 160 (NOVO-20260818-223338-aa3c31f87b9d): as seis peças que faltavam
        # para o wizard de Plano de Trabalho ser v2 de ponta a ponta. Quatro são
        # do SISTEMA, e nasceram aqui porque nenhuma tela tinha por onde
        # dizê-las sem reinventar o desenho: `v2/choice_card.html` e
        # `v2/choice_grid.html` (a opção que ocupa uma caixa clicável e a grade
        # delas — o desenho já existia em `v2/choice-card.css`, vestindo a
        # marcação que a OS escreve à mão), `v2/number_stepper.html` (o campo com
        # "−" e "+") e `v2/live_list.html` (a coluna que um JS reescreve, com
        # contagem e vazio). As outras duas são de DOMÍNIO, como `prestacao_card`
        # e `route_segments`: `v2/efetivo_row.html`, a linha de coleção ordenada
        # da equipe — irmã da linha de destino —, e `v2/document_preview.html`, o
        # cartão que abre o PDF na própria página.
        #
        # O aviso de pendências do wizard NÃO é uma sétima peça: é o
        # `v2/alert_list.html` que Ofícios trouxe no mesmo dia. Nasceram em
        # paralelo com o mesmo contrato, e sobrou o que já estava no `main`.
        # 90 = 160 - 70 implementações antigas substituídas por componentes v2.
        # As 14 folhas restantes fora de v2 não possuem equivalente: shell de
        # fluxo, sidebar, PDF, ícones/sprite, assinatura e integração Drive.
        self.assertEqual(len(self.components()), 90)

    def test_fora_do_v2_so_restam_pecas_sem_equivalente(self):
        fora_do_v2 = {
            path.relative_to(COTTON).as_posix()
            for path in self.components()
            if path.relative_to(COTTON).parts[0] != "v2"
        }
        self.assertEqual(fora_do_v2, SEM_EQUIVALENTE_V2)

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

    def test_os_apagados_com_os_cadastros_nao_voltaram(self):
        """A lista padrão legada e o alternador de abas, sem consumidor."""
        voltaram = [rel for rel in APAGADOS_COM_OS_CADASTROS if (COTTON / rel).exists()]
        self.assertEqual(voltaram, [], "componente apagado com os cadastros voltou")

    def test_os_apagados_com_os_oficios_nao_voltaram(self):
        """O segment toggle legado, sem consumidor depois do `driver_mode_toggle`."""
        voltaram = [rel for rel in APAGADOS_COM_OS_OFICIOS if (COTTON / rel).exists()]
        self.assertEqual(voltaram, [], "componente apagado com os ofícios voltou")

    def test_os_apagados_da_cascata_do_be25_nao_voltaram(self):
        """Idem para a cascata do `NOVO-44` e para o que caiu com o UI Lab (PR #247)."""
        voltaram = [rel for rel in APAGADOS_COM_O_LAB if (COTTON / rel).exists()]
        self.assertEqual(voltaram, [], "componente apagado com o lab voltou")

    def test_os_apagados_na_erradicacao_v2_nao_voltaram(self):
        voltaram = [rel for rel in APAGADOS_NA_ERRADICACAO_V2 if (COTTON / rel).exists()]
        self.assertEqual(voltaram, [], "componente legado substituído pelo v2 voltou")

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
        nomeados = (
            set(APAGADOS_PELO_HT06)
            | set(APAGADOS_COM_O_LAB)
            | set(APAGADOS_COM_OS_CADASTROS)
            | set(APAGADOS_COM_OS_OFICIOS)
            | set(APAGADOS_NA_ERRADICACAO_V2)
        )
        vivos = {str(path.relative_to(COTTON)) for path in self.components()}
        self.assertEqual(nomeados & vivos, set())
        # com consumidor, o guarda de órfão não teria o que reclamar — só a lista pega
        self.assertIn("ui/forms/dropdown.html", nomeados)
