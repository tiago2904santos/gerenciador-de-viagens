"""`BE-14` fatia 5 — rede para a gravação de planos de trabalho.

`planos_trabalho/services.py` tem **1.314 linhas e zero `transaction.atomic`** — é um dos
três módulos que o enunciado do `BE-14` cita pelo nome. As gravações moram nas views, em
sequências de duas a quatro escritas sem nada em volta.

Três caminhos, e o que uma falha no meio deixa:

1. **`wizard_efetivo_diarias`** — `_apply_efetivo_snapshot` reconcilia o efetivo linha a
   linha (`save` para quem já existia, `create` para quem é novo, `delete` para quem saiu),
   e só depois o plano recalcula a diária. É a função com mais gravações soltas do sistema
   inteiro, e grava **em laço**.
2. **`wizard_identificacao`** — três `save()` no mesmo plano: o do formulário, o dos textos
   padrão regenerados e o do snapshot de diárias. O terceiro é dinheiro: uma falha ali
   deixa o plano com o destino novo e o **valor da diária do destino antigo**.
3. **`identificacao_autosave`** — o mesmo par, sem a diária: o form e depois os textos.

A cobertura de caminho feliz já existe (`test_views.py` tem quatro cenários de efetivo e
três de identificação). O que não existe em `planos_trabalho` é **um único teste de
rollback** — igual ao que acontecia em prestações antes das fatias 1 a 4.

Nota de método, herdada da fatia 4: contar `save()` para injetar a falha só funciona se a
contagem distinguir a gravação que se quer medir das que a mesma requisição faz por outro
motivo. Por isso os contadores abaixo olham `update_fields`, e não só a ordem.
"""

from __future__ import annotations

import json
from unittest import expectedFailure
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import Unidade
from core.testing import area_de_teste
from core.testing import vincular_area
from planos_trabalho.models import EfetivoPlano
from planos_trabalho.models import PlanoTrabalho

from .helpers import configurar_sistema
from .helpers import criar_base_geografica
from .helpers import criar_plano_maringa


class EfetivoDoPlanoTests(TestCase):
    """`_apply_efetivo_snapshot`: `save` + `create` + `delete`, em laço, sem transação."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester_be14_pt", password="123456")
        self.client.force_login(self.user)
        vincular_area(self.user)
        _, self.curitiba, self.maringa, _ = criar_base_geografica()
        configurar_sistema(self.curitiba)
        self.plano = criar_plano_maringa(self.maringa, efetivo=6)
        self.efetivo = self.plano.efetivos.first()
        self.unidade_extra = Unidade.objects.create(
            area=area_de_teste(), nome="Delegacia Regional", sigla="DR"
        )
        self.cargo_extra = Cargo.objects.create(area=area_de_teste(), nome="Investigador")

    def url(self):
        return reverse("planos_trabalho:wizard_efetivo_diarias", args=[self.plano.pk])

    def postar(self, *, quantidade_primeira="9"):
        """Uma linha existente (com quantidade nova) e uma linha nova — nessa ordem."""
        return self.client.post(
            self.url(),
            {
                "action": "wizard_next",
                "efetivo-TOTAL_FORMS": "2",
                "efetivo-INITIAL_FORMS": "1",
                "efetivo-MIN_NUM_FORMS": "1",
                "efetivo-MAX_NUM_FORMS": "1000",
                "efetivo-0-id": self.efetivo.pk,
                "efetivo-0-plano": self.plano.pk,
                "efetivo-0-unidade": self.efetivo.unidade_id,
                "efetivo-0-cargo": self.efetivo.cargo_id,
                "efetivo-0-quantidade": quantidade_primeira,
                "efetivo-1-id": "",
                "efetivo-1-plano": self.plano.pk,
                "efetivo-1-unidade": self.unidade_extra.pk,
                "efetivo-1-cargo": self.cargo_extra.pk,
                "efetivo-1-quantidade": "4",
                "saida_sede_data": "2026-06-24",
                "saida_sede_hora": "07:00",
                "chegada_sede_data": "2026-06-28",
                "chegada_sede_hora": "14:00",
            },
        )

    def test_post_reconcilia_as_duas_linhas(self):
        """Caminho feliz, para que o cenário de falha não seja verde por omissão."""
        resposta = self.postar()

        self.assertEqual(resposta.status_code, 302)
        linhas = list(self.plano.efetivos.order_by("pk"))
        self.assertEqual(len(linhas), 2)
        self.assertEqual(linhas[0].quantidade, 9)
        self.assertEqual(linhas[1].cargo_id, self.cargo_extra.pk)

    @expectedFailure
    def test_falha_no_meio_do_laco_nao_deixa_meia_reconciliacao(self):
        """O defeito. **Reprova antes da correção.**

        A primeira linha é atualizada e a segunda falha ao ser criada. Sem transação, a
        quantidade nova da primeira já está no banco enquanto a linha nova não existe —
        e o total do efetivo, que é a base do cálculo da diária, fica errado sem que
        nada na tela diga isso.
        """
        original = EfetivoPlano.save
        chamadas = []

        def falhar_na_segunda(self_efetivo, *args, **kwargs):
            chamadas.append(self_efetivo.pk)
            if len(chamadas) == 2:
                raise RuntimeError("falha no meio do laço do efetivo")
            return original(self_efetivo, *args, **kwargs)

        with mock.patch.object(EfetivoPlano, "save", falhar_na_segunda):
            with self.assertRaises(RuntimeError):
                self.postar()

        self.efetivo.refresh_from_db()
        self.assertEqual(
            self.efetivo.quantidade,
            6,
            "a primeira linha ficou com a quantidade nova e a segunda não entrou",
        )
        self.assertEqual(self.plano.efetivos.count(), 1)

    @expectedFailure
    def test_falha_ao_recalcular_a_diaria_nao_deixa_o_efetivo_reconciliado_sozinho(self):
        """O segundo defeito, e o mais caro. **Reprova antes da correção.**

        O efetivo é reconciliado e **depois** a diária é recalculada — o valor da diária
        é função do total do efetivo. Se o recálculo falhar, o plano fica com o efetivo
        novo e o valor antigo, que é a definição de dado errado em documento de dinheiro.

        A falha é injetada na gravação do próprio plano (`update_fields` do snapshot de
        diárias), e não num nome de módulo: é a primeira escrita **depois** da
        reconciliação, antes e depois da extração.
        """
        original = PlanoTrabalho.save

        def falhar_no_snapshot(self_plano, *args, **kwargs):
            campos = set(kwargs.get("update_fields") or ())
            if "diarias_valor_total" in campos:
                raise RuntimeError("falha ao recalcular a diária depois do efetivo")
            return original(self_plano, *args, **kwargs)

        with mock.patch.object(PlanoTrabalho, "save", falhar_no_snapshot):
            with self.assertRaises(RuntimeError):
                self.postar()

        self.efetivo.refresh_from_db()
        self.assertEqual(
            self.efetivo.quantidade,
            6,
            "o efetivo mudou e a diária não foi recalculada: o plano ficou com valor de "
            "um efetivo que não é mais o dele",
        )
        self.assertEqual(self.plano.efetivos.count(), 1)


class IdentificacaoDoPlanoTests(TestCase):
    """`wizard_identificacao` e o autosave: dois e três `save()` no mesmo plano."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester_be14_id", password="123456")
        self.client.force_login(self.user)
        vincular_area(self.user)
        _, self.curitiba, self.maringa, _ = criar_base_geografica()
        configurar_sistema(self.curitiba)
        self.plano = criar_plano_maringa(self.maringa, efetivo=6)

    def dados_do_formulario(self, **extra):
        dados = {
            "action": "save_draft",
            "destino_estado": self.maringa.estado_id,
            "destino_cidade": self.maringa.pk,
            "data_evento_inicio": "2026-06-25",
            "data_evento_fim": "2026-06-27",
            "saida_sede_data": "2026-06-24",
            "saida_sede_hora": "07:00",
            "chegada_sede_data": "2026-06-28",
            "chegada_sede_hora": "14:00",
        }
        dados.update(extra)
        return dados

    @expectedFailure
    def test_falha_ao_recalcular_a_diaria_nao_deixa_os_textos_gravados(self):
        """O terceiro defeito. **Reprova antes da correção.**

        `wizard_identificacao` grava três vezes o mesmo plano: o formulário, os textos
        padrão regenerados e o snapshot de diárias. Uma falha no terceiro deixa o plano
        com o texto que descreve o destino novo e o **valor da diária do destino
        antigo** — os dois no mesmo documento, sem nada apontando a contradição.
        """
        original = PlanoTrabalho.save

        def falhar_no_snapshot(self_plano, *args, **kwargs):
            campos = set(kwargs.get("update_fields") or ())
            if "diarias_valor_total" in campos:
                raise RuntimeError("falha ao recalcular a diária depois dos textos")
            return original(self_plano, *args, **kwargs)

        antes = PlanoTrabalho.objects.get(pk=self.plano.pk).contextualizacao

        with mock.patch.object(PlanoTrabalho, "save", falhar_no_snapshot):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    reverse("planos_trabalho:wizard_identificacao", args=[self.plano.pk]),
                    self.dados_do_formulario(data_evento_fim="2026-06-29"),
                )

        depois = PlanoTrabalho.objects.get(pk=self.plano.pk)
        self.assertEqual(
            depois.contextualizacao,
            antes,
            "os textos foram regravados numa operação que falhou",
        )
        self.assertEqual(depois.data_evento_fim.isoformat(), "2026-06-27")

    @expectedFailure
    def test_autosave_falha_ao_gravar_os_textos_nao_deixa_o_campo_gravado(self):
        """O quarto defeito. **Reprova antes da correção.**

        O autosave grava o formulário e **depois** os textos padrão regenerados. Se o
        segundo falhar, o campo digitado está salvo e o texto que deriva dele não —
        exatamente o estado que o modo automático existe para impedir.
        """
        original = PlanoTrabalho.save
        chamadas = []

        def falhar_na_segunda(self_plano, *args, **kwargs):
            chamadas.append(set(kwargs.get("update_fields") or ()))
            if len(chamadas) == 2:
                raise RuntimeError("falha ao regravar os textos padrão")
            return original(self_plano, *args, **kwargs)

        url = reverse("planos_trabalho:identificacao_autosave", args=[self.plano.pk])
        payload = {
            "model": "plano_trabalho",
            "object_id": str(self.plano.pk),
            "dirty_fields": ["data_evento_fim"],
            "fields": {"data_evento_fim": "2026-06-29"},
        }

        with mock.patch.object(PlanoTrabalho, "save", falhar_na_segunda):
            with self.assertRaises(RuntimeError):
                self.client.post(url, data=json.dumps(payload), content_type="application/json")

        self.plano.refresh_from_db()
        self.assertEqual(
            self.plano.data_evento_fim.isoformat(),
            "2026-06-27",
            "o campo entrou e o texto que deriva dele não",
        )
