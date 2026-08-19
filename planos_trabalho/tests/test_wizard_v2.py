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

from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.testing import vincular_area

from .helpers import configurar_sistema
from .helpers import criar_base_geografica
from .helpers import criar_plano_maringa

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "templates" / "planos_trabalho"
SCRIPT = ROOT / "static" / "js" / "pages" / "planos-trabalho-wizard.js"


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

    def test_o_texto_de_busca_de_cada_atividade_e_o_que_o_script_le(self):
        """O cartão de escolha do v2 publica o texto em `data-choice-filter`."""
        html = self._html("planos_trabalho:wizard_atividades")
        self.assertIn("data-choice-filter=", html)
        self.assertIn("choiceFilter", SCRIPT.read_text(encoding="utf-8"))

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
