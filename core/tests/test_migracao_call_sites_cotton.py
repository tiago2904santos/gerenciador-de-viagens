from django.test import SimpleTestCase

from scripts.migrar_call_sites_cotton import converter_extends, converter_include, converter_texto
from scripts.migrar_slots_cotton import converter_tag
from scripts.propagar_contratos_cotton import propagate_text
from scripts.isolar_includes_django import isolate_dynamic_cotton, isolate_text


class MigracaoCallSitesCottonTests(SimpleTestCase):
    def test_converte_constantes_variaveis_filtros_e_only(self):
        origem = (
            '{% include "components/ui/buttons/button.html" '
            'with label="Abrir documento" href=arquivo.url '
            'icon=icone|default:"document" only %}'
        )

        self.assertEqual(
            converter_include(origem),
            '{% with cotton_attr_icon=icone|default:"document" %}'
            '<c-ui.buttons.button label="Abrir documento" '
            ':href="arquivo.url" :icon="cotton_attr_icon" only />'
            '{% endwith %}',
        )

    def test_converte_include_sem_parametros(self):
        self.assertEqual(
            converter_include('{% include "components/ui/icons/_sprite.html" %}'),
            '<c-ui.icons._sprite />',
        )

    def test_ignora_include_de_partial_de_aplicacao(self):
        origem = '{% include "oficios/partials/_card.html" with card=card only %}'
        self.assertEqual(converter_include(origem), origem)

    def test_converte_heranca_de_componente_para_template_canonico(self):
        self.assertEqual(
            converter_extends('{% extends "components/page/flow_base.html" %}'),
            '{% extends "cotton/page/flow_base.html" %}',
        )

    def test_rejeita_sintaxe_inesperada_em_componente(self):
        with self.assertRaisesRegex(ValueError, "include de componente não suportado"):
            converter_include(
                '{% include template|default:"components/lists/list_tabs.html" '
                'with abas=abas only %}'
            )

    def test_canonicaliza_caminho_passado_como_parametro_dinamico(self):
        origem = '<c-travel.section rows_template="components/travel/rows.html" />'
        self.assertEqual(
            converter_texto(origem),
            ('<c-travel.section rows_template="cotton/travel/rows.html" />', 1),
        )


class MigracaoSlotsCottonTests(SimpleTestCase):
    def test_converte_templates_estatico_e_dinamico_em_slots(self):
        origem = (
            '<c-form.card title="Dados" body_template="app/_body.html" '
            ':footer_template="footer_template" />'
        )

        self.assertEqual(
            converter_tag(origem),
            '<c-form.card title="Dados">'
            '<c-slot name="body">{% include "app/_body.html" %}</c-slot>'
            '<c-slot name="footer">{% include footer_template %}</c-slot>'
            '</c-form.card>',
        )

    def test_preserva_card_sem_template_dinamico(self):
        origem = '<c-ui.forms.form_block title="Dados" />'
        self.assertEqual(converter_tag(origem), origem)

    def test_remove_template_vazio_sem_criar_include_invalido(self):
        self.assertEqual(
            converter_tag('<c-ui.forms.form_block footer_template="" />'),
            '<c-ui.forms.form_block />',
        )


class PropagacaoContratosCottonTests(SimpleTestCase):
    def test_repassa_atributos_ambientais_ainda_nao_explicitos(self):
        self.assertEqual(
            propagate_text(
                '<c-lists.page title="Dados" />',
                {"lists.page": ["cards", "page_obj", "title"]},
            ),
            '<c-lists.page title="Dados" :cards="cards" :page_obj="page_obj" />',
        )

    def test_respeita_only_e_nao_transforma_slots_em_atributos(self):
        contracts = {"form.card": ["actions", "body", "title"]}
        self.assertEqual(
            propagate_text('<c-form.card :title="title" only />', contracts),
            '<c-form.card :title="title" only />',
        )


class IsolamentoIncludesDjangoTests(SimpleTestCase):
    def test_adiciona_contrato_e_only_a_include_estatico(self):
        source = '{% include "app/_partial.html" with title=page_title %}'

        converted = isolate_text(
            source,
            {"app/_partial.html": ["items", "title"]},
        )

        self.assertEqual(
            converted,
            '{% include "app/_partial.html" with title=page_title items=items only %}',
        )

    def test_completa_include_ja_isolado_e_preserva_include_dinamico(self):
        source = (
            '{% include "app/_partial.html" only %}'
            "{% include partial_template %}"
        )

        self.assertEqual(
            isolate_text(source, {"app/_partial.html": ["items"]}),
            '{% include "app/_partial.html" with items=items only %}'
            "{% include partial_template %}",
        )

    def test_include_dinamico_recebe_contexto_declarado_e_local(self):
        source = (
            "{% cotton:vars items title %}"
            "{% with panel_id=title %}{% include body_template %}{% endwith %}"
        )

        self.assertEqual(
            isolate_dynamic_cotton(source),
            "{% cotton:vars items title %}"
            "{% with panel_id=title %}"
            "{% include body_template with items=items title=title panel_id=panel_id only %}"
            "{% endwith %}",
        )
