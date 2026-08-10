from django.test import SimpleTestCase

from scripts.migrar_call_sites_cotton import converter_include


class MigracaoCallSitesCottonTests(SimpleTestCase):
    def test_converte_constantes_variaveis_filtros_e_only(self):
        origem = (
            '{% include "components/ui/buttons/button.html" '
            'with label="Abrir documento" href=arquivo.url '
            'icon=icone|default:"document" only %}'
        )

        self.assertEqual(
            converter_include(origem),
            '<c-ui.buttons.button label="Abrir documento" '
            ':href="arquivo.url" :icon=\'icone|default:"document"\' only />',
        )

    def test_converte_include_sem_parametros(self):
        self.assertEqual(
            converter_include('{% include "components/ui/icons/_sprite.html" %}'),
            '<c-ui.icons._sprite />',
        )

    def test_ignora_include_de_partial_de_aplicacao(self):
        origem = '{% include "oficios/partials/_card.html" with card=card only %}'
        self.assertEqual(converter_include(origem), origem)

    def test_rejeita_sintaxe_inesperada_em_componente(self):
        with self.assertRaisesRegex(ValueError, "include de componente não suportado"):
            converter_include(
                '{% include template|default:"components/lists/list_tabs.html" '
                'with abas=abas only %}'
            )
