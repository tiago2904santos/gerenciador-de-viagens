"""O editor de roteiro é v2 — e continua sendo o editor (2026-08-17).

A tela tem três motores de JS pendurados nela (editor de trechos, cálculo de
diárias e mapa) e nenhum deles levanta erro quando um gancho some: o campo
apenas para de ser preenchido. Este arquivo é a rede disso — cada `id` e cada
`name` que o `js/pages/roteiros/editor/index.js`, o `trechos.js` e o
`roteiros-map.js` procuram tem uma asserção aqui.

A trava do legado é a outra metade: a página não pode voltar a carregar
`pages/roteiros.css` nem a estender a casca de wizard antiga.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Cidade
from cadastros.models import Estado
from core.testing import vincular_area
from roteiros.services.editor_parser import parse_destinos_post


class EditorDeRoteiroV2Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estado = Estado.objects.create(sigla="PR", nome="Parana")
        cls.cidade = Cidade.objects.create(nome="CURITIBA", estado=cls.estado, uf="PR", capital=True)

    def setUp(self):
        usuario = get_user_model().objects.create_user(username="editor_v2")
        vincular_area(usuario)
        self.client.force_login(usuario)

    def _html(self):
        resposta = self.client.get(reverse("roteiros:novo"))
        self.assertEqual(resposta.status_code, 200)
        return resposta.content.decode()

    # ---- o legado não voltou ------------------------------------------------

    def test_a_pagina_nao_carrega_a_folha_de_pagina_legada(self):
        html = self._html()
        self.assertNotIn("css/pages/roteiros.css", html)
        self.assertNotIn("css/base/domain.css", html)

    def test_o_esqueleto_e_o_do_v2(self):
        html = self._html()
        for marca in ('class="form-page', 'class="header', 'class="panel', "form-block--v2"):
            with self.subTest(marca=marca):
                self.assertIn(marca, html)
        # a casca de wizard legada não é mais estendida
        self.assertNotIn("travel-document-wizard", html)
        self.assertNotIn("wizard-inner-section", html)

    # ---- os ganchos dos três motores ---------------------------------------

    def test_o_formulario_leva_as_urls_que_o_editor_chama(self):
        html = self._html()
        for gancho in (
            'id="roteiro-editor-form"',
            "data-api-cidades-url=",
            "data-api-diarias-url=",
            "data-api-calcular-rota-url=",
            "data-url-trechos-estimar=",
            "data-autosave-create-url=",
        ):
            with self.subTest(gancho=gancho):
                self.assertIn(gancho, html)

    def test_os_campos_ocultos_do_resultado_continuam(self):
        """São eles que levam o cálculo e a rota para o POST."""
        html = self._html()
        for campo in (
            'name="tipo_destino"',
            'name="quantidade_diarias"',
            'name="valor_diarias"',
            'name="valor_diarias_extenso"',
            'name="map_route_geometry_json"',
            'name="map_route_distance_km"',
        ):
            with self.subTest(campo=campo):
                self.assertIn(campo, html)

    def test_os_destinos_expoem_lista_e_molde_por_id(self):
        """O editor reindexa a lista e clona o molde procurando os dois por id."""
        html = self._html()
        self.assertIn('id="destinos-container"', html)
        self.assertIn('id="tmpl-destino-roteiro"', html)
        self.assertIn("data-location-rows", html)
        self.assertIn("data-location-list", html)

    def test_o_mapa_tem_moldura_leituras_e_botoes(self):
        html = self._html()
        for gancho in (
            'id="roteiro-mapa-container"',
            'id="roteiro-mapa-distancia"',
            'id="roteiro-mapa-tempo"',
            'id="btn-calcular-rota-mapa"',
            'id="roteiro-mapa-loading"',
            'id="roteiro-mapa-error"',
        ):
            with self.subTest(gancho=gancho):
                self.assertIn(gancho, html)

    def test_os_trechos_tem_pilha_molde_de_data_e_faixa_de_erro(self):
        html = self._html()
        self.assertIn('id="trechos-gerados-container"', html)
        self.assertIn('id="trecho-single-date-picker-template"', html)
        self.assertIn('id="trechos-error"', html)
        self.assertIn('id="trechos-date-picker-park"', html)

    def test_o_retorno_tem_os_campos_que_o_editor_preenche(self):
        html = self._html()
        for campo in (
            'id="id_retorno_saida_cidade"',
            'id="id_retorno_chegada_cidade"',
            'name="retorno_saida_hora"',
            'name="retorno_distancia_km"',
            'id="id_retorno_tempo_total"',
        ):
            with self.subTest(campo=campo):
                self.assertIn(campo, html)

    def test_as_diarias_tem_onde_escrever_o_resultado(self):
        """Inclusive o `#diarias-status`, sem o qual o chip nunca aparecia."""
        html = self._html()
        for gancho in (
            'id="diarias-valor"',
            'id="diarias-extenso"',
            'id="diarias-tipo"',
            'id="diarias-qtd"',
            'id="diarias-error"',
            'id="diarias-status"',
        ):
            with self.subTest(gancho=gancho):
                self.assertIn(gancho, html)

    def test_o_bate_volta_continua_ligado_ao_toggle_de_estado(self):
        html = self._html()
        self.assertIn("data-cv-state-toggle", html)
        self.assertIn('data-cv-state-input="#id_bate_volta_diario_ativo"', html)
        self.assertIn('id="bate-volta-body"', html)
        self.assertIn('name="bate_volta_data_inicio"', html)

    def test_os_dois_modos_do_roteiro_continuam_alternaveis(self):
        html = self._html()
        self.assertIn('id="roteiro-selector-wrapper"', html)
        self.assertIn('id="panel-roteiro-novo"', html)
        self.assertIn('id="id_roteiro_modo_proprio"', html)


class ParseDestinosPostTests(TestCase):
    """A primeira linha do `c-v2.destination_row` vem SEM sufixo.

    Ler só o formato numerado descartaria o primeiro destino em silêncio — e um
    roteiro sem o primeiro destino é um roteiro para outro lugar.
    """

    def test_le_a_primeira_linha_sem_sufixo(self):
        destinos = parse_destinos_post({"destino_estado": "1", "destino_cidade": "2"})
        self.assertEqual(destinos, [(1, 2)])

    def test_le_o_formato_numerado_do_wizard_de_oficio(self):
        destinos = parse_destinos_post(
            {"destino_estado_0": "1", "destino_cidade_0": "2", "destino_estado_1": "3", "destino_cidade_1": "4"}
        )
        self.assertEqual(destinos, [(1, 2), (3, 4)])

    def test_a_linha_sem_sufixo_vem_primeiro_e_as_numeradas_em_ordem(self):
        destinos = parse_destinos_post(
            {
                "destino_estado": "1",
                "destino_cidade": "2",
                "destino_estado_2": "5",
                "destino_cidade_2": "6",
                "destino_estado_1": "3",
                "destino_cidade_1": "4",
            }
        )
        self.assertEqual(destinos, [(1, 2), (3, 4), (5, 6)])

    def test_linha_pela_metade_e_descartada(self):
        self.assertEqual(parse_destinos_post({"destino_estado": "1"}), [])
        self.assertEqual(parse_destinos_post({"destino_estado_1": "1", "destino_cidade_1": ""}), [])
