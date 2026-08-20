"""A lista de roteiros é v2 — e continua sendo lista de roteiros (2026-08-17).

Migrar uma tela tem dois modos de dar errado, e este arquivo guarda os dois:

1. **sobra legado** — a página volta a carregar `entity-cards.css` ou a render um
   `entity_card`, e aí duas linguagens de card convivem na mesma tela;
2. **some função** — a busca do servidor perde o `?q=`, a aba perde o recorte, a
   paginação some ou o botão de excluir deixa de apontar para o diálogo. Nada
   disso levanta erro: a tela fica bonita e não faz mais o que fazia.

O teste anterior desta tela media custo de consulta (`test_custo_da_lista.py`) e
não markup, então a troca de esqueleto passaria inteira por baixo dele.
"""

from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Cidade
from cadastros.models import Estado
from core.testing import area_de_teste
from core.testing import vincular_area
from roteiros.models import Roteiro
from roteiros.models import RoteiroDestino


class ListaDeRoteirosV2Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estado = Estado.objects.create(sigla="PR", nome="Parana")
        cls.origem = Cidade.objects.create(
            nome="CURITIBA", estado=cls.estado, uf="PR", capital=True
        )
        cls.destino = Cidade.objects.create(nome="ARAPONGAS", estado=cls.estado, uf="PR")

    def setUp(self):
        usuario = get_user_model().objects.create_user(username="lista_v2_roteiros")
        vincular_area(usuario)
        self.client.force_login(usuario)
        self.roteiro = self._criar_roteiro(dias=3)

    def _criar_roteiro(self, *, dias):
        roteiro = Roteiro.objects.create(
            area=area_de_teste(),
            origem_estado=self.estado,
            origem_cidade=self.origem,
            saida_dt=timezone.now() + timedelta(days=dias),
            chegada_dt=timezone.now() + timedelta(days=dias, hours=6),
        )
        RoteiroDestino.objects.create(
            roteiro=roteiro, estado=self.estado, cidade=self.destino, ordem=0
        )
        return roteiro

    def _html(self, **params):
        resposta = self.client.get(reverse("roteiros:index"), params)
        self.assertEqual(resposta.status_code, 200)
        return resposta.content.decode()

    # ---- 1. o legado não voltou --------------------------------------------

    def test_a_pagina_nao_carrega_nem_renderiza_o_card_legado(self):
        html = self._html()
        self.assertNotIn("entity-cards.css", html)
        self.assertNotIn("entity-card", html)
        self.assertNotIn("record-card", html)

    def test_o_esqueleto_e_o_do_v2(self):
        html = self._html()
        for marca in ('class="list-page', 'class="rail', 'class="panel', "record "):
            with self.subTest(marca=marca):
                self.assertIn(marca, html)

    # ---- 2. a tela continua fazendo o que fazia -----------------------------

    def test_a_linha_diz_rota_periodo_trechos_e_valor(self):
        html = self._html()
        self.assertIn("CURITIBA/PR", html)
        self.assertIn("ARAPONGAS/PR", html)
        # Valores sem rótulo: "Trechos: 2 trechos" diria a mesma coisa duas vezes.
        # O roteiro do teste não tem trechos gravados, e "0 trechos" é resposta
        # legítima — o que se cobra aqui é a LINHA de meta com as três medidas.
        meta = html[html.index('class="record__meta"') :][:200]
        self.assertRegex(meta, r"\d{2}/\d{2}/\d{4}[^<]* a ")
        self.assertIn("trechos", meta)
        self.assertIn("·", meta)

    def test_a_busca_e_o_multiselect_sao_do_servidor(self):
        """`filter_mode="none"`: filtrar no cliente esconderia as outras páginas."""
        html = self._html(aba=["futuras", "cancelados"])
        self.assertNotIn("data-collection-mode", html)
        self.assertIn('<form method="get"', html)
        self.assertIn('name="q"', html)
        self.assertIn('name="aba"', html)
        self.assertIn("multiple", html)
        self.assertNotIn('type="hidden" name="aba"', html)

    def test_a_busca_do_servidor_filtra_de_verdade(self):
        self.assertIn("ARAPONGAS/PR", self._html(q="arapongas"))
        self.assertNotIn("ARAPONGAS/PR", self._html(q="florianopolis"))

    def test_as_quatro_situacoes_continuam_no_select_v2(self):
        html = self._html()
        for label in ("Que vão acontecer", "Em andamento", "Finalizados", "Cancelados"):
            with self.subTest(aba=label):
                self.assertIn(label, html)
        self.assertIn('aria-label="Filtrar roteiros por situação"', html)
        self.assertIn("data-server-filter-control", html)
        self.assertNotIn("toggle--nav", html)

    def test_multiselect_combina_situacoes_e_preserva_a_query_na_paginacao(self):
        atual = self._criar_roteiro(dias=-3)
        cancelado = self._criar_roteiro(dias=8)
        cancelado.cancelado = True
        cancelado.save(update_fields=["cancelado"])
        query = urlencode(
            [("aba", "futuras"), ("aba", "cancelados")],
            doseq=True,
        )

        resposta = self.client.get(f"{reverse('roteiros:index')}?{query}")

        self.assertEqual(resposta.status_code, 200)
        ids = {roteiro.pk for roteiro in resposta.context["page_obj"].object_list}
        self.assertEqual(ids, {self.roteiro.pk, cancelado.pk})
        self.assertNotIn(atual.pk, ids)
        self.assertEqual(
            resposta.context["abas_selecionadas"],
            ["futuras", "cancelados"],
        )
        self.assertEqual(
            resposta.context["page_querystring"],
            "aba=futuras&aba=cancelados",
        )

    def test_sem_situacao_selecionada_mostra_todos_os_roteiros(self):
        atual = self._criar_roteiro(dias=-3)
        cancelado = self._criar_roteiro(dias=8)
        cancelado.cancelado = True
        cancelado.save(update_fields=["cancelado"])

        resposta = self.client.get(reverse("roteiros:index"))

        self.assertEqual(resposta.status_code, 200)
        ids = {roteiro.pk for roteiro in resposta.context["page_obj"].object_list}
        self.assertEqual(ids, {self.roteiro.pk, atual.pk, cancelado.pk})
        self.assertEqual(resposta.context["abas_selecionadas"], [])
        self.assertFalse(
            any(opcao["selected"] for opcao in resposta.context["status_filter_options"])
        )

    def test_excluir_abre_o_dialogo_v2_com_o_nome_do_roteiro(self):
        """Sem `data-delete-url` no gatilho o `overlay.js` não abre nada."""
        html = self._html()
        self.assertIn('data-overlay-target="delete-confirm-modal"', html)
        self.assertIn(
            'data-delete-url="%s"' % reverse("roteiros:excluir", args=[self.roteiro.pk]),
            html,
        )
        self.assertIn("data-delete-confirm-modal", html)
        self.assertIn("data-delete-confirm-form", html)

    def test_editar_leva_de_volta_para_a_lista(self):
        """O `next` é o que faz o editor voltar para a página em que se estava."""
        html = self._html()
        self.assertIn(reverse("roteiros:editar", args=[self.roteiro.pk]) + "?next=", html)

    def test_o_selo_diz_quanto_falta(self):
        html = self._html()
        self.assertIn("faltam 3 dias", html)
        self.assertIn('data-tone="info"', html)

    def test_a_lista_vazia_diz_que_esta_vazia(self):
        Roteiro.objects.all().delete()
        self.assertIn("Nenhum roteiro cadastrado ainda.", self._html())
