"""Toda etapa navegável do wizard tem que oferecer "Voltar" e "Avançar".

A etapa 3 (Transporte) era a única sem rodapé: dependia do stepper e do autosave
para o usuário sair dela. A view **já** tratava `wizard_back` e `wizard_next` — o
backend estava pronto e só faltava oferecer os botões.

A etapa 2 (Roteiro) *parecia* estar sem também. Não estava: os botões dela vêm de
um include aninhado no editor de roteiro, invisível para um `grep` no template da
etapa. Só medir a **tela renderizada** mostrou isso — e o que denunciou foi um
canário que não disparou.

Por isso as asserções aqui contam ocorrências no HTML renderizado em vez de
procurar a string `wizard_next`: ela aparece na página por outros caminhos, então
`assertIn` passaria mesmo sem rodapé nenhum. Foi exatamente o falso verde que a
primeira versão deste arquivo teve.
"""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from oficios.models import Oficio
from core.testing import area_de_teste
from core.testing import vincular_area


class RodapeDasEtapasNavegaveisTests(TestCase):
    #: as quatro primeiras etapas avançam; a 5ª é a última e fecha o fluxo
    ETAPAS_QUE_AVANCAM = (
        "oficios:dados_viajantes",
        "oficios:wizard_roteiro",
        "oficios:transporte",
        "oficios:wizard_justificativa",
    )

    def setUp(self):
        usuario = get_user_model().objects.create_user(username="wizard_rodape")
        vincular_area(usuario)
        self.client.force_login(usuario)
        self.oficio = Oficio.objects.create(area=area_de_teste(), data_criacao=date(2026, 8, 1))

    def _corpo(self, url_name):
        response = self.client.get(reverse(url_name, args=[self.oficio.pk]))
        self.assertEqual(response.status_code, 200, url_name)
        return response.content.decode()

    def test_toda_etapa_navegavel_tem_botao_de_avancar(self):
        for url_name in self.ETAPAS_QUE_AVANCAM:
            with self.subTest(etapa=url_name):
                corpo = self._corpo(url_name)

                # Exatamente um "Avançar": mais de um significa rodapé duplicado,
                # que foi o erro da primeira tentativa nesta mudança.
                self.assertEqual(corpo.count('value="wizard_next"'), 1)
                self.assertIn("Avançar", corpo)

    def test_a_etapa_de_transporte_ganhou_o_rodape_que_faltava(self):
        corpo = self._corpo("oficios:transporte")

        self.assertEqual(corpo.count('value="wizard_next"'), 1)
        self.assertEqual(corpo.count('value="wizard_back"'), 1)

    def test_nenhuma_etapa_duplica_o_rodape(self):
        """Guarda contra o erro que eu cometi: adicionar um rodapé onde já havia."""
        for url_name in self.ETAPAS_QUE_AVANCAM:
            with self.subTest(etapa=url_name):
                corpo = self._corpo(url_name)

                self.assertLessEqual(corpo.count('value="wizard_back"'), 1)

    def test_a_view_reconhece_as_acoes_que_o_template_emite(self):
        """Um botão com `action` que a view ignora navegaria para lugar nenhum."""
        from oficios.views import _wizard_normalizar_acao

        self.assertEqual(
            _wizard_normalizar_acao({"action": "wizard_next"}), "wizard_next"
        )
        self.assertEqual(
            _wizard_normalizar_acao({"action": "wizard_back"}), "wizard_back"
        )
        # `save_continue` é o nome antigo e continua caindo em avançar.
        self.assertEqual(
            _wizard_normalizar_acao({"action": "save_continue"}), "wizard_next"
        )
