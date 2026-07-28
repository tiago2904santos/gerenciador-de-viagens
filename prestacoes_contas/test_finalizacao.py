"""Fatia 5/6 de T-01 — arquivamento e finalização.

São as transições que tiram a prestação da mesa. Duas características do
desenho atual ficam registradas aqui, sem juízo de valor:

* os endpoints são **alternadores**, não atribuições — o mesmo POST arquiva e
  desarquiva. Um duplo envio desfaz a ação;
* **não há pré-condição**: finalizar não exige comprovante, relatório técnico
  nem número de solicitação. A decisão é inteiramente do operador.

A segunda pode ser deliberada — é uma pergunta de produto, não um defeito
óbvio. Está travada como está para que uma mudança futura seja uma escolha
explícita, e não um efeito colateral.
"""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from prestacoes_contas.models import PrestacaoServidor
from prestacoes_contas.test_helpers import PrestacaoFixturesMixin


class ArquivamentoTests(PrestacaoFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.setUpPrestacaoFixtures()
        self.fixture = self.criar_prestacao(numero=1)
        self.ps = self.fixture.prestacoes_servidor[0]

    def arquivar(self, ps=None):
        ps = ps or self.ps
        return self.client.post(
            reverse("prestacoes_contas:prestacao_servidor_arquivar", args=[ps.pk])
        )

    def test_arquivar_marca_flag_e_carimba_o_momento(self):
        self.assertFalse(self.ps.arquivada)
        self.assertIsNone(self.ps.arquivada_em)

        self.arquivar()

        self.ps.refresh_from_db()
        self.assertTrue(self.ps.arquivada)
        self.assertIsNotNone(self.ps.arquivada_em)

    def test_segundo_post_desarquiva_e_limpa_o_carimbo(self):
        """O endpoint alterna. Duplo envio desfaz — não é idempotente."""
        self.arquivar()
        self.arquivar()

        self.ps.refresh_from_db()
        self.assertFalse(self.ps.arquivada)
        self.assertIsNone(self.ps.arquivada_em)

    def test_arquivar_move_o_card_para_a_aba_de_arquivados(self):
        self.arquivar()

        padrao = [c["ps_pk"] for c in self.get_listagem().context["cards"]]
        arquivados = [
            c["ps_pk"] for c in self.get_listagem(aba="arquivados").context["cards"]
        ]

        self.assertNotIn(self.ps.pk, padrao)
        self.assertEqual(arquivados, [self.ps.pk])

    def test_get_nao_arquiva(self):
        """A ação é destrutiva o bastante para exigir POST."""
        response = self.client.get(
            reverse("prestacoes_contas:prestacao_servidor_arquivar", args=[self.ps.pk])
        )

        self.assertEqual(response.status_code, 405)
        self.ps.refresh_from_db()
        self.assertFalse(self.ps.arquivada)

    def test_arquivar_servidor_de_outra_area_responde_404(self):
        alheia = self.criar_prestacao(numero=90, area=self.outra_area)
        ps_alheio = alheia.prestacoes_servidor[0]

        response = self.arquivar(ps_alheio)

        self.assertEqual(response.status_code, 404)
        ps_alheio.refresh_from_db()
        self.assertFalse(ps_alheio.arquivada)


class FinalizacaoTests(PrestacaoFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.setUpPrestacaoFixtures()
        self.fixture = self.criar_prestacao(numero=1)
        self.ps = self.fixture.prestacoes_servidor[0]

    def finalizar(self, ps=None):
        ps = ps or self.ps
        return self.client.post(
            reverse("prestacoes_contas:prestacao_servidor_finalizar", args=[ps.pk])
        )

    def test_finalizar_marca_flag_e_carimba_o_momento(self):
        self.finalizar()

        self.ps.refresh_from_db()
        self.assertTrue(self.ps.finalizada)
        self.assertIsNotNone(self.ps.finalizada_em)

    def test_segundo_post_reabre_e_limpa_o_carimbo(self):
        """Também alterna: finalizar não é irreversível nem idempotente."""
        self.finalizar()
        self.finalizar()

        self.ps.refresh_from_db()
        self.assertFalse(self.ps.finalizada)
        self.assertIsNone(self.ps.finalizada_em)

    def test_finalizar_nao_exige_nenhuma_pre_condicao(self):
        """Sem comprovante, sem RT e sem número de solicitação, finaliza igual.

        Caracterização, não aprovação: pode ser decisão de produto (o operador
        é quem julga). Fica travado para que mudar isso seja escolha explícita.
        """
        self.assertEqual(self.ps.numero_solicitacao, "")
        self.assertEqual(self.ps.documentos_anexos.count(), 0)
        self.assertEqual(self.ps.status, PrestacaoServidor.STATUS_PENDENTE)

        self.finalizar()

        self.ps.refresh_from_db()
        self.assertTrue(self.ps.finalizada)
        # A finalização não mexe no status de preenchimento.
        self.assertEqual(self.ps.status, PrestacaoServidor.STATUS_PENDENTE)

    def test_finalizar_move_o_card_para_a_aba_de_finalizados(self):
        self.finalizar()

        padrao = [c["ps_pk"] for c in self.get_listagem().context["cards"]]
        finalizados = [
            c["ps_pk"] for c in self.get_listagem(aba="finalizados").context["cards"]
        ]

        self.assertNotIn(self.ps.pk, padrao)
        self.assertEqual(finalizados, [self.ps.pk])

    def test_finalizar_servidor_de_outra_area_responde_404(self):
        alheia = self.criar_prestacao(numero=91, area=self.outra_area)
        ps_alheio = alheia.prestacoes_servidor[0]

        response = self.finalizar(ps_alheio)

        self.assertEqual(response.status_code, 404)
        ps_alheio.refresh_from_db()
        self.assertFalse(ps_alheio.finalizada)


class AcoesPorOficioTests(PrestacaoFixturesMixin, TestCase):
    """As rotas antigas, por ofício, mantidas por compatibilidade."""

    def setUp(self):
        super().setUp()
        self.setUpPrestacaoFixtures()

    def test_finalizar_por_oficio_atinge_apenas_o_primeiro_servidor(self):
        """Contrato declarado na view: delega ao primeiro servidor, só a ele.

        Num ofício com equipe, a rota antiga finaliza um e deixa os outros —
        por isso a tela usa as rotas por servidor.
        """
        segundo = self.criar_servidor("Servidor Dois")
        fixture = self.criar_prestacao(
            numero=1, servidores=[self.criar_servidor("Servidor Um"), segundo]
        )
        ps_um, ps_dois = fixture.prestacoes_servidor

        self.client.post(
            reverse("prestacoes_contas:prestacao_finalizar", args=[fixture.prestacao.pk])
        )

        ps_um.refresh_from_db()
        ps_dois.refresh_from_db()
        self.assertTrue(ps_um.finalizada)
        self.assertFalse(ps_dois.finalizada)

    def test_acao_por_oficio_de_outra_area_responde_404(self):
        alheia = self.criar_prestacao(numero=92, area=self.outra_area)

        response = self.client.post(
            reverse("prestacoes_contas:prestacao_arquivar", args=[alheia.prestacao.pk])
        )

        self.assertEqual(response.status_code, 404)
        ps_alheio = alheia.prestacoes_servidor[0]
        ps_alheio.refresh_from_db()
        self.assertFalse(ps_alheio.arquivada)
