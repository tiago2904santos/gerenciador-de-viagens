"""Onde cada trecho começa e termina, conferido contra o sistema oficial.

Estes dois roteiros vêm de telas do **sistema oficial de solicitação de
diárias** — o demonstrativo de cálculo dele, com os valores que a
administração efetivamente paga. São a régua: o que este sistema calcula tem
de bater com eles, ao centavo.

A regra que os dois demonstrativos revelam:

* o período de um destino vai da **chegada** nele até a **chegada** no destino
  seguinte — não de uma saída à outra;
* o primeiro período é a exceção: começa na **saída da sede**, porque a viagem
  de ida é faturada no destino para onde se vai;
* o trecho final de volta à sede não gera período próprio: a chegada dele
  apenas fecha o período anterior.

Consequência prática: o tempo de deslocamento entre dois destinos é faturado
na tarifa de **onde o servidor estava**, e não some da conta — que é
exatamente o que acontecia antes (`NOVO-11`).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.test import TestCase

from roteiros.services.diarias import PeriodMarker
from roteiros.services.diarias import calculate_periodized_diarias

SAO_PAULO = ("SAO PAULO", "SP")
ABATIA = ("ABATIA", "PR")
CURITIBA = ("CURITIBA", "PR")


def marcador(saida: datetime, chegada: datetime, destino: tuple[str, str]) -> PeriodMarker:
    return PeriodMarker(
        saida=saida,
        chegada=chegada,
        destino_cidade=destino[0],
        destino_uf=destino[1],
    )


class DemonstrativoOficialTests(TestCase):
    """Cada teste reproduz um demonstrativo do sistema oficial, linha a linha."""

    def calcular(self, markers, chegada_final):
        return calculate_periodized_diarias(
            markers,
            chegada_final,
            quantidade_servidores=1,
            sede_cidade="CURITIBA",
            sede_uf="PR",
        )

    def test_tres_trechos_curitiba_sao_paulo_abatia_curitiba(self):
        """Demonstrativo oficial: total R$ 773,19.

        | Trecho | Grupo    | Período               | Dias/Horas | Diária    |
        |--------|----------|-----------------------|------------|-----------|
        | 1      | Capitais | 12/08 08:00–13/08 18:00 | 1 dia + 10h | R$ 482,64 |
        | 2      | Demais   | 13/08 18:00–14/08 18:00 | 1 dia       | R$ 290,55 |

        As 10 horas do trecho 1 são o deslocamento São Paulo → Abatiá, faturado
        na tarifa da **capital**, de onde o servidor saiu. Antes do `NOVO-11`
        esse tempo caía no trecho de retorno e não era cobrado: R$ 661,81.
        """
        resultado = self.calcular(
            [
                marcador(datetime(2026, 8, 12, 8, 0), datetime(2026, 8, 12, 18, 0), SAO_PAULO),
                marcador(datetime(2026, 8, 13, 8, 0), datetime(2026, 8, 13, 18, 0), ABATIA),
                marcador(datetime(2026, 8, 14, 8, 0), datetime(2026, 8, 14, 18, 0), CURITIBA),
            ],
            datetime(2026, 8, 14, 18, 0),
        )

        self.assertEqual(resultado["totais"]["total_valor_decimal"], Decimal("773.19"))

    def test_tres_trechos_detalhe_por_periodo(self):
        """O total certo pode esconder períodos errados; aqui cada linha é afirmada."""
        resultado = self.calcular(
            [
                marcador(datetime(2026, 8, 12, 8, 0), datetime(2026, 8, 12, 18, 0), SAO_PAULO),
                marcador(datetime(2026, 8, 13, 8, 0), datetime(2026, 8, 13, 18, 0), ABATIA),
                marcador(datetime(2026, 8, 14, 8, 0), datetime(2026, 8, 14, 18, 0), CURITIBA),
            ],
            datetime(2026, 8, 14, 18, 0),
        )
        periodos = resultado["periodos"]

        self.assertEqual(len(periodos), 2)

        capital, interior = periodos
        self.assertEqual(capital["tipo"], "CAPITAL")
        self.assertEqual(capital["data_saida"], "12/08/2026")
        self.assertEqual(capital["hora_saida"], "08:00")
        self.assertEqual(capital["data_chegada"], "13/08/2026")
        self.assertEqual(capital["hora_chegada"], "18:00")
        self.assertEqual(capital["n_diarias"], 1)
        self.assertEqual(capital["percentual_adicional"], 30)
        self.assertEqual(capital["subtotal"], "482,64")

        self.assertEqual(interior["tipo"], "INTERIOR")
        self.assertEqual(interior["data_saida"], "13/08/2026")
        self.assertEqual(interior["hora_saida"], "18:00")
        self.assertEqual(interior["n_diarias"], 1)
        self.assertEqual(interior["percentual_adicional"], 0)
        self.assertEqual(interior["subtotal"], "290,55")

    def test_quatro_trechos_com_retorno_passando_pela_capital(self):
        """Demonstrativo oficial: total R$ 1.144,45.

        | Trecho | Grupo    | Período                 | Dias/Horas  | Diária    |
        |--------|----------|-------------------------|-------------|-----------|
        | 1      | Capitais | 12/08 08:00–13/08 18:00 | 1 dia + 10h | R$ 482,64 |
        | 2      | Demais   | 13/08 18:00–14/08 18:00 | 1 dia       | R$ 290,55 |
        | 3      | Capitais | 14/08 18:00–15/08 18:00 | 1 dia       | R$ 371,26 |

        Caso independente do anterior: a mesma cidade aparece duas vezes, em
        trechos separados, e cada passagem é faturada por si. Antes do
        `NOVO-11`: R$ 1.033,07.
        """
        resultado = self.calcular(
            [
                marcador(datetime(2026, 8, 12, 8, 0), datetime(2026, 8, 12, 18, 0), SAO_PAULO),
                marcador(datetime(2026, 8, 13, 8, 0), datetime(2026, 8, 13, 18, 0), ABATIA),
                marcador(datetime(2026, 8, 14, 8, 0), datetime(2026, 8, 14, 18, 0), SAO_PAULO),
                marcador(datetime(2026, 8, 15, 8, 0), datetime(2026, 8, 15, 18, 0), CURITIBA),
            ],
            datetime(2026, 8, 15, 18, 0),
        )

        self.assertEqual(resultado["totais"]["total_valor_decimal"], Decimal("1144.45"))

    def test_o_deslocamento_entre_destinos_nao_desaparece_da_conta(self):
        """O defeito, dito de forma direta.

        São 10 horas de estrada entre São Paulo e Abatiá. Elas têm de ser
        cobradas em algum lugar; antes não eram cobradas em lugar nenhum.
        """
        resultado = self.calcular(
            [
                marcador(datetime(2026, 8, 12, 8, 0), datetime(2026, 8, 12, 18, 0), SAO_PAULO),
                marcador(datetime(2026, 8, 13, 8, 0), datetime(2026, 8, 13, 18, 0), ABATIA),
                marcador(datetime(2026, 8, 14, 8, 0), datetime(2026, 8, 14, 18, 0), CURITIBA),
            ],
            datetime(2026, 8, 14, 18, 0),
        )

        complementos = [
            p["percentual_adicional"] for p in resultado["periodos"] if p["percentual_adicional"]
        ]
        self.assertEqual(complementos, [30])


class SemHoraDeChegadaTests(TestCase):
    """Quem só conhece um instante por destino (planos de trabalho) não muda.

    O plano de trabalho monta marcadores a partir de eventos, que têm data de
    início e não têm hora de chegada. Nesses casos o instante conhecido **é** a
    chegada ao destino, e o cálculo continua exatamente como era — não há duas
    regras, há uma regra com menos informação disponível.
    """

    def test_marcadores_sem_chegada_mantem_os_limites_por_saida(self):
        sem_chegada = [
            PeriodMarker(saida=datetime(2026, 8, 12, 8, 0), destino_cidade="SAO PAULO", destino_uf="SP"),
            PeriodMarker(saida=datetime(2026, 8, 13, 8, 0), destino_cidade="ABATIA", destino_uf="PR"),
        ]

        resultado = calculate_periodized_diarias(
            sem_chegada,
            datetime(2026, 8, 14, 18, 0),
            quantidade_servidores=1,
            sede_cidade="CURITIBA",
            sede_uf="PR",
        )
        periodos = resultado["periodos"]

        self.assertEqual(periodos[0]["data_chegada"], "13/08/2026")
        self.assertEqual(periodos[0]["hora_chegada"], "08:00")


class RoteiroCompletoTests(TestCase):
    """A ponta que o defeito realmente habitava.

    Os testes acima falam com o motor de cálculo. Este fala com a camada que
    monta os marcadores a partir do estado da tela — que era exatamente onde a
    hora de chegada se perdia. Sem ele, alguém poderia deixar de passar
    ``chegada`` na construção do marcador e a suíte continuaria verde, porque o
    motor sozinho estaria correto.
    """

    def setUp(self):
        from cadastros.models import Cidade
        from cadastros.models import Estado

        self.pr, _ = Estado.objects.get_or_create(sigla="PR", defaults={"nome": "PARANA"})
        self.sp, _ = Estado.objects.get_or_create(sigla="SP", defaults={"nome": "SAO PAULO"})
        self.curitiba, _ = Cidade.objects.get_or_create(
            nome="CURITIBA", estado=self.pr, defaults={"uf": "PR"}
        )
        self.sao_paulo, _ = Cidade.objects.get_or_create(
            nome="SAO PAULO", estado=self.sp, defaults={"uf": "SP"}
        )
        self.abatia, _ = Cidade.objects.get_or_create(
            nome="ABATIA", estado=self.pr, defaults={"uf": "PR"}
        )

    def trecho(self, origem, destino, saida, chegada):
        return {
            "origem_estado_id": origem.estado_id,
            "origem_cidade_id": origem.pk,
            "destino_estado_id": destino.estado_id,
            "destino_cidade_id": destino.pk,
            "saida_data": saida[0],
            "saida_hora": saida[1],
            "chegada_data": chegada[0],
            "chegada_hora": chegada[1],
        }

    def test_o_estado_da_tela_produz_o_valor_do_sistema_oficial(self):
        from roteiros import roteiro_logic

        state = {
            "sede_estado_id": self.pr.pk,
            "sede_cidade_id": self.curitiba.pk,
            "trechos": [
                self.trecho(
                    self.curitiba, self.sao_paulo,
                    ("2026-08-12", "08:00"), ("2026-08-12", "18:00"),
                ),
                self.trecho(
                    self.sao_paulo, self.abatia,
                    ("2026-08-13", "08:00"), ("2026-08-13", "18:00"),
                ),
                self.trecho(
                    self.abatia, self.curitiba,
                    ("2026-08-14", "08:00"), ("2026-08-14", "18:00"),
                ),
            ],
            "retorno": {"chegada_data": "2026-08-14", "chegada_hora": "18:00"},
        }

        resultado = roteiro_logic._calculate_avulso_diarias_from_state(
            state, quantidade_servidores=1
        )

        self.assertEqual(resultado["totais"]["total_valor_decimal"], Decimal("773.19"))
