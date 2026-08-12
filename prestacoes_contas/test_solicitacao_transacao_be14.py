"""`BE-14` fatia 2 — rede para a gravação da solicitação, antes de ela sair da view.

Duas rotas implementam a mesma regra (número da solicitação, data de liberação e prazo
limite), e elas **divergem em três pontos**, todos já fotografados em
`test_solicitacao.py`. Esta fatia não decide qual comportamento é o certo: ela move a
gravação para um service com transação e **preserva o que está fotografado**. Unificar as
rotas muda o que o operador vê e é decisão própria.

O que esta rede acrescenta ao que já existia:

1. **A gravação parcial do autosave, com `ok=False`.** `prestacao_servidor_solicitacao_autosave`
   grava o número, depois valida a data de liberação, e se ela for inválida **retorna erro
   com o número já gravado**. Nenhum teste fotografava isso, e é o comportamento que a
   transação **não pode** mudar sem decisão — `return` não é exceção, então o `atomic`
   commita e o número continua salvo.
2. **Falha real no meio do laço do lote.** `_salvar_solicitacoes_em_lote` percorre N
   servidores e grava um por um. Se o terceiro falhar, os dois primeiros ficam. É o
   defeito do `BE-14`, e é o único cenário aqui que **reprova hoje**.
3. **Três `save()` no mesmo objeto numa requisição.** O autosave grava campo a campo, e
   cada gravação dispara a marcação de status — até seis escritas numa requisição só.

Os testes de divergência que já existem (`test_solicitacao.py:178` e `:192`) citam
`NOVO-09` no docstring, mas o `NOVO-09` do catálogo é outro defeito — modelo de
justificativa sem `area`. A divergência das solicitações nunca teve entrada própria.
"""

from __future__ import annotations

import json
from datetime import date
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from prestacoes_contas.models import PrestacaoServidor
from prestacoes_contas.test_helpers import PrestacaoFixturesMixin


class SolicitacaoAutosaveParcialTests(PrestacaoFixturesMixin, TestCase):
    """O autosave grava campo a campo, e o erro chega depois da primeira gravação."""

    def setUp(self):
        super().setUp()
        self.setUpPrestacaoFixtures()
        self.fixture = self.criar_prestacao(numero=51)
        self.ps = self.fixture.prestacoes_servidor[0]

    def autosave(self, **campos):
        payload = {
            "model": "prestacao_servidor",
            "object_id": str(self.ps.pk),
            "dirty_fields": list(campos),
            "fields": campos,
        }
        return self.client.post(
            reverse("prestacoes_contas:prestacao_servidor_solicitacao_autosave", args=[self.ps.pk]),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_numero_fica_gravado_mesmo_quando_a_data_seguinte_e_recusada(self):
        """A gravação parcial que o autosave faz hoje, fotografada.

        O operador digita número e data na mesma tela. A data sai inválida, ele recebe
        "Data de liberação inválida." — e o número **já está no banco**, sem nada dizendo
        isso. Preservado nesta fatia de propósito: mudar aqui é decisão de produto, não de
        camada.
        """
        resposta = self.autosave(
            numero_solicitacao="SOL-2026-1",
            data_liberacao_diarias="01/09/2026",
        )

        corpo = json.loads(resposta.content)
        self.assertFalse(corpo["ok"])
        self.assertEqual(corpo["message"], "Data de liberação inválida.")

        self.ps.refresh_from_db()
        self.assertEqual(
            self.ps.numero_solicitacao,
            "SOL-2026-1",
            "o número foi gravado antes de a data ser validada — é o comportamento de hoje",
        )
        self.assertIsNone(self.ps.data_liberacao_diarias)

    def test_prazo_invalido_deixa_numero_e_liberacao_gravados(self):
        """A mesma coisa um passo adiante: dois campos gravados, o terceiro recusado."""
        resposta = self.autosave(
            numero_solicitacao="SOL-2026-2",
            data_liberacao_diarias="2026-09-01",
            prazo_limite_saque="15/09/2026",
        )

        corpo = json.loads(resposta.content)
        self.assertFalse(corpo["ok"])
        self.assertEqual(corpo["message"], "Data de prazo limite inválida.")

        self.ps.refresh_from_db()
        self.assertEqual(self.ps.numero_solicitacao, "SOL-2026-2")
        self.assertEqual(self.ps.data_liberacao_diarias, date(2026, 9, 1))
        self.assertIsNone(self.ps.prazo_limite_saque)

    def test_tudo_valido_grava_os_tres_campos_e_marca_o_servidor(self):
        resposta = self.autosave(
            numero_solicitacao="SOL-2026-3",
            data_liberacao_diarias="2026-09-01",
            prazo_limite_saque="2026-09-15",
        )

        self.assertTrue(json.loads(resposta.content)["ok"])
        self.ps.refresh_from_db()
        self.assertEqual(self.ps.numero_solicitacao, "SOL-2026-3")
        self.assertEqual(self.ps.data_liberacao_diarias, date(2026, 9, 1))
        self.assertEqual(self.ps.prazo_limite_saque, date(2026, 9, 15))
        self.assertEqual(self.ps.status, PrestacaoServidor.STATUS_EM_PREENCHIMENTO)

    def test_campo_ausente_do_payload_nao_e_apagado(self):
        """`None` significa "não veio", e não "limpar" — o autosave manda só o sujo."""
        self.autosave(data_liberacao_diarias="2026-09-01")
        self.autosave(numero_solicitacao="SOL-2026-4")

        self.ps.refresh_from_db()
        self.assertEqual(self.ps.numero_solicitacao, "SOL-2026-4")
        self.assertEqual(
            self.ps.data_liberacao_diarias,
            date(2026, 9, 1),
            "a segunda requisição não mandou a data, e ela não podia sumir",
        )


class SolicitacaoEmLoteTransacaoTests(PrestacaoFixturesMixin, TestCase):
    """O caminho sem JS: um `UPDATE` por servidor, num laço, sem transação."""

    def setUp(self):
        super().setUp()
        self.setUpPrestacaoFixtures()
        self.primeiro = self.criar_servidor("Primeiro SOL")
        self.segundo = self.criar_servidor("Segundo SOL")
        self.fixture = self.criar_prestacao(
            numero=52, servidores=[self.primeiro, self.segundo]
        )
        self.ps_a, self.ps_b = self.fixture.prestacoes_servidor

    def salvar_em_lote(self, **por_servidor):
        dados = {"action": "save_solicitacoes"}
        for ps, campos in por_servidor.items():
            for nome, valor in campos.items():
                dados[f"ps-{ps}-{nome}"] = valor
        return self.client.post(reverse("prestacoes_contas:index"), dados)

    def test_lote_grava_os_dois_servidores(self):
        self.salvar_em_lote(
            **{
                str(self.ps_a.pk): {"numero_solicitacao": "LOTE-A"},
                str(self.ps_b.pk): {"numero_solicitacao": "LOTE-B"},
            }
        )

        self.ps_a.refresh_from_db()
        self.ps_b.refresh_from_db()
        self.assertEqual(self.ps_a.numero_solicitacao, "LOTE-A")
        self.assertEqual(self.ps_b.numero_solicitacao, "LOTE-B")

    def test_falha_no_meio_do_laco_nao_deixa_meia_gravacao(self):
        """Era o defeito do `BE-14` no lote, e é a razão de o service ser atômico.

        Reprovava no commit da rede e passou a valer quando o laço saiu da view para
        `solicitacao_services.salvar_solicitacoes_em_lote`.
        """
        original = PrestacaoServidor.save
        chamadas = []

        def falhar_na_segunda(self_ps, *args, **kwargs):
            chamadas.append(self_ps.pk)
            if len(chamadas) == 2:
                raise RuntimeError("falha no meio do lote de solicitações")
            return original(self_ps, *args, **kwargs)

        with mock.patch.object(PrestacaoServidor, "save", falhar_na_segunda):
            with self.assertRaises(RuntimeError):
                self.salvar_em_lote(
                    **{
                        str(self.ps_a.pk): {"numero_solicitacao": "LOTE-A"},
                        str(self.ps_b.pk): {"numero_solicitacao": "LOTE-B"},
                    }
                )

        self.ps_a.refresh_from_db()
        self.ps_b.refresh_from_db()
        self.assertEqual(self.ps_a.numero_solicitacao, "")
        self.assertEqual(self.ps_b.numero_solicitacao, "")
