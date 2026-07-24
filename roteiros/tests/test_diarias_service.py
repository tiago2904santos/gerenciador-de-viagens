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
