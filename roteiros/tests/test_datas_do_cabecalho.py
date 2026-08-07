"""`NOVO-36` — o cabeçalho de datas do roteiro deriva dos trechos por cronologia.

`_atualizar_datas_roteiro_apos_salvar_trechos` derivava POSICIONALMENTE:
`trechos[0].saida_dt` e `trechos[-2].chegada_dt`. Posição e cronologia coincidem
até a REORDENAÇÃO de destinos, que preserva o horário de cada trecho e troca a
ordem — e aí o cabeçalho saía com chegada antes da saída. Quem achou foi a
constraint `roteiro_ida_ordenada` do `DB-07`, que por isso ficou adiada.

Três famílias de teste aqui, e as três são necessárias:

- **A inversão não acontece mais** — o defeito, nas duas formas (com e sem trecho
  de retorno). A forma sem retorno importa porque a versão antiga usava um ramo
  próprio (`trechos[-1]`), e uma correção que mexesse só no ramo com retorno a
  deixaria passar.
- **O caso normal não mudou** — caracterização. Em roteiro cronologicamente bem
  formado, posicional e cronológica dão o mesmo valor; se este teste ficar
  vermelho, a correção mudou o significado do campo, que não é o que se quer.
- **Os estados degenerados continuam salvando** — em especial o roteiro cujo
  único trecho é o de RETORNO, que o autosave fabrica quando o usuário remove a
  última linha de destino. Uma regra que caísse para "máximo sobre todos os
  trechos" gravaria `retorno.chegada_dt` em `chegada_dt` e violaria
  `roteiro_permanencia_ordenada` — constraint já em produção. Seria trocar dado
  errado por HTTP 500.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from cadastros.models import Cidade
from cadastros.models import Estado
from roteiros.models import Roteiro
from roteiros.models import RoteiroTrecho
from roteiros.roteiro_logic import _atualizar_datas_roteiro_apos_salvar_trechos
from core.testing import area_de_teste

DIA_1 = timezone.make_aware(datetime(2026, 5, 1, 8, 0))
DIA_2 = timezone.make_aware(datetime(2026, 5, 2, 9, 0))
DIA_3 = timezone.make_aware(datetime(2026, 5, 3, 18, 0))


class CabecalhoDeDatasBase(TestCase):
    def setUp(self):
        self.estado = Estado.objects.create(nome="Paraná", sigla="PR")
        self.sede = Cidade.objects.create(estado=self.estado, nome="Curitiba", uf="PR")
        self.destino_a = Cidade.objects.create(estado=self.estado, nome="Londrina", uf="PR")
        self.destino_b = Cidade.objects.create(estado=self.estado, nome="Maringá", uf="PR")
        self.roteiro = Roteiro.objects.create(area=area_de_teste(), 
            origem_estado=self.estado, origem_cidade=self.sede,
        )

    def _trecho(self, ordem, tipo, saida, chegada, destino=None):
        return RoteiroTrecho.objects.create(
            roteiro=self.roteiro,
            ordem=ordem,
            tipo=tipo,
            origem_estado=self.estado,
            origem_cidade=self.sede,
            destino_estado=self.estado,
            destino_cidade=destino or self.destino_a,
            saida_dt=saida,
            chegada_dt=chegada,
        )

    def _derivar(self):
        _atualizar_datas_roteiro_apos_salvar_trechos(self.roteiro)
        self.roteiro.refresh_from_db()
        return self.roteiro


class InversaoNaoAconteceMaisTests(CabecalhoDeDatasBase):
    """O defeito. Cada teste reproduz uma reordenação real de destinos."""

    def test_ida_reordenada_com_retorno_nao_inverte(self):
        # Ordem dos trechos: destino B (02/05) antes de destino A (01/05) — é o
        # que a reordenação produz ao arrastar o segundo destino para cima.
        self._trecho(0, RoteiroTrecho.TIPO_IDA, DIA_2, DIA_2 + timedelta(hours=2), self.destino_b)
        self._trecho(1, RoteiroTrecho.TIPO_IDA, DIA_1, DIA_1 + timedelta(hours=2), self.destino_a)
        self._trecho(2, RoteiroTrecho.TIPO_RETORNO, DIA_3, DIA_3 + timedelta(hours=2), self.sede)

        roteiro = self._derivar()

        self.assertEqual(roteiro.saida_dt, DIA_1, "saída deve ser a mais antiga das idas")
        self.assertEqual(
            roteiro.chegada_dt, DIA_2 + timedelta(hours=2),
            "chegada da ida deve ser a mais recente das idas",
        )
        self.assertLessEqual(roteiro.saida_dt, roteiro.chegada_dt)

    def test_ida_reordenada_sem_retorno_nao_inverte(self):
        """O ramo próprio da versão antiga (`trechos[-1]`), que passava despercebido."""
        self._trecho(0, RoteiroTrecho.TIPO_IDA, DIA_2, DIA_2 + timedelta(hours=2), self.destino_b)
        self._trecho(1, RoteiroTrecho.TIPO_IDA, DIA_1, DIA_1 + timedelta(hours=2), self.destino_a)

        roteiro = self._derivar()

        self.assertEqual(roteiro.saida_dt, DIA_1)
        self.assertEqual(roteiro.chegada_dt, DIA_2 + timedelta(hours=2))
        self.assertLessEqual(roteiro.saida_dt, roteiro.chegada_dt)

    def test_o_banco_agora_recusa_a_inversao(self):
        """A constraint que o `DB-07` adiou. Sem ela, a correção não tem rede."""
        from django.db import IntegrityError
        from django.db import transaction

        self._trecho(0, RoteiroTrecho.TIPO_IDA, DIA_1, DIA_1 + timedelta(hours=2))
        roteiro = self._derivar()

        with self.assertRaises(IntegrityError), transaction.atomic():
            Roteiro.objects.filter(pk=roteiro.pk).update(chegada_dt=DIA_1 - timedelta(days=1))


class CasoNormalNaoMudouTests(CabecalhoDeDatasBase):
    """Caracterização: onde a posição já concordava com a cronologia, nada muda."""

    def test_ida_em_ordem_com_retorno(self):
        self._trecho(0, RoteiroTrecho.TIPO_IDA, DIA_1, DIA_1 + timedelta(hours=2), self.destino_a)
        self._trecho(1, RoteiroTrecho.TIPO_IDA, DIA_2, DIA_2 + timedelta(hours=2), self.destino_b)
        self._trecho(2, RoteiroTrecho.TIPO_RETORNO, DIA_3, DIA_3 + timedelta(hours=2), self.sede)

        roteiro = self._derivar()

        # Exatamente o que a regra posicional produzia: trechos[0].saida,
        # trechos[-2].chegada, trechos[-1].saida, trechos[-1].chegada.
        self.assertEqual(roteiro.saida_dt, DIA_1)
        self.assertEqual(roteiro.chegada_dt, DIA_2 + timedelta(hours=2))
        self.assertEqual(roteiro.retorno_saida_dt, DIA_3)
        self.assertEqual(roteiro.retorno_chegada_dt, DIA_3 + timedelta(hours=2))

    def test_ida_unica_sem_retorno(self):
        self._trecho(0, RoteiroTrecho.TIPO_IDA, DIA_1, DIA_1 + timedelta(hours=2))

        roteiro = self._derivar()

        self.assertEqual(roteiro.saida_dt, DIA_1)
        self.assertEqual(roteiro.chegada_dt, DIA_1 + timedelta(hours=2))
        self.assertIsNone(roteiro.retorno_saida_dt)
        self.assertIsNone(roteiro.retorno_chegada_dt)


class EstadosDegeneradosContinuamSalvandoTests(CabecalhoDeDatasBase):
    """Os estados que o editor fabrica e que uma regra ingênua transformaria em 500."""

    def test_roteiro_so_com_trecho_de_retorno(self):
        """O contraexemplo que derrubou a primeira versão da regra.

        `_salvar_roteiro_avulso_from_roteiro_state` cria o trecho de retorno
        **incondicionalmente** e apaga os demais; o editor esvazia a lista de
        trechos quando o usuário remove a última linha de destino. Uma regra que
        caísse para "máximo sobre todos os trechos" gravaria `retorno.chegada_dt`
        em `chegada_dt`, que por construção vem depois de `retorno_saida_dt` —
        violação determinística de `roteiro_permanencia_ordenada`.
        """
        self._trecho(0, RoteiroTrecho.TIPO_RETORNO, DIA_3, DIA_3 + timedelta(hours=2), self.sede)

        roteiro = self._derivar()  # não pode levantar

        self.assertEqual(roteiro.saida_dt, DIA_3, "sem ida, a viagem começa no retorno")
        self.assertIsNone(roteiro.chegada_dt, "sem ida não existe fim de ida")
        self.assertEqual(roteiro.retorno_saida_dt, DIA_3)
        self.assertEqual(roteiro.retorno_chegada_dt, DIA_3 + timedelta(hours=2))

    def test_rascunho_com_retorno_sem_datas_preserva_o_que_ja_havia(self):
        """Limpar `retorno_*` cegamente apagaria o que o usuário já tinha digitado."""
        self._trecho(0, RoteiroTrecho.TIPO_IDA, DIA_1, DIA_1 + timedelta(hours=2))
        self._trecho(1, RoteiroTrecho.TIPO_RETORNO, None, None, self.sede)
        Roteiro.objects.filter(pk=self.roteiro.pk).update(
            retorno_saida_dt=DIA_3, retorno_chegada_dt=DIA_3 + timedelta(hours=2),
        )
        self.roteiro.refresh_from_db()

        roteiro = self._derivar()

        self.assertEqual(roteiro.retorno_saida_dt, DIA_3)
        self.assertEqual(roteiro.retorno_chegada_dt, DIA_3 + timedelta(hours=2))

    def test_trechos_sem_nenhuma_data_nao_gravam_nada(self):
        self._trecho(0, RoteiroTrecho.TIPO_IDA, None, None)

        roteiro = self._derivar()

        self.assertIsNone(roteiro.saida_dt)
        self.assertIsNone(roteiro.chegada_dt)
