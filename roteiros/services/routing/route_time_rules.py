# -*- coding: utf-8 -*-
"""
Regras de tempo do roteiro.

Três camadas, nesta ordem:

1. `estimate_travel_minutes` — ETA técnico calibrado. É o que deve bater com o
   Google Maps.
2. `round_trip_minutes_to_15` — arredondamento operacional em blocos de 15 min.
3. `calculate_additional_time_minutes` — folga operacional (paradas, abastecimento,
   refeição) somada por cima do tempo de viagem.

Por que existe a camada 1
-------------------------
O OpenRouteService acerta a *distância* (erro mediano de 0,5% contra o Google em
32 rotas reais do PR), mas calcula o *tempo* em fluxo livre: cruza a 84-87 km/h
onde o trânsito real do Paraná faz 62-74 km/h. O viés não é constante — some no
urbano curto e chega a -75 min em Curitiba→Cascavel —, então não dá para corrigir
com um fator único.

A calibração de 2026-08-24 (32 pares medidos contra o Google Maps, validação
leave-one-out) reconstrói o tempo a partir da distância, que é o dado confiável, e
usa só um resíduo do tempo da ORS como sinal de terreno — o suficiente para
distinguir serra de planalto sem reimportar o viés dela.

    erro médio   22,0 min  ->   6,4 min
    pior caso    74   min  ->  17   min
    dentro de 15 min   47% ->  97%

Recalibrar: `scripts/calibrar_rotas.py` (mede a ORS e refaz o ajuste).
"""
from __future__ import annotations

# --- Calibração 2026-08-24 (n=32, rotas do PR contra o Google Maps) ---
# Velocidade de cruzeiro efetiva e distância-fantasma que representa o custo fixo
# de sair e entrar em cidade (~10 min em `VELOCIDADE_CRUZEIRO_KMH`).
VELOCIDADE_CRUZEIRO_KMH = 74.0
OVERHEAD_ENTRADA_SAIDA_KM = 12.0

# Curva da própria ORS na mesma amostra. Serve de referência: quando a ORS estima
# mais lento que esta curva, a rota tem terreno/traçado ruim.
ORS_VELOCIDADE_REF_KMH = 87.0
ORS_OVERHEAD_REF_KM = 20.0

# Quanto do desvio de terreno da ORS entra no resultado. Ajustado por
# leave-one-out: 0 (ignorar a ORS) dá 8,2 min de erro médio, 0,5 dá 12,4; 0,15 é o
# ponto ótimo. Peso alto reimporta o viés de fluxo livre da ORS.
PESO_TERRENO_ORS = 0.15

# Folga operacional: fração do tempo de viagem, com piso e limiar de dispensa.
FRACAO_TEMPO_ADICIONAL = 1.0 / 6.0
VIAGEM_MINIMA_PARA_ADICIONAL_MIN = 30
TEMPO_ADICIONAL_MINIMO_MIN = 15


def estimate_travel_minutes(
    distance_km: float | int | None,
    provider_minutes: float | int | None = None,
) -> float:
    """
    ETA calibrado em minutos, **sem arredondar**.

    `distance_km` é a distância rodoviária (a da ORS serve). `provider_minutes` é o
    tempo cru da ORS, usado só como sinal de terreno; quando ausente ou inválido, a
    estimativa cai na curva pura de distância — que sozinha já entrega 8,2 min de
    erro médio.
    """
    try:
        km = float(distance_km or 0.0)
    except (TypeError, ValueError):
        km = 0.0
    if km <= 0:
        return 0.0

    base_min = (km + OVERHEAD_ENTRADA_SAIDA_KM) / VELOCIDADE_CRUZEIRO_KMH * 60.0

    try:
        ors_min = float(provider_minutes or 0.0)
    except (TypeError, ValueError):
        ors_min = 0.0
    if ors_min <= 0:
        return base_min

    referencia_min = (km + ORS_OVERHEAD_REF_KM) / ORS_VELOCIDADE_REF_KMH * 60.0
    if referencia_min <= 0:
        return base_min

    # `razao` > 1 => a ORS achou esta rota mais lenta que o típico para a distância
    # (serra, travessia urbana). Entra elevada a PESO_TERRENO_ORS para mover o
    # resultado na direção certa sem arrastar o viés de fluxo livre junto.
    razao = ors_min / referencia_min
    return base_min * (razao ** PESO_TERRENO_ORS)


def round_trip_minutes_to_15(minutes: int | float | None) -> int:
    """
    Arredonda em blocos de 15 com tolerância operacional:
    - resto <= 5: arredonda para baixo (mantém o bloco atual)
    - resto > 5: arredonda para cima (próximo bloco de 15)

    Exemplos:
    65 -> 60
    66 -> 75
    76 -> 75
    """
    try:
        m = int(round(float(minutes or 0)))
    except (TypeError, ValueError):
        m = 0
    if m <= 0:
        return 0
    base = (m // 15) * 15
    resto = m - base
    if resto == 0:
        return m
    if resto <= 5:
        return base
    return base + 15


def calculate_additional_time_minutes(rounded_travel_minutes: int | float | None) -> int:
    """
    Folga operacional, proporcional e contínua: ~1/6 do tempo de viagem, com piso
    de 15 min a partir de 30 min de viagem, arredondada no mesmo bloco de 15.

    A regra anterior era uma tabela em degraus (61 min de viagem valiam 30 de
    folga, 60 min valiam 15) — um minuto a mais dobrava o buffer, e o degrau caía
    em cima do arredondamento, o que produzia ida 75 / volta 90 na mesma rota.
    A forma proporcional preserva os patamares das pontas (180 -> 30, 540 -> 90) e
    elimina o salto.
    """
    try:
        m = int(round(float(rounded_travel_minutes or 0)))
    except (TypeError, ValueError):
        m = 0

    if m < VIAGEM_MINIMA_PARA_ADICIONAL_MIN:
        return 0
    return max(
        TEMPO_ADICIONAL_MINIMO_MIN,
        round_trip_minutes_to_15(m * FRACAO_TEMPO_ADICIONAL),
    )
