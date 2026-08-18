"""Para onde a pessoa vai depois de salvar uma Ordem de Serviço.

Ia para a própria tela de edição: a mensagem de sucesso aparecia sobre o mesmo
formulário, e nada dizia que o trabalho tinha terminado. Quem salva uma OS quer
conferi-la na lista.

A exceção é a OS nascida dentro de um evento: ali a "lista" é a etapa do evento,
que é de onde a pessoa veio.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from eventos.models import Evento
from ordens_servico.models import OrdemServico
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea


class RedirecionamentoAposSalvarTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área OS", sigla="OS-R")
        self.user = get_user_model().objects.create_user(username="os_redirect")
        VinculoUsuarioArea.objects.create(usuario=self.user, area=self.area, area_padrao=True)
        self.client.force_login(self.user)

    def _payload(self):
        return {"motivo": "Apoio", "tipo_necessidade": OrdemServico.TIPO_CAMINHAO}

    def test_cadastrar_leva_para_a_lista(self):
        resposta = self.client.post(reverse("ordens_servico:nova"), self._payload())

        self.assertRedirects(resposta, reverse("ordens_servico:index"))

    def test_editar_leva_para_a_lista(self):
        ordem = OrdemServico.objects.create(area=self.area)

        resposta = self.client.post(
            reverse("ordens_servico:editar", args=[ordem.pk]), self._payload()
        )

        self.assertRedirects(resposta, reverse("ordens_servico:index"))

    def test_ordem_de_evento_volta_para_a_etapa_do_evento(self):
        evento = Evento.objects.create(area=self.area, titulo="Evento com OS")
        ordem = OrdemServico.objects.create(area=self.area, evento=evento)

        resposta = self.client.post(
            reverse("ordens_servico:editar", args=[ordem.pk]), self._payload()
        )

        self.assertRedirects(
            resposta,
            reverse("eventos:guiado_etapa", kwargs={"pk": evento.pk, "etapa": 4}),
            fetch_redirect_response=False,
        )
