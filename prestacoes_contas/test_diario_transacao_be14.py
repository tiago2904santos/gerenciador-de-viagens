"""`BE-14` fatia 4 — rede para a gravação do diário de bordo, a última do defeito.

Três caminhos de escrita em `diario_views.py`, nenhum em transação:

1. **O autosave**, que grava `linha.save(update_fields=[campo])` **um por campo sujo**
   dentro de um laço, e depois `diario.save()`. Digitar km inicial e km final da mesma
   linha são duas gravações; uma falha entre elas deixa metade.
2. **A troca de motorista/viatura**, que grava três vezes: o form do diário, a prévia de
   "informações complementares" do RT, e a marcação de status. Uma falha no meio deixa o
   motorista trocado com o texto do RT desatualizado — e é justamente o texto que explica
   a troca no documento.
3. **O POST do formset**, que grava N linhas de km e abastecimento de uma vez.

`sincronizar_trechos` já é `@transaction.atomic` desde o `DB-08` fatia 2, e é chamada
antes destes três. Ou seja: a parte que **cria** as linhas do diário é atômica, e a parte
que **preenche** não era.

Como nas fatias 1 e 3, as duas rotas de autosave divergem na marcação de status —
`diario_servidor_autosave` marca só o servidor da URL, `diario_autosave` marca a equipe
pendente inteira. E como na fatia 1, a rota por servidor **não tinha teste nenhum**.

Uma nota de fixture que vale para quem escrever teste de diário: `criar_prestacao` monta
um ofício **sem roteiro**, e sem roteiro `sincronizar_trechos` não cria linha nenhuma —
o autosave passa a ser um laço sobre lista vazia e todo cenário vira verde por omissão.
`_com_roteiro` existe para isso.
"""

from __future__ import annotations

import json
from unittest import expectedFailure
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from core.testing import area_de_teste
from oficios.models import Oficio
from prestacoes_contas.models import DiarioBordo
from prestacoes_contas.models import DiarioBordoTrecho
from prestacoes_contas.models import PrestacaoServidor
from prestacoes_contas.models import RelatorioTecnico
from prestacoes_contas.test_helpers import PrestacaoFixturesMixin
from roteiros.models import Roteiro
from roteiros.models import RoteiroTrecho


def _com_roteiro(oficio, trechos=1):
    """Dá ao ofício um roteiro com trechos — sem isso o diário nasce sem linhas."""
    roteiro = Roteiro.objects.create(area=area_de_teste())
    for ordem in range(trechos):
        RoteiroTrecho.objects.create(roteiro=roteiro, tipo=RoteiroTrecho.TIPO_IDA, ordem=ordem)
    Oficio.objects.filter(pk=oficio.pk).update(roteiro=roteiro)
    oficio.refresh_from_db()
    return roteiro


class DiarioAutosaveTests(PrestacaoFixturesMixin, TestCase):
    """O autosave do diário, pelas duas rotas."""

    def setUp(self):
        super().setUp()
        self.setUpPrestacaoFixtures()
        self.fixture = self.criar_prestacao(
            numero=71,
            servidores=[self.criar_servidor("Um DB"), self.criar_servidor("Dois DB")],
        )
        _com_roteiro(self.fixture.oficio)
        self.prestacao = self.fixture.prestacao
        self.ps_a, self.ps_b = self.fixture.prestacoes_servidor
        self.diario, _ = DiarioBordo.objects.get_or_create(prestacao=self.prestacao)

    def _payload(self, campos):
        return json.dumps(
            {
                "model": "diario_bordo",
                "object_id": str(self.diario.pk),
                "dirty_fields": list(campos),
                "fields": campos,
            }
        )

    def autosave_por_servidor(self, **campos):
        """`diario_servidor_autosave` — a rota que não tinha teste nenhum."""
        return self.client.post(
            reverse("prestacoes_contas:diario_servidor_autosave", args=[self.ps_a.pk]),
            data=self._payload(campos),
            content_type="application/json",
        )

    def autosave_por_diario(self, **campos):
        return self.client.post(
            reverse("prestacoes_contas:diario_autosave", args=[self.diario.pk]),
            data=self._payload(campos),
            content_type="application/json",
        )

    def _linhas(self):
        return list(self.diario.trechos.order_by("ordem", "pk"))

    def test_a_fixture_produz_linha_de_diario(self):
        """Guarda contra o cenário vazio: sem linha, os testes abaixo não medem nada."""
        self.client.get(reverse("prestacoes_contas:diario_servidor", args=[self.ps_a.pk]))
        self.assertTrue(self._linhas(), "sem linha de diário a rede seria verde por omissão")

    def test_autosave_por_servidor_grava_km_e_abastecimento(self):
        resposta = self.autosave_por_servidor(
            **{"form-0-km_inicial": "1.200", "form-0-abastecimento": "sim"}
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(json.loads(resposta.content)["ok"])
        linha = self._linhas()[0]
        self.assertEqual(linha.km_inicial, 1200)
        self.assertTrue(linha.abastecimento)

    def test_as_duas_rotas_marcam_status_diferente(self):
        """A mesma divergência de escopo das fatias 1 e 3, travada antes de extrair."""
        self.autosave_por_servidor(**{"form-0-km_inicial": "10"})

        self.ps_a.refresh_from_db()
        self.ps_b.refresh_from_db()
        self.assertEqual(self.ps_a.status, PrestacaoServidor.STATUS_EM_PREENCHIMENTO)
        self.assertEqual(
            self.ps_b.status,
            PrestacaoServidor.STATUS_PENDENTE,
            "a rota por servidor não pode marcar o colega",
        )

        self.autosave_por_diario(**{"form-0-km_final": "20"})

        self.ps_b.refresh_from_db()
        self.assertEqual(
            self.ps_b.status,
            PrestacaoServidor.STATUS_EM_PREENCHIMENTO,
            "a rota por diário marca todos os pendentes",
        )

    @expectedFailure
    def test_falha_no_meio_do_laco_nao_deixa_meia_gravacao(self):
        """O defeito. **Reprova antes da correção.**

        Dois campos sujos da mesma linha, e a segunda gravação falha. Sem transação, o
        primeiro campo já está no banco — o operador vê km inicial gravado e km final
        não, sem nada dizendo que faltou.
        """
        original = DiarioBordoTrecho.save
        chamadas = []
        CAMPOS_DO_AUTOSAVE = {"km_inicial", "km_final", "abastecimento"}

        def falhar_na_segunda(self_linha, *args, **kwargs):
            # Só conta as gravações do **laço do autosave**. `sincronizar_trechos` roda
            # antes, na mesma requisição, e também salva `DiarioBordoTrecho` — contar as
            # dela fazia a falha cair antes do laço começar, e o teste passava sem medir
            # nada. Foi assim que ele apareceu verde na primeira tentativa.
            if set(kwargs.get("update_fields") or ()) & CAMPOS_DO_AUTOSAVE:
                chamadas.append(self_linha.pk)
                if len(chamadas) == 2:
                    raise RuntimeError("falha no meio do laço do diário")
            return original(self_linha, *args, **kwargs)

        with mock.patch.object(DiarioBordoTrecho, "save", falhar_na_segunda):
            with self.assertRaises(RuntimeError):
                self.autosave_por_diario(
                    **{"form-0-km_inicial": "500", "form-0-km_final": "900"}
                )

        linha = self._linhas()[0]
        self.assertIsNone(
            linha.km_inicial,
            "sobrou meia gravação: o primeiro campo entrou e o segundo não",
        )


class TrocaDeMotoristaTests(PrestacaoFixturesMixin, TestCase):
    """A troca de motorista/viatura grava três vezes, e nenhuma em transação."""

    def setUp(self):
        super().setUp()
        self.setUpPrestacaoFixtures()
        self.outro = self.criar_servidor("Condutor Novo")
        self.fixture = self.criar_prestacao(
            numero=72, servidores=[self.criar_servidor("Titular DB"), self.outro]
        )
        _com_roteiro(self.fixture.oficio)
        self.prestacao = self.fixture.prestacao
        self.ps = self.fixture.prestacoes_servidor[0]
        self.diario, _ = DiarioBordo.objects.get_or_create(prestacao=self.prestacao)
        self.relatorio = RelatorioTecnico.objects.create(prestacao=self.prestacao)

    def url(self):
        return reverse("prestacoes_contas:diario_servidor_motorista", args=[self.ps.pk])

    def trocar(self, **campos):
        dados = {
            "motorista_modo": DiarioBordo.MOTORISTA_MODO_SERVIDOR,
            "motorista_servidor": self.outro.pk,
            "viatura_modo": self.diario.viatura_modo or "OFICIO",
        }
        dados.update(campos)
        return self.client.post(self.url(), dados)

    def test_troca_grava_o_diario_e_marca_o_servidor(self):
        resposta = self.trocar()

        self.assertEqual(resposta.status_code, 302)
        self.diario.refresh_from_db()
        self.ps.refresh_from_db()
        self.assertEqual(self.diario.motorista_modo, DiarioBordo.MOTORISTA_MODO_SERVIDOR)
        self.assertEqual(self.diario.motorista_servidor_id, self.outro.pk)
        self.assertEqual(self.ps.status, PrestacaoServidor.STATUS_EM_PREENCHIMENTO)

    @expectedFailure
    def test_falha_ao_sincronizar_o_rt_nao_deixa_o_motorista_trocado_sozinho(self):
        """O segundo defeito. **Reprova antes da correção.**

        A troca grava o diário, depois gera a prévia de "informações complementares" do
        RT — que é o texto que **explica a troca** no documento — e depois marca o
        status. Se a segunda falhar, o motorista fica trocado e o documento sai sem a
        explicação, sem nada na tela dizendo isso.
        """
        def falhar(_prestacao):
            raise RuntimeError("falha ao sincronizar o RT depois da troca")

        with mock.patch(
            "prestacoes_contas.diario_views._sincronizar_info_complementares_rt", falhar
        ):
            with self.assertRaises(RuntimeError):
                self.trocar()

        self.diario.refresh_from_db()
        self.assertNotEqual(
            self.diario.motorista_modo,
            DiarioBordo.MOTORISTA_MODO_SERVIDOR,
            "o motorista ficou trocado com o RT não sincronizado",
        )
