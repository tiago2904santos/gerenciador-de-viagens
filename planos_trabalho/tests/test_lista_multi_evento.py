"""A lista de Plano de Trabalho quebrava com qualquer plano multi-evento.

`index` fazia `prefetch_related("eventos__destino_cidade__estado")`, e
`EventoPlano` **não tem** `destino_cidade` — os destinos de um evento vivem em
`PlanoDestino`, pela relação `destinos`. O Django só valida o segundo nível de um
prefetch quando o primeiro traz alguma linha, então a lista abria normalmente
enquanto nenhum plano tivesse evento e devolvia 500 assim que um tivesse:

    AttributeError: Cannot find 'destino_cidade' on EventoPlano object,
    'eventos__destino_cidade__estado' is an invalid parameter to prefetch_related()

É por isso que a suíte não pegava: nenhum teste da lista criava `EventoPlano`.
O par de testes aqui existe para fechar exatamente essa fresta — o primeiro
cobre o caso que já funcionava, o segundo o que derrubava a página.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Cidade
from cadastros.models import Estado
from planos_trabalho.models import EventoPlano
from planos_trabalho.models import PlanoDestino
from planos_trabalho.models import PlanoTrabalho


class ListaDePlanosComEventosTests(TestCase):
    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_user(username="pt_multi_evento")
        )
        self.estado = Estado.objects.create(nome="Parana", sigla="PR")
        self.cidade = Cidade.objects.create(nome="Curitiba", estado=self.estado, uf="PR")
        self.inicio = timezone.localdate() - timedelta(days=3)
        self.url = reverse("planos_trabalho:index") + "?aba=atuais"

    def _criar_plano(self, numero):
        return PlanoTrabalho.objects.create(
            numero=numero,
            ano=2026,
            destino_estado=self.estado,
            destino_cidade=self.cidade,
            contextualizacao="Apoio logistico ao evento institucional.",
            data_evento_inicio=self.inicio,
            data_evento_fim=self.inicio + timedelta(days=1),
        )

    def test_lista_abre_com_plano_de_evento_unico(self):
        self._criar_plano(1)

        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_lista_abre_com_plano_multi_evento(self):
        plano = self._criar_plano(2)
        for ordem in range(2):
            evento = EventoPlano.objects.create(
                plano=plano,
                ordem=ordem,
                data_evento_inicio=self.inicio,
                data_evento_fim=self.inicio + timedelta(days=1),
            )
            PlanoDestino.objects.create(
                plano=plano,
                evento=evento,
                estado=self.estado,
                cidade=self.cidade,
                ordem=ordem,
            )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        # Um card por plano — o plano tem dois eventos, nao dois cards.
        self.assertEqual(len(response.context["cards"]), 1)

    def test_o_card_do_plano_multi_evento_mostra_o_destino_do_evento(self):
        """Sem isto, apagar o prefetch quebrado poderia levar o destino junto."""
        plano = self._criar_plano(3)
        evento = EventoPlano.objects.create(
            plano=plano,
            ordem=0,
            data_evento_inicio=self.inicio,
            data_evento_fim=self.inicio + timedelta(days=1),
        )
        PlanoDestino.objects.create(
            plano=plano, evento=evento, estado=self.estado, cidade=self.cidade, ordem=0
        )

        response = self.client.get(self.url)

        cards = response.context["cards"]
        self.assertEqual(len(cards), 1)
        # O nome da cidade e gravado em caixa alta pelo model.
        self.assertIn(f"{self.cidade.nome}/PR", cards[0]["destino"])
