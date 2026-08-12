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
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase

from roteiros.services.diarias import PeriodMarker
from roteiros.services.diarias import calculate_periodized_diarias

SAO_PAULO = ("SAO PAULO", "SP")
ABATIA = ("ABATIA", "PR")
FLORIANOPOLIS = ("FLORIANOPOLIS", "SC")
ADRIANOPOLIS = ("ADRIANOPOLIS", "PR")
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

    def test_destinos_seguidos_do_mesmo_grupo_formam_um_trecho_so(self):
        """Demonstrativo oficial: total R$ 1.169,47, num **único** trecho.

        | Trecho | Grupo    | Período                 | Dias/Horas | Diária      |
        |--------|----------|-------------------------|------------|-------------|
        | 1      | Capitais | 12/08 08:00–15/08 16:00 | 3 dias + 8h | R$ 1.169,47 |

        São Paulo, Florianópolis e São Paulo de novo — três destinos, um trecho.
        O oficial funde períodos consecutivos do mesmo grupo tarifário e cobra
        **um** complemento sobre a sobra da soma (8h → 15%).

        É o caso que decidiu o `N-05`. As sobras de cada permanência isolada
        (6h, 2h, 0h) não chegam a 6 horas e nenhuma geraria complemento sozinha;
        somadas dentro do trecho, dão 8h e valem 15%.
        """
        resultado = self.calcular(
            [
                marcador(datetime(2026, 8, 12, 8, 0), datetime(2026, 8, 12, 18, 0), SAO_PAULO),
                marcador(datetime(2026, 8, 13, 8, 0), datetime(2026, 8, 13, 14, 0), FLORIANOPOLIS),
                marcador(datetime(2026, 8, 14, 8, 0), datetime(2026, 8, 14, 16, 0), SAO_PAULO),
                marcador(datetime(2026, 8, 15, 8, 0), datetime(2026, 8, 15, 16, 0), CURITIBA),
            ],
            datetime(2026, 8, 15, 16, 0),
        )

        self.assertEqual(resultado["totais"]["total_valor_decimal"], Decimal("1169.47"))
        self.assertEqual(len(resultado["periodos"]), 1)

        trecho = resultado["periodos"][0]
        self.assertEqual(trecho["tipo"], "CAPITAL")
        self.assertEqual(trecho["data_saida"], "12/08/2026")
        self.assertEqual(trecho["hora_saida"], "08:00")
        self.assertEqual(trecho["data_chegada"], "15/08/2026")
        self.assertEqual(trecho["hora_chegada"], "16:00")
        self.assertEqual(trecho["n_diarias"], 3)
        self.assertEqual(trecho["percentual_adicional"], 15)

    def test_grupo_diferente_no_meio_quebra_a_sequencia(self):
        """A fusão é de consecutivos: um interior no meio abre trecho novo.

        É o demonstrativo de quatro trechos — capital, interior, capital. As
        duas capitais não se fundem porque não são vizinhas.
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

        self.assertEqual(
            [p["tipo"] for p in resultado["periodos"]],
            ["CAPITAL", "INTERIOR", "CAPITAL"],
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
        from roteiros.services import editor_state_builder

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

        resultado = editor_state_builder._calculate_avulso_diarias_from_state(
            state, quantidade_servidores=1
        )

        self.assertEqual(resultado["totais"]["total_valor_decimal"], Decimal("773.19"))


class EscadaDoRestoTests(TestCase):
    """`N-08` / `N-10` — quanto vale o tempo que sobra depois dos dias inteiros.

    A escada vem de cinco demonstrativos do sistema oficial, um deles um
    experimento desenhado para isolar a variável: 12h01 **dentro do mesmo dia**,
    sem nenhuma virada de meia-noite, rendendo 100% da diária. Isso prova que o
    corte é por **duração**, não por calendário.

        resto ≤ 6h        →   0%
        resto > 6h  ≤ 8h  →  15%
        resto > 8h  ≤ 12h →  30%
        resto > 12h       → 100%

    Antes, o cálculo tinha teto de 30% acima de 8h e uma exceção que dava diária
    inteira a qualquer período que cruzasse a meia-noite. Errava nos dois
    sentidos: pagava a menos em toda viagem acima de 12 horas e cobrava diária
    cheia por dois minutos entre 23:59 e 00:01.
    """

    def calcular(self, markers, chegada_final):
        return calculate_periodized_diarias(
            markers, chegada_final, quantidade_servidores=1,
            sede_cidade="CURITIBA", sede_uf="PR",
        )

    def test_doze_horas_e_um_minuto_no_mesmo_dia_rendem_diaria_inteira(self):
        """Demonstrativo oficial: R$ 290,55, e o experimento que decidiu a regra.

        | Trecho | Grupo  | Período                 | Dias/Horas  | Diária    |
        |--------|--------|-------------------------|-------------|-----------|
        | 1      | Demais | 12/08 08:00–12/08 20:01 | 0 dias + 12h01 | R$ 290,55 |

        Sai às 08:00 e volta às 20:01 do **mesmo dia**. Não há pernoite, não há
        virada de data — e mesmo assim vale uma diária cheia. Antes daqui o
        sistema pagava R$ 87,17 (o teto de 30%): R$ 203,38 a menos.
        """
        resultado = self.calcular(
            [
                marcador(datetime(2026, 8, 12, 8, 0), datetime(2026, 8, 12, 12, 0), ADRIANOPOLIS),
                marcador(datetime(2026, 8, 12, 19, 0), datetime(2026, 8, 12, 20, 1), CURITIBA),
            ],
            datetime(2026, 8, 12, 20, 1),
        )

        self.assertEqual(resultado["totais"]["total_valor_decimal"], Decimal("290.55"))
        trecho = resultado["periodos"][0]
        self.assertEqual(trecho["tipo"], "INTERIOR")
        self.assertEqual(trecho["n_diarias"], 0)
        self.assertEqual(trecho["percentual_adicional"], 100)

    def test_dezesseis_horas_atravessando_a_madrugada(self):
        """Demonstrativo oficial: R$ 371,26, como **0 dias + 16h**.

        O total já batia antes, mas por outro caminho: o código chamava isso de
        "uma diária inteira" por ter cruzado a meia-noite. Coincidência —
        70% + 30% também dá 100%.
        """
        resultado = self.calcular(
            [
                marcador(datetime(2026, 8, 12, 20, 0), datetime(2026, 8, 13, 2, 0), SAO_PAULO),
                marcador(datetime(2026, 8, 13, 6, 0), datetime(2026, 8, 13, 12, 0), CURITIBA),
            ],
            datetime(2026, 8, 13, 12, 0),
        )

        self.assertEqual(resultado["totais"]["total_valor_decimal"], Decimal("371.26"))
        trecho = resultado["periodos"][0]
        self.assertEqual(trecho["n_diarias"], 0)
        self.assertEqual(trecho["percentual_adicional"], 100)

    def test_a_escada_completa(self):
        """As quatro faixas, medidas na função que decide."""
        from roteiros.services.diarias import _segment_breakdown

        base = datetime(2026, 8, 12, 6, 0)
        casos = {
            5: 0, 6: 0,          # ate 6h: nada
            7: 15, 8: 15,        # >6h ate 8h
            9: 30, 12: 30,       # >8h ate 12h
            13: 100, 20: 100,    # >12h: diaria inteira
        }
        for horas, esperado in casos.items():
            with self.subTest(horas=horas):
                _dias, parcial, _h, _t = _segment_breakdown(base, base + timedelta(hours=horas))
                self.assertEqual(parcial, esperado)

    def test_cruzar_a_meia_noite_nao_e_mais_criterio(self):
        """Dois minutos entre 23:59 e 00:01 valiam uma diária inteira.

        Valem zero: é menos de 6 horas. O calendário saiu do cálculo — o que
        sobrava eram duas definições de "diária integral" convivendo (`N-08`),
        e o pernoite curto era o sintoma visível (`N-10`).
        """
        from roteiros.services.diarias import _segment_breakdown

        dias, parcial, _h, _t = _segment_breakdown(
            datetime(2026, 8, 12, 23, 59), datetime(2026, 8, 13, 0, 1)
        )

        self.assertEqual(dias, 0)
        self.assertEqual(parcial, 0)

    def test_dia_inteiro_mais_resto_longo_soma_duas_diarias(self):
        """44 horas = 1 dia + 20h. O resto passa de 12h, então vale outra diária.

        É a forma comum de viagem — sair de manhã e voltar de madrugada dois
        dias depois — e era onde o teto de 30% custava mais caro: R$ 482,64 no
        lugar de R$ 742,52.
        """
        from roteiros.services.diarias import _segment_breakdown

        dias, parcial, _h, _t = _segment_breakdown(
            datetime(2026, 8, 12, 8, 0), datetime(2026, 8, 14, 4, 0)
        )

        self.assertEqual(dias, 1)
        self.assertEqual(parcial, 100)


class ReconciliacaoPorServidorTests(TestCase):
    """`N-09` — o valor por servidor tem de fechar com o total.

    O documento mostra os dois: o ofício traz o total da equipe, o relatório
    técnico traz o valor daquele servidor. Se `por_servidor × servidores` não
    der `total`, os dois papéis não batem — e quem confere não tem como saber
    qual está certo.

    A auditoria registra isso como possível. Não reproduz: cada trecho calcula
    `valor_1_servidor × servidores`, então o total é o produto exato e a divisão
    de volta não perde centavo. O que faltava era a afirmação — sem ela, uma
    mudança futura no arredondamento quebraria isso em silêncio.

    O teste existente `test_total_valor_multiplica_servidores` prova que o total
    **escala** com a equipe. É outra afirmação: escalar não garante reconciliar.
    """

    def cenario(self, nome):
        roteiros = {
            "misto": (
                [
                    marcador(datetime(2026, 8, 12, 8, 0), datetime(2026, 8, 12, 18, 0), SAO_PAULO),
                    marcador(datetime(2026, 8, 13, 8, 0), datetime(2026, 8, 13, 18, 0), ABATIA),
                    marcador(datetime(2026, 8, 14, 8, 0), datetime(2026, 8, 14, 18, 0), CURITIBA),
                ],
                datetime(2026, 8, 14, 18, 0),
            ),
            "categoria_unica": (
                [
                    marcador(datetime(2026, 8, 12, 8, 0), datetime(2026, 8, 12, 18, 0), SAO_PAULO),
                    marcador(datetime(2026, 8, 13, 8, 0), datetime(2026, 8, 13, 14, 0), FLORIANOPOLIS),
                    marcador(datetime(2026, 8, 14, 8, 0), datetime(2026, 8, 14, 16, 0), SAO_PAULO),
                    marcador(datetime(2026, 8, 15, 8, 0), datetime(2026, 8, 15, 16, 0), CURITIBA),
                ],
                datetime(2026, 8, 15, 16, 0),
            ),
            "com_complemento": (
                [
                    marcador(datetime(2026, 8, 12, 8, 0), datetime(2026, 8, 12, 12, 0), ABATIA),
                    marcador(datetime(2026, 8, 12, 19, 0), datetime(2026, 8, 12, 20, 1), CURITIBA),
                ],
                datetime(2026, 8, 12, 20, 1),
            ),
        }
        return roteiros[nome]

    def test_o_valor_por_servidor_reconstroi_o_total(self):
        for nome in ("misto", "categoria_unica", "com_complemento"):
            markers, chegada = self.cenario(nome)
            for servidores in (1, 2, 3, 7):
                with self.subTest(roteiro=nome, servidores=servidores):
                    totais = calculate_periodized_diarias(
                        markers, chegada, quantidade_servidores=servidores,
                        sede_cidade="CURITIBA", sede_uf="PR",
                    )["totais"]

                    self.assertEqual(
                        totais["valor_por_servidor_decimal"] * servidores,
                        totais["total_valor_decimal"],
                        "o valor por servidor não reconstrói o total",
                    )

    def test_equipe_sem_servidor_nao_divide_por_zero(self):
        markers, chegada = self.cenario("misto")

        totais = calculate_periodized_diarias(
            markers, chegada, quantidade_servidores=0,
            sede_cidade="CURITIBA", sede_uf="PR",
        )["totais"]

        self.assertEqual(totais["valor_por_servidor_decimal"], Decimal("0.00"))
        self.assertEqual(totais["total_valor_decimal"], Decimal("0.00"))
