"""`BE-13` fatia 2 — rede para o subgrafo de contexto antes de ele sair do `roteiro_logic`.

`_build_roteiro_form_context` (113 linhas) e as duas funções que só ela usa vão para
`roteiros/presenters.py`. `coverage` apontava **20 linhas descobertas** dentro desse
subgrafo, e duas delas não são detalhe:

- o ramo `roteiro_state is None`, que reconstrói o estado a partir de `trechos_list` +
  `destinos_atuais` (o caminho de compatibilidade dos forms guiados) — nenhum teste
  chamava a fachada sem `roteiro_state`;
- os ramos `qs == 0` e `qs > 1` de `_build_roteiro_diarias_fallback`, que **dividem o
  valor total das diárias pelo número de viajantes**, com `ROUND_HALF_UP`. É dinheiro por
  servidor, exibido na tela, e não havia teste.

Tudo pela fachada pública `montar_contexto_editor_roteiro`, que é o que os chamadores
usam — assim a rede sobrevive à mudança de arquivo.
"""

from decimal import Decimal

from django.test import TestCase

from cadastros.models import Cidade
from cadastros.models import Estado
from core.testing import area_de_teste
from roteiros.forms import RoteiroForm
from roteiros.models import Roteiro
from roteiros.services import montar_contexto_editor_roteiro


class ContextoDoEditorTests(TestCase):
    """O dict que o template do editor recebe."""

    def setUp(self):
        self.estado = Estado.objects.create(nome="Parana CTX", sigla="CX")
        self.sede = Cidade.objects.create(nome="Curitiba CTX", estado=self.estado)
        self.destino = Cidade.objects.create(nome="Londrina CTX", estado=self.estado)

    def _roteiro(self, **campos):
        padrao = dict(
            area=area_de_teste(),
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado,
            origem_cidade=self.sede,
        )
        padrao.update(campos)
        return Roteiro.objects.create(**padrao)

    def _contexto(self, *, roteiro, roteiro_state, destinos=None, trechos=None, servidores=1):
        return montar_contexto_editor_roteiro(
            evento=None,
            form=RoteiroForm(instance=roteiro),
            obj=roteiro,
            destinos_atuais=destinos or [],
            trechos_list=trechos or [],
            is_avulso=True,
            roteiro_state=roteiro_state,
            route_options=[],
            diarias_quantidade_servidores=servidores,
        )

    # -- o ramo `roteiro_state is None` ------------------------------------

    def test_sem_roteiro_state_o_contexto_e_reconstruido_dos_destinos(self):
        """Compatibilidade dos forms guiados: sem estado pronto, monta a partir do resto.

        A sede sai da instância (`origem_estado_id`/`origem_cidade_id`), e o modo é
        forçado para `ROTEIRO_PROPRIO`.
        """
        roteiro = self._roteiro()

        contexto = self._contexto(
            roteiro=roteiro,
            roteiro_state=None,
            destinos=[{"estado_id": self.estado.pk, "cidade_id": self.destino.pk}],
        )

        estado = contexto["roteiro_editor_state_json"]
        self.assertEqual(estado["roteiro_modo"], "ROTEIRO_PROPRIO")
        self.assertEqual(estado["sede_estado_id"], self.estado.pk)
        self.assertEqual(estado["sede_cidade_id"], self.sede.pk)
        self.assertEqual(
            [d["cidade_id"] for d in estado["destinos_atuais"]],
            [self.destino.pk],
            "os destinos passados entram no estado reconstruído",
        )
        self.assertEqual(contexto["sede_estado_id"], self.estado.pk)
        self.assertEqual(contexto["sede_cidade_id"], self.sede.pk)

    def test_sem_roteiro_state_e_sem_instancia_a_sede_fica_vazia(self):
        """`getattr(instance, 'origem_estado_id', None)` com instância sem sede."""
        roteiro = self._roteiro(origem_estado=None, origem_cidade=None)

        contexto = self._contexto(roteiro=roteiro, roteiro_state=None)

        self.assertIsNone(contexto["sede_estado_id"])
        self.assertIsNone(contexto["sede_cidade_id"])

    # -- a divisão do valor por viajante -----------------------------------
    #
    # O estado vazio faz o motor de diárias não produzir resultado, e o contexto cai no
    # `_build_roteiro_diarias_fallback`, que lê o valor já gravado no roteiro.

    def _totais_do_fallback(self, roteiro, servidores):
        contexto = self._contexto(roteiro=roteiro, roteiro_state={}, servidores=servidores)
        resultado = contexto["roteiro_diarias_resultado"]
        self.assertIsNotNone(resultado, "o fallback devia ter assumido")
        return resultado["totais"]

    def test_um_viajante_recebe_o_total(self):
        roteiro = self._roteiro(valor_diarias=Decimal("300.00"), quantidade_diarias="2")

        totais = self._totais_do_fallback(roteiro, servidores=1)

        self.assertEqual(totais["valor_por_servidor_decimal"], Decimal("300.00"))
        self.assertEqual(totais["valor_por_servidor"], "300,00")
        self.assertEqual(totais["quantidade_servidores"], 1)

    def test_varios_viajantes_dividem_o_total(self):
        roteiro = self._roteiro(valor_diarias=Decimal("300.00"), quantidade_diarias="2")

        totais = self._totais_do_fallback(roteiro, servidores=3)

        self.assertEqual(totais["valor_por_servidor_decimal"], Decimal("100.00"))
        self.assertEqual(totais["total_valor"], "300,00", "o total não muda com o rateio")

    def test_o_rateio_arredonda_para_cima_no_meio_centavo(self):
        """`ROUND_HALF_UP`, e não truncamento: 1,00 / 8 = 0,125 vira 0,13.

        O caso que separa os dois. Com truncamento daria 0,12.
        """
        roteiro = self._roteiro(valor_diarias=Decimal("1.00"), quantidade_diarias="1")

        totais = self._totais_do_fallback(roteiro, servidores=8)

        self.assertEqual(totais["valor_por_servidor_decimal"], Decimal("0.13"))
        self.assertEqual(totais["valor_por_servidor"], "0,13")

    def test_zero_viajantes_nao_divide_por_zero(self):
        roteiro = self._roteiro(valor_diarias=Decimal("300.00"), quantidade_diarias="2")

        totais = self._totais_do_fallback(roteiro, servidores=0)

        self.assertEqual(totais["valor_por_servidor_decimal"], Decimal("0.00"))
        self.assertEqual(totais["quantidade_servidores"], 0)

    def test_roteiro_sem_valor_gravado_nao_inventa_diarias(self):
        """As duas saídas antecipadas do fallback, ambas descobertas."""
        roteiro = self._roteiro()

        contexto = self._contexto(roteiro=roteiro, roteiro_state={}, servidores=2)

        self.assertIsNone(contexto["roteiro_diarias_resultado"])
