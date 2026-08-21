"""O wizard de Plano de Trabalho no v2 continua salvando — e continua ligado ao script.

As quatro etapas trocaram de casca inteira: saíram `page-shell--wizard`,
`c-form.card`, `c-ui.forms.form_block` e quatro folhas de página; entraram
`c-v2.wizard_page`, `c-v2.panel` e `c-v2.form_block`. Nada disso pode ter mexido
em três coisas:

1. os NOMES dos campos que os formulários leem no POST — se um mudar, a etapa
   salva pela metade e ninguém vê erro;
2. os `data-*` que `js/pages/planos-trabalho-wizard.js` procura, um por um, para
   trocar o painel do coordenador, calcular as diárias ao vivo, filtrar as
   atividades e clonar a linha de efetivo — se um sumir, o controle continua na
   tela e para de responder EM SILÊNCIO;
3. o par `wizard_action`/valor de cada botão de rodapé, que é como a view sabe se
   avança, volta ou finaliza.

Este arquivo é o par do `termos/tests/test_form_v2.py`, e existe pelo mesmo
motivo: com Planos de Trabalho fora da tupla de
`core/tests/test_global_period_destinations_section.py`, é aqui que a promessa
"período e destinos continuam iguais" passa a ser cobrada.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from core.testing import vincular_area

from .helpers import configurar_sistema
from .helpers import criar_base_geografica
from .helpers import criar_plano_maringa

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "templates" / "planos_trabalho"
SCRIPT = ROOT / "static" / "js" / "pages" / "planos-trabalho-wizard.js"
LIVE_LIST_CSS = ROOT / "static" / "css" / "v2" / "live-list.css"


class WizardV2Tests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="pt_v2", password="123456")
        self.client.force_login(user)
        vincular_area(user)
        _, self.curitiba, self.maringa, _ = criar_base_geografica()
        configurar_sistema(self.curitiba)
        self.plano = criar_plano_maringa(self.maringa)

    def _html(self, nome):
        resposta = self.client.get(reverse(nome, args=[self.plano.pk]))
        self.assertEqual(resposta.status_code, 200, nome)
        return resposta.content.decode()

    # ---- casca -----------------------------------------------------------

    def test_nenhuma_tela_carrega_folha_de_pagina(self):
        """Quatro folhas saíram; tudo o que desenha vem do `ui.bundle.css`.

        A checagem é pelo `<link>`, e não pelo nome do arquivo: os comentários
        que registram a troca citam as folhas que saíram, e citar não é carregar.
        """
        for arquivo in sorted(TEMPLATES.rglob("*.html")):
            with self.subTest(template=arquivo.name):
                fonte = arquivo.read_text(encoding="utf-8")
                self.assertNotIn("<link rel=\"stylesheet\"", fonte)

    def test_nenhuma_tela_usa_componente_anterior_ao_v2(self):
        """A migração é total: nenhum `c-ui.`, `c-form.`, `c-feedback.` ou `c-travel.`."""
        proibidos = ("<c-ui.", "<c-form.", "<c-feedback.", "<c-travel.", "<c-lists.")
        for arquivo in sorted(TEMPLATES.rglob("*.html")):
            fonte = arquivo.read_text(encoding="utf-8")
            for prefixo in proibidos:
                with self.subTest(template=arquivo.name, prefixo=prefixo):
                    self.assertNotIn(prefixo, fonte)

    def test_o_marcador_do_tema_legado_saiu_das_quatro_etapas(self):
        """`data-travel-document-wizard-step1` é gancho de 160 regras legadas.

        O `overlay.js` ainda o copia para os menus que abre, levando o tema
        junto: numa tela v2 ele desfaz o desenho em vez de completá-lo.
        """
        for nome in (
            "planos_trabalho:wizard_identificacao",
            "planos_trabalho:wizard_efetivo_diarias",
            "planos_trabalho:wizard_atividades",
            "planos_trabalho:wizard_documentos",
        ):
            with self.subTest(etapa=nome):
                html = self._html(nome)
                self.assertNotIn("data-travel-document-wizard-step1", html)
                self.assertNotIn("data-travel-document-wizard-documentos", html)

    def test_o_resumo_de_evento_usa_o_card_de_lista_v2(self):
        card = (TEMPLATES / "partials" / "_resumo_evento_record.html").read_text(
            encoding="utf-8"
        )
        corpo = (TEMPLATES / "partials" / "_resumo_evento_body.html").read_text(
            encoding="utf-8"
        )

        self.assertIn('<c-v2.record box="panel"', card)
        self.assertNotIn("<c-v2.panel", card)
        self.assertEqual(corpo.count('extra_class="plan-event-summary__block"'), 3)
        self.assertIn('aria_label="Coordenação do evento"', corpo)
        self.assertIn('aria_label="Efetivo do evento"', corpo)
        self.assertIn('aria_label="Diárias e atividades do evento"', corpo)

        html = render_to_string(
            "planos_trabalho/partials/resumo_evento_card.html",
            {
                "ev": {
                    "ordem": 1,
                    "programa": "PROGRAMA PARANÁ EM AÇÃO",
                    "destino": "ANTONINA/PR",
                    "data_evento_extenso": "17 a 23 de agosto de 2026",
                    "horario": "09:00 até 17:00",
                    "coordenador_op_presente": False,
                    "efetivo_total": 0,
                    "efetivo_itens": [],
                    "valor_total_display": "—",
                    "diarias_composicao": "—",
                    "atividades_count": 0,
                    "atividades": [],
                },
                "numero": "32/2026/ASCOM",
                "coordenador_adm_nome": "—",
                "coordenador_adm_cargo": "",
                "is_multi": True,
                "total_eventos": 1,
                "mostrar_acoes": False,
            },
        )
        self.assertIn('class="record panel plan-event-summary"', html)
        self.assertIn("Nº 32/2026/ASCOM · ANTONINA/PR", html)
        self.assertEqual(html.count("plan-event-summary__block"), 3)

    # ---- etapa 1 ---------------------------------------------------------

    def test_os_campos_do_post_da_identificacao_continuam_os_mesmos(self):
        html = self._html("planos_trabalho:wizard_identificacao")
        for nome in (
            'name="programa"',
            'name="programa_outros"',
            'name="destino_estado"',
            'name="destino_cidade"',
            'name="data_evento_inicio"',
            'name="data_evento_fim"',
            'name="horario_atendimento"',
            'name="contextualizacao"',
            'name="coordenacao"',
            'name="consideracao_final"',
            'name="contextualizacao_auto"',
            'name="coordenador_adm"',
            'name="coordenador_op"',
        ):
            with self.subTest(campo=nome):
                self.assertIn(nome, html)

    def test_os_ganchos_da_identificacao_continuam_na_tela_e_no_script(self):
        html = self._html("planos_trabalho:wizard_identificacao")
        script = SCRIPT.read_text(encoding="utf-8")
        for gancho in (
            "data-pt-form",
            "data-pt-programa-outros-field",
            "data-pt-coordenador-panel",
            "data-pt-texto-auto-flag",
            "data-location-row",
            "data-location-state",
            "data-location-city",
        ):
            with self.subTest(gancho=gancho):
                self.assertIn(gancho, html, f"{gancho} sumiu da tela")
                self.assertIn(gancho, script, f"{gancho} não é mais procurado pelo script")

    def test_a_secao_de_destinos_liga_o_motor_uma_vez_so(self):
        """Dois ouvintes no "+" fazem um clique inserir DUAS linhas.

        O `c-v2.destinations` se liga sozinho por `data-location-managed`; o
        script da etapa deixou de chamar `initManagedRows` no mesmo escopo.
        """
        html = self._html("planos_trabalho:wizard_identificacao")
        self.assertIn("data-location-managed", html)
        # A chamada, não a menção: o comentário que registra a saída a cita.
        self.assertNotIn("locationRows.initManagedRows(", SCRIPT.read_text(encoding="utf-8"))

    def test_o_voltar_do_cabecalho_preserva_o_rascunho_antes_de_sair(self):
        """`autosave.js` procura `[data-autosave-link="1"]` para esperar o salvamento.

        Sem o atributo, quem edita e clica em "voltar" dentro da janela do
        debounce depende só do beacon de `unload`, que corre contra a navegação.
        O cabeçalho legado marcava este link; a migração o perdeu por um turno.
        """
        html = self._html("planos_trabalho:wizard_identificacao")
        voltar = html[: html.index(">Voltar", html.index("wizard-page"))]
        inicio = voltar.rindex("<a")
        self.assertIn('data-autosave-link="1"', voltar[inicio:])

    def test_o_calendario_do_evento_escreve_nos_campos_do_formulario(self):
        html = self._html("planos_trabalho:wizard_identificacao")
        self.assertIn("data-cv-date-picker-start-value", html)
        self.assertIn("data-cv-date-picker-end-value", html)

    def test_selects_com_gerenciamento_usam_o_componente_global(self):
        html = self._html("planos_trabalho:wizard_identificacao")

        self.assertEqual(html.count('data-entity-picker-renderer="select"'), 6)
        self.assertNotIn('class="field__manage"', html)
        self.assertIn('aria-label="Gerenciar programas"', html)
        self.assertEqual(html.count('aria-label="Gerenciar cargos"'), 2)
        self.assertIn('aria-label="Gerenciar horários"', html)
        for field_id in ("id_coordenador_adm_genero", "id_coordenador_op_genero"):
            inicio = html.index(f'id="{field_id}"')
            wrapper = html.rfind('data-entity-picker-renderer="select"', 0, inicio)
            self.assertGreater(wrapper, html.rfind("<div class=\"field\"", 0, inicio))
        self.assertIn(
            "cadastros/cargos/?next=%2Fplanos-trabalho%2F",
            html,
        )

    def test_programa_solicitante_usa_form_block_split(self):
        html = self._html("planos_trabalho:wizard_identificacao")
        titulo = html.index('<h2 class="form-block__title">Programa solicitante</h2>')
        abertura = html.rfind("<section", 0, titulo)
        section = html[abertura : html.index(">", abertura) + 1]

        self.assertIn("form-block--split", section)

        css = (ROOT / "static" / "css" / "v2" / "form-block.css").read_text(encoding="utf-8")
        regra = css[css.index(".form-block--v2.form-block--split .form-block__description {") :]
        regra = regra[: regra.index("}")]
        self.assertIn("white-space: normal", regra)
        self.assertIn("overflow-wrap: anywhere", regra)

    def test_programa_ocupa_linha_e_divide_somente_quando_outro_aparece(self):
        html = self._html("planos_trabalho:wizard_identificacao")

        self.assertIn("field-grid--cols-2 programa-solicitante-grid", html)
        self.assertIn("data-pt-programa-outros-field hidden", html)
        css = (ROOT / "static" / "css" / "v2" / "form-block.css").read_text(encoding="utf-8")
        self.assertIn(
            ".programa-solicitante-grid:has(\n  > [data-pt-programa-outros-field][hidden]",
            css,
        )

    def test_periodo_do_evento_usa_form_block_split(self):
        html = self._html("planos_trabalho:wizard_identificacao")
        titulo = html.index('<h2 class="form-block__title">Período do evento</h2>')
        abertura = html.rfind("<section", 0, titulo)
        section = html[abertura : html.index(">", abertura) + 1]

        self.assertIn("form-block--split", section)

    def test_textos_da_identificacao_usam_o_textarea_global(self):
        html = self._html("planos_trabalho:wizard_identificacao")

        campos = {
            "id_contextualizacao": "Breve contextualização",
            "id_coordenacao": "Coordenação do evento",
            "id_consideracao_final": "Considerações finais",
        }
        for field_id, rotulo in campos.items():
            inicio = html.index(f'id="{field_id}"')
            tag = html[html.rfind("<textarea", 0, inicio) : html.index(">", inicio) + 1]
            self.assertIn('class="input__control input__control--textarea"', tag)
            self.assertNotIn("cv-field__control", tag)
            self.assertIn(
                f'class="field__label sr-only" for="{field_id}">{rotulo}</label>',
                html,
            )

        input_css = (ROOT / "static" / "css" / "v2" / "input.css").read_text(encoding="utf-8")
        regra_textarea = input_css[input_css.index(".input__control--textarea {") :]
        regra_textarea = regra_textarea[: regra_textarea.index("}")]
        self.assertIn("scrollbar-color: var(--text-muted) transparent", regra_textarea)
        self.assertIn("scrollbar-width: thin", regra_textarea)

    def test_pickers_de_coordenador_nao_repetem_o_rotulo_nome(self):
        html = self._html("planos_trabalho:wizard_identificacao")

        # A contagem é do rótulo "Nome", e não de todo rótulo escondido: os
        # blocos de texto da etapa (contextualização, coordenação, considerações)
        # também escondem o seu, e passaram a somar cinco.
        escondidos = re.findall(
            r'<label class="field__label sr-only"[^>]*>([^<]*)</label>', html
        )
        self.assertEqual(escondidos.count("Nome"), 2)
        self.assertNotIn('class="field__label">Nome</label>', html)

    # ---- etapa 2 ---------------------------------------------------------

    def test_a_linha_de_efetivo_mantem_os_ganchos_do_formset(self):
        html = self._html("planos_trabalho:wizard_efetivo_diarias")
        script = SCRIPT.read_text(encoding="utf-8")
        for gancho in (
            "data-pt-efetivo-rows",
            "data-pt-efetivo-template",
            "data-pt-efetivo-row",
            "data-pt-efetivo-add",
            "data-pt-efetivo-remove",
            "data-pt-efetivo-ord",
            "data-pt-quantidade-delta",
        ):
            with self.subTest(gancho=gancho):
                self.assertIn(gancho, html, f"{gancho} sumiu da tela")
                self.assertIn(gancho, script, f"{gancho} não é mais procurado pelo script")
        self.assertIn('name="efetivo-TOTAL_FORMS"', html)
        self.assertIn("__prefix__", html, "o molde do formset perdeu o marcador")

    def test_o_stepper_de_quantidade_e_o_do_sistema(self):
        """O JS acha o par pelo `closest('.number-stepper')` — a classe é contrato."""
        html = self._html("planos_trabalho:wizard_efetivo_diarias")
        self.assertIn('class="number-stepper"', html)
        self.assertIn(".number-stepper", SCRIPT.read_text(encoding="utf-8"))

    def test_datas_e_horas_do_deslocamento_ocupam_a_mesma_linha(self):
        fonte = (TEMPLATES / "partials" / "_diarias_body.html").read_text(encoding="utf-8")

        self.assertIn('class="field-grid field-grid--cols-4"', fonte)
        self.assertIn('extra_class="field-grid__span-2"', fonte)
        self.assertNotIn(
            'class="field-grid field-grid--cols-2">\n  <c-v2.form_field :field="diarias_form.saida_sede_hora"',
            fonte,
        )

    def test_efetivo_usa_select_com_acao_e_input_globais(self):
        html = self._html("planos_trabalho:wizard_efetivo_diarias")

        self.assertGreaterEqual(html.count('data-entity-picker-renderer="select"'), 2)
        self.assertGreaterEqual(html.count('aria-label="Gerenciar cargos"'), 2)
        inicio = html.index('id="id_efetivo-0-quantidade"')
        tag = html[html.rfind("<input", 0, inicio) : html.index(">", inicio) + 1]
        self.assertIn('class="input__control"', tag)
        self.assertNotIn("cv-field__control", tag)
        self.assertIn(
            "cadastros/cargos/?next=%2Fplanos-trabalho%2F",
            html,
        )

    def test_so_a_primeira_linha_de_efetivo_exibe_os_rotulos(self):
        html = self._html("planos_trabalho:wizard_efetivo_diarias")
        script = SCRIPT.read_text(encoding="utf-8")

        # A linha existente mostra os rótulos; o molde das próximas já nasce
        # compacto e o motor recalcula o estado após inserção ou remoção.
        self.assertEqual(html.count("efetivo-row--without-labels"), 1)
        self.assertIn('classList.toggle("efetivo-row--without-labels", index > 0)', script)

    def test_o_resultado_das_diarias_tem_onde_receber_o_calculo(self):
        html = self._html("planos_trabalho:wizard_efetivo_diarias")
        for gancho in (
            "data-pt-diarias-resultado",
            "data-pt-resultado-total",
            "data-pt-resultado-total-extenso",
            "data-pt-resultado-unitario",
            "data-pt-resultado-unitario-extenso",
            "data-pt-resultado-composicao",
            "data-pt-resultado-efetivo",
            "data-pt-diarias-erros",
        ):
            with self.subTest(gancho=gancho):
                self.assertIn(gancho, html)

    def test_o_resumo_das_diarias_usa_tres_paineis_v2(self):
        html = self._html("planos_trabalho:wizard_efetivo_diarias")

        # `pt-diarias-summary` e `pt-diarias-summary__panel` não tinham CSS:
        # os três painéis vinham EMPILHADOS, e não na faixa que o comentário da
        # tela descrevia. A faixa agora é o modificador do próprio bloco.
        self.assertIn('class="fact-list fact-list--band-3"', html)
        self.assertEqual(html.count('aria-label="Valor total do plano"'), 1)
        self.assertEqual(html.count('aria-label="Valor por servidor"'), 1)
        self.assertEqual(
            html.count('aria-label="Quantidade de diárias e efetivo total"'), 1
        )
        self.assertIn("Quantidade de diárias", html)
        self.assertNotIn("Composição por servidor", html)

    def test_o_aviso_das_diarias_fica_antes_do_resumo_financeiro(self):
        html = self._html("planos_trabalho:wizard_efetivo_diarias")

        self.assertLess(
            html.index("data-pt-diarias-erros"),
            html.index("data-pt-diarias-resultado"),
        )

    def test_a_nota_de_cada_fato_de_diarias_existe_mesmo_sem_calculo(self):
        """A tela abre SEM cálculo, e é aí que o script mais precisa de onde escrever.

        `setText` procura `[data-pt-resultado-*-extenso]` por nome: se a nota só
        nascesse com texto, o valor por extenso nunca apareceria num plano que
        ainda não tem datas — que é exatamente o plano em que se acabou de
        preencher a etapa.
        """
        self.plano.saida_sede_data = None
        self.plano.chegada_sede_data = None
        self.plano.diarias_valor_total = None
        self.plano.save()
        html = self._html("planos_trabalho:wizard_efetivo_diarias")
        for gancho in (
            "data-pt-resultado-total-extenso",
            "data-pt-resultado-unitario-extenso",
            "data-pt-resultado-efetivo",
        ):
            with self.subTest(gancho=gancho):
                self.assertIn(gancho, html)

    def test_o_fato_que_o_calculo_preenche_nao_nasce_no_desenho_de_vazio(self):
        """Com o estado vazio do `fact`, o total chegava certo e continuava apagado.

        `fact__value--empty` é apagado, itálico, sem `--strong` e sem
        `data-fit-text`; o `runCalc()` só troca o `textContent`. O traço faz o
        elemento já nascer sendo o valor que ele vai virar — é o que o
        `c-v2.travel_allowance` do roteiro faz.
        """
        self.plano.saida_sede_data = None
        self.plano.chegada_sede_data = None
        self.plano.diarias_valor_total = None
        self.plano.save()
        html = self._html("planos_trabalho:wizard_efetivo_diarias")

        resultado = html[html.index("data-pt-diarias-resultado") :]
        resultado = resultado[: resultado.index("</div>", resultado.index("data-pt-resultado-efetivo"))]
        self.assertNotIn("fact__value--empty", resultado)
        self.assertIn("fact__value--strong", resultado)
        self.assertIn("data-fit-text", resultado)

    def test_o_erro_do_destino_chega_a_tela(self):
        """`clean()` anexa "Informe a cidade do destino." a `destino_cidade`.

        As linhas de destino são `<select>` montados pelo componente, fora do
        `field` — sem renderizar os erros dos dois campos, a etapa recarregava
        com o resumo genérico e nenhum campo destacado.
        """
        resposta = self.client.post(
            reverse("planos_trabalho:wizard_identificacao", args=[self.plano.pk]),
            {
                "wizard_action": "wizard_next",
                "destino_estado": self.maringa.estado_id,
                "destino_cidade": "",
                "data_evento_inicio": "2026-09-01",
                "data_evento_fim": "2026-09-03",
                "coordenador_adm_modo": "SERVIDOR",
                "coordenador_op_modo": "SERVIDOR",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Informe a cidade do destino.")

    # ---- etapa 3 ---------------------------------------------------------

    def test_a_grade_de_atividades_mantem_os_ganchos_da_selecao(self):
        html = self._html("planos_trabalho:wizard_atividades")
        script = SCRIPT.read_text(encoding="utf-8")
        for gancho in (
            "data-pt-activity",
            "data-pt-activity-preset",
            "data-pt-activity-search",
            "data-pt-activity-clear",
            "data-pt-activity-empty",
            "data-pt-live-metas-list",
            "data-pt-live-recursos-list",
        ):
            with self.subTest(gancho=gancho):
                self.assertIn(gancho, html, f"{gancho} sumiu da tela")
                self.assertIn(gancho, script, f"{gancho} não é mais procurado pelo script")

    def test_a_barra_de_atividades_separa_busca_e_preset_com_acao(self):
        html = self._html("planos_trabalho:wizard_atividades")

        inicio = html.index("choice-grid__toolbar-start")
        fim = html.index("choice-grid__toolbar-end")
        self.assertLess(inicio, fim)
        self.assertLess(html.index('id="pt-atividade-search"', inicio), fim)
        self.assertLess(html.index("data-pt-activity-clear", inicio), fim)
        self.assertIn('id="pt-atividade-preset"', html[fim:])
        self.assertIn("field-with-action", html[fim:])
        self.assertIn("Gerenciar presets", html[fim:])

    def test_a_grade_de_atividades_tem_duas_colunas(self):
        html = self._html("planos_trabalho:wizard_atividades")

        self.assertIn('class="choice-grid"', html)
        self.assertNotIn("choice-grid--dense", html)

    def test_o_texto_de_busca_de_cada_atividade_e_o_que_o_script_le(self):
        """O cartão de escolha do v2 publica o texto em `data-choice-filter`."""
        html = self._html("planos_trabalho:wizard_atividades")
        self.assertIn("data-choice-filter=", html)
        self.assertIn("choiceFilter", SCRIPT.read_text(encoding="utf-8"))

    def test_metas_e_recursos_usam_o_mesmo_cabecalho_alinhado(self):
        html = self._html("planos_trabalho:wizard_atividades")

        self.assertEqual(html.count('class="live-list__head"'), 2)
        self.assertEqual(html.count('class="live-list__count"'), 2)

    def test_metas_e_recursos_possuem_teto_e_rolagem_v2(self):
        css = LIVE_LIST_CSS.read_text(encoding="utf-8")

        self.assertIn("max-height: 190px", css)
        self.assertIn("overflow-y: auto", css)
        self.assertIn("scrollbar-color: var(--text-muted) transparent", css)
        self.assertIn("scrollbar-width: thin", css)

    # ---- rodapés ---------------------------------------------------------

    def test_cada_rodape_manda_a_acao_que_a_view_espera(self):
        """Sem o par `name`/`value` o POST não diz o que pedir e a etapa recarrega em si."""
        esperado = {
            "planos_trabalho:wizard_identificacao": ("save_draft_list", "wizard_next"),
            "planos_trabalho:wizard_efetivo_diarias": ("wizard_back", "wizard_next"),
            "planos_trabalho:wizard_atividades": ("wizard_back", "wizard_next"),
        }
        for nome, acoes in esperado.items():
            html = self._html(nome)
            self.assertIn('name="wizard_action"', html, nome)
            for acao in acoes:
                with self.subTest(etapa=nome, acao=acao):
                    self.assertIn(f'value="{acao}"', html)

    def test_a_etapa_de_documentos_oferece_finalizar_quando_nao_ha_pendencia(self):
        html = self._html("planos_trabalho:wizard_documentos")
        self.assertIn('name="wizard_action"', html)
        self.assertRegex(html, r'value="(finalizar|save_draft_list)"')
        # "Adicionar evento ao plano" vive DENTRO do `<form>` da etapa: é um
        # submit com `formaction`, porque formulário aninhado o HTML não tem.
        self.assertIn("formaction=", html)
        self.assertIn("formnovalidate", html)
