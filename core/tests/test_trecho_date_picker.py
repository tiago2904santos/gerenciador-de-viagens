"""O calendário dos trechos é um calendário comum mais DUAS coisas, e nada além.

O contrato é literal: contexto do trecho e seleção múltipla. Se um terceiro
botão ou uma terceira faixa aparecerem no painel, ele deixou de ser o componente
pedido. Por isso os testes comparam gancho a gancho com o painel comum, em vez
de só conferir que o HTML "tem um calendário".

E o componente é um PRESET do partial global: se um dia alguém copiar a marcação
do painel para dentro dele, `test_e_um_preset_e_nao_uma_segunda_copia_do_painel`
cai antes de a cópia chegar na tela.
"""

import re
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase


def _ganchos(html):
    return set(re.findall(r"data-cv-date-picker-([a-z-]+)", html))


class TrechoDatePickerTests(SimpleTestCase):
    def _novo(self, **contexto):
        return render_to_string("cotton/v2/trecho_date_picker.html", contexto)

    def _motor(self):
        return (
            Path(settings.BASE_DIR)
            / "static"
            / "js"
            / "components"
            / "date-picker.js"
        ).read_text(encoding="utf-8")

    def _comum(self):
        return render_to_string(
            "cotton/v2/date_picker.html",
            {
                "mode": "single",
                "single_input_id": "comum-display",
                "single_hidden_id": "comum-value",
                "single_hidden_name": "comum_value",
            },
        )

    def test_e_um_preset_e_nao_uma_segunda_copia_do_painel(self):
        fonte = (
            Path(settings.BASE_DIR)
            / "templates"
            / "cotton"
            / "v2"
            / "trecho_date_picker.html"
        ).read_text(encoding="utf-8")
        self.assertIn("<c-v2.date_picker", fonte)
        self.assertNotIn("date-picker__panel", fonte)
        self.assertNotIn("date-picker__days", fonte)

        self.assertEqual(self._novo().count("data-cv-date-picker-panel"), 1)

    def test_o_painel_tem_as_pecas_do_calendario_comum(self):
        html = self._novo()
        for peca in ("prev", "month", "next", "weekdays", "days", "panel"):
            with self.subTest(peca=peca):
                self.assertIn(f"data-cv-date-picker-{peca}", html)

    def test_diferenca_1_a_faixa_de_contexto_do_trecho(self):
        html = self._novo()
        self.assertIn("data-cv-date-picker-context", html)
        self.assertIn("data-cv-date-picker-context-step", html)
        self.assertIn("data-cv-date-picker-context-route", html)
        self.assertNotIn("data-cv-date-picker-context", self._comum())

    def test_diferenca_2_a_selecao_e_multipla_e_sequencial(self):
        html = self._novo()
        self.assertIn('data-mode="multi"', html)
        self.assertIn('data-allow-repeat-dates="true"', html)

    def test_a_faixa_de_contexto_nomeia_o_trecho_sem_o_total(self):
        """`Trecho 1:`, e não `Trecho 1 de 4` — quem escreve é o motor."""
        motor = self._motor()
        self.assertIn("'Trecho ' + currentStepNumber + ':'", motor)
        self.assertNotIn("' de ' + totalSteps", motor)

    def test_a_faixa_veste_as_classes_do_bate_volta(self):
        """Pill contínuo do primeiro ao último dia, com as MESMAS classes do
        intervalo. Sem `--multi-*`: dois desenhos para a mesma ideia era o que
        fazia esta tela destoar."""
        motor = self._motor()
        for classe in ("--range-start", "--range-end", "date-picker__day--range"):
            with self.subTest(classe=classe):
                self.assertIn(classe, motor)
        self.assertNotIn("--multi-selected", motor)
        self.assertNotIn("--multi-start", motor)
        self.assertNotIn("--multi-middle", motor)
        self.assertNotIn("--multi-single", motor)

    def test_a_data_do_meio_ganha_o_numero_do_deslocamento(self):
        """Com três ou mais datas, as do meio somem dentro da faixa: as pontas
        se leem pela cápsula, o miolo não. O número diz qual delas é qual."""
        motor = self._motor()
        self.assertIn("if (mode === 'multi' && selectedDates.length > 2) {", motor)
        self.assertIn("for (var si = 1; si < selectedDates.length - 1; si += 1) {", motor)
        self.assertIn("badge.className = 'date-picker__day-badge';", motor)
        self.assertIn("badge.textContent = String(si + 1);", motor)

        folha = (
            Path(settings.BASE_DIR) / "static" / "css" / "v2" / "date-picker.css"
        ).read_text(encoding="utf-8")
        self.assertIn(".date-picker__day-badge {", folha)

    def test_nao_ha_terceira_diferenca_alem_do_contexto_e_do_desfazer(self):
        """`undo` não é feature nova: a seleção sequencial não desmarca no clique."""
        so_do_novo = _ganchos(self._novo()) - _ganchos(self._comum())
        self.assertEqual(
            so_do_novo,
            {"context", "context-step", "context-route", "undo"},
        )

    def test_o_rodape_nao_pede_um_clique_a_mais(self):
        """Sem "Aplicar datas": o motor fecha sozinho ao receber a última data."""
        self.assertNotIn("data-cv-date-picker-confirm", self._novo())
        self.assertNotIn("Aplicar datas", self._novo())

    def test_nao_ha_campo_de_texto_nem_resumo(self):
        html = self._novo()
        self.assertNotIn("data-cv-date-picker-display", html)
        self.assertNotIn("data-cv-date-picker-summary", html)

    def test_o_gatilho_e_um_botao_do_sistema_e_aponta_para_o_painel(self):
        html = self._novo(picker_id="trechos-date-picker", trigger_label="Datas")
        self.assertIn('id="trechos-date-picker"', html)
        self.assertIn('id="trechos-date-picker-panel"', html)
        self.assertIn('aria-controls="trechos-date-picker-panel"', html)
        self.assertIn("button button--secondary", html)
        self.assertNotIn("travel-period-filter__btn", html)
        self.assertIn(">Datas</span>", html)

    def test_o_gatilho_nao_veste_a_classe_do_icone_flutuante(self):
        """`.date-field .date-picker__trigger` é o ícone com `opacity: 0` até o
        hover. Num botão inteiro ela o apagava da tela — e como o motor acha o
        gatilho pelo `data-*`, nada quebrava: o botão só sumia."""
        gatilho = re.search(
            r'<button[^>]*data-cv-date-picker-trigger', self._novo()
        )
        self.assertIsNotNone(gatilho, "o gatilho sumiu")
        self.assertNotIn("date-picker__trigger", gatilho.group(0))

    def test_os_padroes_chegam_do_outro_lado(self):
        """Padrão dentro de `:attr` do Cotton não é avaliado — daí resolvê-los antes."""
        html = self._novo()
        self.assertIn('id="trecho-date-picker"', html)
        self.assertIn('aria-controls="trecho-date-picker-panel"', html)
        self.assertIn(">Datas</span>", html)
        self.assertIn('aria-label="Preencher as datas dos trechos"', html)
