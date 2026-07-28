from datetime import datetime
from decimal import Decimal

from django.test import TestCase

from roteiros import roteiro_logic
from roteiros.services.diarias import (
    PeriodMarker,
    TABELA_DIARIAS,
    calculate_periodized_diarias,
)


class DiariasServiceTests(TestCase):
    def test_periodizacao_inclui_percentual_30_no_retorno_final(self):
        markers = [
            PeriodMarker(
                saida=datetime(2026, 5, 1, 8, 0),
                destino_cidade="FLORIANOPOLIS",
                destino_uf="SC",
            ),
            PeriodMarker(
                saida=datetime(2026, 5, 4, 10, 0),
                destino_cidade="CURITIBA",
                destino_uf="PR",
            ),
        ]
        resultado = calculate_periodized_diarias(
            markers,
            datetime(2026, 5, 4, 19, 0),
            quantidade_servidores=1,
            sede_cidade="CURITIBA",
            sede_uf="PR",
        )

        self.assertEqual(resultado["totais"]["total_diarias"], "3 x 100% + 1 x 30%")
        expected_total = (TABELA_DIARIAS["CAPITAL"]["24h"] * 3) + TABELA_DIARIAS["CAPITAL"]["30"]
        self.assertEqual(resultado["totais"]["total_valor_decimal"], expected_total)

    def test_viagem_unica_gera_apenas_um_percentual_complementar(self):
        # Uma única viagem (saída da sede → retorno à sede) não pode acumular um
        # complemento por trecho. Aqui são 3 pernoites + ~15h30 além das noites
        # inteiras, o que gera UM único complemento de 30% sobre a viagem toda —
        # e não 15% de um trecho somado a 30% de outro.
        markers = [
            PeriodMarker(
                saida=datetime(2026, 5, 1, 8, 0),
                destino_cidade="FLORIANOPOLIS",
                destino_uf="SC",
            ),
            PeriodMarker(
                saida=datetime(2026, 5, 4, 15, 0),
                destino_cidade="CURITIBA",
                destino_uf="PR",
            ),
        ]
        resultado = calculate_periodized_diarias(
            markers,
            datetime(2026, 5, 4, 23, 30),
            quantidade_servidores=1,
            sede_cidade="CURITIBA",
            sede_uf="PR",
        )

        self.assertEqual(resultado["totais"]["total_diarias"], "3 x 100% + 1 x 30%")
        expected_total = (TABELA_DIARIAS["CAPITAL"]["24h"] * 3) + TABELA_DIARIAS["CAPITAL"]["30"]
        self.assertEqual(resultado["totais"]["total_valor_decimal"], expected_total)

    def test_multiplos_destinos_nao_somam_complemento_por_trecho(self):
        # Curitiba -> Maringá (interior) -> Londrina (interior) -> Curitiba.
        # Cada parada intermediária tem sobra de horas que, isolada, geraria um
        # complemento próprio. A viagem, porém, é única: o resultado deve refletir
        # o total de pernoites da viagem inteira e, no máximo, um complemento —
        # nunca a soma dos complementos de cada trecho.
        markers = [
            PeriodMarker(
                saida=datetime(2026, 5, 1, 8, 0),
                destino_cidade="MARINGA",
                destino_uf="PR",
            ),
            PeriodMarker(
                saida=datetime(2026, 5, 1, 20, 0),
                destino_cidade="LONDRINA",
                destino_uf="PR",
            ),
            PeriodMarker(
                saida=datetime(2026, 5, 3, 10, 0),
                destino_cidade="CURITIBA",
                destino_uf="PR",
            ),
        ]
        resultado = calculate_periodized_diarias(
            markers,
            datetime(2026, 5, 3, 14, 0),
            quantidade_servidores=1,
            sede_cidade="CURITIBA",
            sede_uf="PR",
        )

        # 05-01 08:00 -> 05-03 14:00 = 2 pernoites + 6h (<=6h -> sem complemento).
        self.assertEqual(resultado["totais"]["total_diarias"], "2 x 100%")
        expected_total = TABELA_DIARIAS["INTERIOR"]["24h"] * 2
        self.assertEqual(resultado["totais"]["total_valor_decimal"], expected_total)

    def test_roteiro_que_mistura_categorias_tem_complemento_por_permanencia(self):
        # Curitiba 12/08 08:00 -> Florianópolis; sai de lá 13/08 15:00 -> Cambé;
        # sai de Cambé 14/08 08:00 e chega em Curitiba 14/08 12:00.
        # Misturando capital e interior, cada permanência é faturada na sua tarifa e
        # com o próprio complemento: 31h em Florianópolis = 1 diária + 7h -> 15%.
        markers = [
            PeriodMarker(
                saida=datetime(2026, 8, 12, 8, 0),
                destino_cidade="FLORIANOPOLIS",
                destino_uf="SC",
            ),
            PeriodMarker(
                saida=datetime(2026, 8, 13, 15, 0),
                destino_cidade="CAMBE",
                destino_uf="PR",
            ),
            PeriodMarker(
                saida=datetime(2026, 8, 14, 8, 0),
                destino_cidade="CURITIBA",
                destino_uf="PR",
            ),
        ]
        resultado = calculate_periodized_diarias(
            markers,
            datetime(2026, 8, 14, 12, 0),
            quantidade_servidores=1,
            sede_cidade="CURITIBA",
            sede_uf="PR",
        )

        self.assertEqual(resultado["totais"]["total_diarias"], "2 x 100% + 1 x 15%")
        expected_total = (
            TABELA_DIARIAS["CAPITAL"]["24h"]
            + TABELA_DIARIAS["CAPITAL"]["15"]
            + TABELA_DIARIAS["INTERIOR"]["24h"]
        )
        self.assertEqual(resultado["totais"]["total_valor_decimal"], expected_total)

    def test_volta_para_sede_nao_carrega_o_complemento(self):
        # Bate-volta a partir de uma sede que é capital: as 14h fora rendem 30%, mas
        # na tarifa do destino visitado (interior) — a volta pra casa não pode puxar
        # o complemento para a tarifa da própria sede.
        markers = [
            PeriodMarker(
                saida=datetime(2026, 8, 18, 8, 0),
                destino_cidade="CAMBE",
                destino_uf="PR",
            ),
            PeriodMarker(
                saida=datetime(2026, 8, 18, 16, 0),
                destino_cidade="CURITIBA",
                destino_uf="PR",
            ),
        ]
        resultado = calculate_periodized_diarias(
            markers,
            datetime(2026, 8, 18, 22, 0),
            quantidade_servidores=1,
            sede_cidade="CURITIBA",
            sede_uf="PR",
        )

        self.assertEqual(resultado["totais"]["total_diarias"], "1 x 30%")
        self.assertEqual(
            resultado["totais"]["total_valor_decimal"],
            TABELA_DIARIAS["INTERIOR"]["30"],
        )

    def test_trechos_seguidos_no_mesmo_horario_nao_invalidam_o_calculo(self):
        # Curitiba -> Cambé -> Cianorte -> Curitiba, com o segundo destino no mesmo
        # dia do primeiro. Quando as horas de saída coincidem, a parada tem duração
        # zero: ela não gera diária, mas também não pode derrubar o cálculo.
        markers = [
            PeriodMarker(
                saida=datetime(2026, 8, 10, 8, 0),
                destino_cidade="CAMBE",
                destino_uf="PR",
            ),
            PeriodMarker(
                saida=datetime(2026, 8, 12, 8, 0),
                destino_cidade="CIANORTE",
                destino_uf="PR",
            ),
            PeriodMarker(
                saida=datetime(2026, 8, 12, 8, 0),
                destino_cidade="MARINGA",
                destino_uf="PR",
            ),
        ]
        resultado = calculate_periodized_diarias(
            markers,
            datetime(2026, 8, 12, 20, 0),
            quantidade_servidores=1,
            sede_cidade="MARINGA",
            sede_uf="PR",
        )

        # 10/08 08:00 -> 12/08 20:00 = 2 pernoites em Cambé + 12h de sobra (-> 30%).
        self.assertEqual(resultado["totais"]["total_diarias"], "2 x 100% + 1 x 30%")
        expected_total = (TABELA_DIARIAS["INTERIOR"]["24h"] * 2) + TABELA_DIARIAS["INTERIOR"]["30"]
        self.assertEqual(resultado["totais"]["total_valor_decimal"], expected_total)

    def test_ida_e_volta_no_mesmo_dia_e_no_mesmo_horario(self):
        markers = [
            PeriodMarker(
                saida=datetime(2026, 8, 18, 8, 0),
                destino_cidade="CAMBE",
                destino_uf="PR",
            ),
            PeriodMarker(
                saida=datetime(2026, 8, 18, 8, 0),
                destino_cidade="MARINGA",
                destino_uf="PR",
            ),
        ]
        resultado = calculate_periodized_diarias(
            markers,
            datetime(2026, 8, 18, 22, 0),
            quantidade_servidores=1,
            sede_cidade="MARINGA",
            sede_uf="PR",
        )

        # Sem pernoite: 14h fora da sede -> apenas o complemento de 30%.
        self.assertEqual(resultado["totais"]["total_diarias"], "1 x 30%")
        self.assertEqual(
            resultado["totais"]["total_valor_decimal"],
            TABELA_DIARIAS["INTERIOR"]["30"],
        )

    def test_periodizacao_sem_percentual_complementar(self):
        markers = [
            PeriodMarker(
                saida=datetime(2026, 5, 1, 8, 0),
                destino_cidade="FLORIANOPOLIS",
                destino_uf="SC",
            ),
            PeriodMarker(
                saida=datetime(2026, 5, 3, 8, 0),
                destino_cidade="CURITIBA",
                destino_uf="PR",
            ),
        ]
        resultado = calculate_periodized_diarias(
            markers,
            datetime(2026, 5, 3, 12, 0),
            quantidade_servidores=1,
            sede_cidade="CURITIBA",
            sede_uf="PR",
        )

        self.assertEqual(resultado["totais"]["total_diarias"], "2 x 100%")

    def test_total_valor_multiplica_servidores(self):
        markers = [
            PeriodMarker(
                saida=datetime(2026, 5, 1, 8, 0),
                destino_cidade="FLORIANOPOLIS",
                destino_uf="SC",
            ),
            PeriodMarker(
                saida=datetime(2026, 5, 3, 8, 0),
                destino_cidade="CURITIBA",
                destino_uf="PR",
            ),
        ]
        chegada = datetime(2026, 5, 3, 12, 0)
        r1 = calculate_periodized_diarias(
            markers,
            chegada,
            quantidade_servidores=1,
            sede_cidade="CURITIBA",
            sede_uf="PR",
        )
        r3 = calculate_periodized_diarias(
            markers,
            chegada,
            quantidade_servidores=3,
            sede_cidade="CURITIBA",
            sede_uf="PR",
        )
        self.assertEqual(r3["totais"]["total_valor_decimal"], r1["totais"]["total_valor_decimal"] * 3)
        self.assertEqual(r3["totais"]["quantidade_servidores"], 3)

    def test_calculo_avulso_considera_retorno_final_manual(self):
        state = {
            "roteiro_modo": roteiro_logic.ROTEIRO_MODO_PROPRIO,
            "sede_estado_id": None,
            "sede_cidade_id": None,
            "trechos": [
                {
                    "saida_data": "2026-05-01",
                    "saida_hora": "08:00",
                    "destino_cidade_id": None,
                    "destino_estado_id": None,
                    "destino_nome": "FLORIANOPOLIS/SC",
                },
                {
                    "saida_data": "2026-05-04",
                    "saida_hora": "10:00",
                    "destino_cidade_id": None,
                    "destino_estado_id": None,
                    "destino_nome": "CURITIBA/PR",
                },
            ],
            "retorno": {
                "chegada_data": "2026-05-04",
                "chegada_hora": "19:00",
            },
        }
        resultado = roteiro_logic._calculate_avulso_diarias_from_state(state)
        self.assertIn("1 x 30%", resultado["totais"]["total_diarias"])
        self.assertGreaterEqual(resultado["totais"]["total_valor_decimal"], Decimal("0.01"))
