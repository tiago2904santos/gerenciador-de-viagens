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
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import Unidade
from core.testing import area_de_teste
from core.testing import com_request
from core.testing import vincular_area
from planos_trabalho.efetivo_services import reconciliar_efetivo
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

    def test_falha_no_meio_do_laco_nao_deixa_meia_reconciliacao(self):
        """O defeito, e a garantia que esta fatia entrega.

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

    def test_falha_ao_recalcular_a_diaria_nao_deixa_o_efetivo_reconciliado_sozinho(self):
        """O segundo defeito, e o mais caro.

        O efetivo é reconciliado e **depois** a diária é recalculada — o valor da diária
        é função do total do efetivo. Se o recálculo falhar, o plano fica com o efetivo
        novo e o valor antigo, que é a definição de dado errado em documento de dinheiro.

        A falha é injetada na gravação do próprio plano (`update_fields` do snapshot de
        diárias), e não num nome de módulo: é a primeira escrita **depois** da
        reconciliação, antes e depois da extração.

        Reprovava no commit da rede; passou a valer com `salvar_efetivo_e_diarias`.
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


class ReconciliarEfetivoSozinhaTests(TestCase):
    """`reconciliar_efetivo` chamada direto, sem a transação de quem a envolve.

    Existe porque `atomic` aninhado vira **SAVEPOINT**: com `salvar_efetivo_e_diarias`
    atômica por fora, tirar o decorador de `reconciliar_efetivo` não reprova nada pela
    rota HTTP, e a função pública ficaria sem rede própria. Um chamador futuro que
    entrasse direto aqui herdaria a meia gravação de volta — foi o que a fatia 1 mediu em
    `salvar_diarias_recebidas`, e o `BE-12` já tinha pago essa conta antes.
    """

    def setUp(self):
        _, self.curitiba, self.maringa, _ = criar_base_geografica()
        configurar_sistema(self.curitiba)
        self.plano = criar_plano_maringa(self.maringa, efetivo=6)
        self.efetivo = self.plano.efetivos.first()
        self.cargo_extra = Cargo.objects.create(area=area_de_teste(), nome="Escrivão")

    def linhas(self):
        return [
            {
                "idx": 0,
                "id": self.efetivo.pk,
                "unidade": self.efetivo.unidade_id,
                "cargo": self.efetivo.cargo_id,
                "quantidade": 9,
            },
            {"idx": 1, "id": None, "unidade": None, "cargo": self.cargo_extra.pk, "quantidade": 4},
        ]

    def test_chamada_direta_reconcilia_as_duas_linhas(self):
        # `reconciliar_efetivo` valida cargo e unidade contra a área corrente. Fora de um
        # request não há área no thread-local e **toda linha seria descartada em
        # silêncio** — o cenário de falha viraria um laço sobre lista vazia, verde por
        # omissão. Mesma armadilha do `NOVO-106`, noutro app.
        with com_request(area_de_teste()):
            saida = reconciliar_efetivo(self.plano, self.linhas())

        self.assertEqual(len(saida), 2)
        self.efetivo.refresh_from_db()
        self.assertEqual(self.efetivo.quantidade, 9)

    def test_chamada_direta_com_falha_no_laco_nao_deixa_meia_reconciliacao(self):
        original = EfetivoPlano.save
        chamadas = []

        def falhar_na_segunda(self_efetivo, *args, **kwargs):
            chamadas.append(self_efetivo.pk)
            if len(chamadas) == 2:
                raise RuntimeError("falha no meio do laço, sem transação de fora")
            return original(self_efetivo, *args, **kwargs)

        with com_request(area_de_teste()):
            with mock.patch.object(EfetivoPlano, "save", falhar_na_segunda):
                with self.assertRaises(RuntimeError):
                    reconciliar_efetivo(self.plano, self.linhas())

        self.efetivo.refresh_from_db()
        self.assertEqual(
            self.efetivo.quantidade,
            6,
            "sem a transação própria, quem chama o service direto herda a meia gravação",
        )
        self.assertEqual(self.plano.efetivos.count(), 1)


class EfetivoPeloAutosaveTests(TestCase):
    """A rota de autosave da etapa 2 — a irmã do `POST`, com a mesma sequência."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester_be14_pta", password="123456"
        )
        self.client.force_login(self.user)
        vincular_area(self.user)
        _, self.curitiba, self.maringa, _ = criar_base_geografica()
        configurar_sistema(self.curitiba)
        self.plano = criar_plano_maringa(self.maringa, efetivo=6)
        self.efetivo = self.plano.efetivos.first()

    def autosave(self):
        return self.client.post(
            reverse("planos_trabalho:efetivo_diarias_autosave", args=[self.plano.pk]),
            data=json.dumps(
                {
                    "model": "plano_trabalho",
                    "object_id": str(self.plano.pk),
                    "dirty_fields": ["chegada_sede_data"],
                    "fields": {"chegada_sede_data": "2026-06-29"},
                    "snapshots": {
                        "efetivo": [
                            {
                                "idx": 0,
                                "id": self.efetivo.pk,
                                "unidade": self.efetivo.unidade_id,
                                "cargo": self.efetivo.cargo_id,
                                "quantidade": 9,
                            }
                        ]
                    },
                }
            ),
            content_type="application/json",
        )

    def test_autosave_reconcilia_o_efetivo_e_recalcula(self):
        resposta = self.autosave()

        self.assertTrue(resposta.json()["ok"])
        self.efetivo.refresh_from_db()
        self.assertEqual(self.efetivo.quantidade, 9)

    def test_autosave_falha_ao_recalcular_nao_deixa_o_efetivo_sozinho(self):
        """Mesma garantia do `POST`, pela rota que o navegador usa sem clique.

        Sem esta, `salvar_efetivo_do_autosave` ficaria com um `@transaction.atomic` que
        nenhum teste faz morder — decorador sem rede é o que a fatia 1 chamou de
        garantia vazia.
        """
        original = PlanoTrabalho.save

        def falhar_no_snapshot(self_plano, *args, **kwargs):
            if "diarias_valor_total" in set(kwargs.get("update_fields") or ()):
                raise RuntimeError("falha ao recalcular a diária no autosave")
            return original(self_plano, *args, **kwargs)

        with mock.patch.object(PlanoTrabalho, "save", falhar_no_snapshot):
            with self.assertRaises(RuntimeError):
                self.autosave()

        self.efetivo.refresh_from_db()
        self.assertEqual(
            self.efetivo.quantidade,
            6,
            "o autosave reconciliou o efetivo e não recalculou a diária",
        )


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

    def test_falha_ao_recalcular_a_diaria_nao_deixa_os_textos_gravados(self):
        """O terceiro defeito.

        `wizard_identificacao` grava três vezes o mesmo plano: o formulário, os textos
        padrão regenerados e o snapshot de diárias. Uma falha no terceiro deixa o plano
        com o texto que descreve o destino novo e o **valor da diária do destino
        antigo** — os dois no mesmo documento, sem nada apontando a contradição.

        Reprovava no commit da rede; passou a valer com `salvar_identificacao_do_wizard`.
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

    def test_autosave_falha_ao_gravar_os_textos_nao_deixa_o_campo_gravado(self):
        """O quarto defeito.

        O autosave grava o formulário e **depois** os textos padrão regenerados. Se o
        segundo falhar, o campo digitado está salvo e o texto que deriva dele não —
        exatamente o estado que o modo automático existe para impedir.

        Reprovava no commit da rede; passou a valer com `salvar_identificacao_do_autosave`.
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
