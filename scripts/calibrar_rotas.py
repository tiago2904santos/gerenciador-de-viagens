# -*- coding: utf-8 -*-
"""
Recalibra o ETA de viagem (`roteiros.services.routing.route_time_rules`).

O OpenRouteService acerta a distancia e erra o tempo: calcula em fluxo livre. Este
script mede a ORS nos pares de um arquivo de referencia, compara com tempos reais
coletados a mao no Google Maps e reajusta os parametros da curva.

Uso
---
1. Monte o arquivo de referencia (`;` como separador):

       origem;destino;km_google;min_google
       CURITIBA;LONDRINA;383;325

   Os tempos vem do Google Maps em `maps.google.com/maps/dir/?api=1&origin=...`,
   anotando o trajeto mais rapido. Vale a pena coletar em horario comercial e
   cobrir a faixa toda de distancia, nao so as rotas longas.

2. Rode:

       python scripts/calibrar_rotas.py --referencia dados/rotas_referencia.csv

   `--aplicar` reescreve as constantes em `route_time_rules.py`; sem ele o script
   so relata. `--validar` roda leave-one-out em vez de so ajustar, para medir o
   erro esperado fora da amostra.

A calibracao de 2026-08-24 (n=32, PR) levou o erro medio de 22,0 para 6,9 min.
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics as st
import sys
import time
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

from cadastros.models import Cidade  # noqa: E402
from roteiros.services.routing.openrouteservice import (  # noqa: E402
    get_openrouteservice_provider,
)
from roteiros.services.routing.route_time_rules import (  # noqa: E402
    round_trip_minutes_to_15,
)


def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in base if not unicodedata.combining(c)).upper().strip()


def medir_ors(caminho: Path, pausa: float = 1.6) -> list[dict]:
    """Consulta a ORS em cada par do arquivo e devolve a amostra casada."""
    provider = get_openrouteservice_provider()
    if provider is None:
        raise SystemExit("OPENROUTESERVICE_API_KEY ausente: nada a medir.")

    cidades = {_sem_acento(c.nome): c for c in Cidade.objects.all()}
    amostra: list[dict] = []
    with caminho.open(encoding="utf-8") as fh:
        for linha in csv.DictReader(fh, delimiter=";"):
            a = cidades.get(_sem_acento(linha["origem"]))
            b = cidades.get(_sem_acento(linha["destino"]))
            if not a or not b or a.latitude is None or b.latitude is None:
                print(f"  ignorado (sem cidade/coordenada): {linha['origem']} -> {linha['destino']}")
                continue
            pontos = [
                {"id": "a", "lat": float(a.latitude), "lng": float(a.longitude), "label": a.nome},
                {"id": "b", "lat": float(b.latitude), "lng": float(b.longitude), "label": b.nome},
            ]
            try:
                res = provider.calculate_route(pontos, profile="driving-car")
            except Exception as exc:  # provedor fora do ar nao pode abortar a coleta inteira
                print(f"  falhou: {linha['origem']} -> {linha['destino']}: {exc}")
                continue
            time.sleep(pausa)
            amostra.append(
                {
                    "origem": linha["origem"],
                    "destino": linha["destino"],
                    "km_o": float(res["distance_km"]),
                    "min_o": int(res["duration_minutes"]),
                    "min_g": int(linha["min_google"]),
                }
            )
            print(
                f"  {linha['origem']} -> {linha['destino']}: "
                f"ORS {res['duration_minutes']} min, real {linha['min_google']} min"
            )
    return amostra


def _ajustar_referencia_ors(amostra: list[dict]) -> tuple[int, int]:
    """Curva que descreve a propria ORS; serve de base para o sinal de terreno."""
    melhor = None
    for velocidade in range(78, 96):
        for overhead in range(0, 30):
            erro = st.mean(
                abs((r["km_o"] + overhead) / velocidade * 60 - r["min_o"]) for r in amostra
            )
            if melhor is None or erro < melhor[0]:
                melhor = (erro, velocidade, overhead)
    return melhor[1], melhor[2]


def _prever(km: float, min_ors: float, params: dict) -> float:
    base = (km + params["overhead"]) / params["velocidade"] * 60
    referencia = (km + params["overhead_ref"]) / params["velocidade_ref"] * 60
    if min_ors <= 0 or referencia <= 0:
        return base
    return base * ((min_ors / referencia) ** params["peso"])


def ajustar(amostra: list[dict], peso: float) -> dict:
    velocidade_ref, overhead_ref = _ajustar_referencia_ors(amostra)
    melhor = None
    for velocidade in range(64, 92):
        for overhead in range(0, 34):
            p = {
                "velocidade": velocidade,
                "overhead": overhead,
                "velocidade_ref": velocidade_ref,
                "overhead_ref": overhead_ref,
                "peso": peso,
            }
            erro = st.mean(
                abs(round_trip_minutes_to_15(_prever(r["km_o"], r["min_o"], p)) - r["min_g"])
                for r in amostra
            )
            if melhor is None or erro < melhor[0]:
                melhor = (erro, p)
    return melhor[1]


def relatar(amostra: list[dict], params: dict) -> None:
    erros_novo, erros_ors = [], []
    for r in amostra:
        novo = round_trip_minutes_to_15(_prever(r["km_o"], r["min_o"], params))
        erros_novo.append(novo - r["min_g"])
        erros_ors.append(round_trip_minutes_to_15(r["min_o"]) - r["min_g"])
    for nome, erros in (("ORS crua", erros_ors), ("calibrada", erros_novo)):
        absolutos = [abs(e) for e in erros]
        dentro15 = sum(1 for e in absolutos if e <= 15) / len(absolutos) * 100
        dentro30 = sum(1 for e in absolutos if e <= 30) / len(absolutos) * 100
        print(
            f"  {nome:<10} erro medio {st.mean(absolutos):5.1f} | pior {max(absolutos):3.0f} "
            f"| vies {st.mean(erros):+5.1f} | <=15min {dentro15:3.0f}% | <=30min {dentro30:3.0f}%"
        )


def validar(amostra: list[dict], peso: float) -> None:
    """Leave-one-out: reajusta sem o ponto avaliado, para medir erro fora da amostra."""
    erros = []
    for i in range(len(amostra)):
        treino = amostra[:i] + amostra[i + 1 :]
        p = ajustar(treino, peso)
        r = amostra[i]
        erros.append(round_trip_minutes_to_15(_prever(r["km_o"], r["min_o"], p)) - r["min_g"])
    absolutos = [abs(e) for e in erros]
    dentro15 = sum(1 for e in absolutos if e <= 15) / len(absolutos) * 100
    print(
        f"  leave-one-out: erro medio {st.mean(absolutos):.1f} "
        f"| pior {max(absolutos):.0f} | <=15min {dentro15:.0f}%"
    )


def aplicar(params: dict) -> None:
    alvo = RAIZ / "roteiros" / "services" / "routing" / "route_time_rules.py"
    linhas = alvo.read_text(encoding="utf-8").splitlines(keepends=True)
    trocas = {
        "VELOCIDADE_CRUZEIRO_KMH": f"{float(params['velocidade']):.1f}",
        "OVERHEAD_ENTRADA_SAIDA_KM": f"{float(params['overhead']):.1f}",
        "ORS_VELOCIDADE_REF_KMH": f"{float(params['velocidade_ref']):.1f}",
        "ORS_OVERHEAD_REF_KM": f"{float(params['overhead_ref']):.1f}",
        "PESO_TERRENO_ORS": f"{params['peso']}",
    }
    for nome, valor in trocas.items():
        for idx, linha in enumerate(linhas):
            if linha.startswith(f"{nome} = "):
                linhas[idx] = f"{nome} = {valor}\n"
                break
        else:
            raise SystemExit(f"constante {nome} nao encontrada em {alvo}")
    alvo.write_text("".join(linhas), encoding="utf-8")
    print(f"  constantes reescritas em {alvo.relative_to(RAIZ)}")
    print("  rode a suite: python manage.py test roteiros --settings=config.settings.test")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Recalibra o ETA de viagem contra tempos reais do Google Maps."
    )
    ap.add_argument("--referencia", required=True, type=Path, help="CSV com os tempos reais")
    ap.add_argument("--peso", type=float, default=0.15, help="peso do sinal de terreno da ORS")
    ap.add_argument("--aplicar", action="store_true", help="reescreve as constantes")
    ap.add_argument("--validar", action="store_true", help="roda leave-one-out")
    args = ap.parse_args()

    if not args.referencia.exists():
        raise SystemExit(f"arquivo nao encontrado: {args.referencia}")

    print("Medindo a ORS...")
    amostra = medir_ors(args.referencia)
    if len(amostra) < 8:
        raise SystemExit(f"amostra pequena demais ({len(amostra)} pares): colete mais rotas.")

    params = ajustar(amostra, args.peso)
    print(f"\nParametros (n={len(amostra)}):")
    for chave, valor in params.items():
        print(f"  {chave} = {valor}")
    print("\nErro na amostra:")
    relatar(amostra, params)

    if args.validar:
        print("\nFora da amostra:")
        validar(amostra, args.peso)

    if args.aplicar:
        print("\nAplicando:")
        aplicar(params)
    else:
        print("\n(use --aplicar para gravar as constantes)")


if __name__ == "__main__":
    main()
