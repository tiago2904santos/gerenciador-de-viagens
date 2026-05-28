# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List


def _duration_human(total_minutes: int) -> str:
    h, m = divmod(max(0, int(total_minutes or 0)), 60)
    if h and m:
        return f"{h}h{m}min"
    if h:
        return f"{h}h"
    return f"{m}min"


def summarize_route_leg_metrics(
    legs: List[dict],
    *,
    distance_km_total: float | None,
    duration_minutes_total: int | None,
    round_trip: bool | None = None,
) -> Dict[str, Any]:
    """
    Ida e volta: totais informados; ida = metade da distância e do tempo.
    Somente ida: totais vão para os campos de ida (sem metade).
    """
    has_return_leg = any(leg.get("kind") == "retorno" for leg in (legs or []))
    has_round_trip = has_return_leg if round_trip is None else bool(round_trip)

    out: Dict[str, Any] = {"has_round_trip": has_round_trip}

    if distance_km_total is not None:
        total_dist = float(distance_km_total)
        if has_round_trip:
            out["distance_km_round_trip"] = total_dist
            out["distance_km_ida"] = round(total_dist / 2, 2)
        else:
            out["distance_km_ida"] = round(total_dist, 2)

    if duration_minutes_total is not None:
        total_min = int(duration_minutes_total)
        if has_round_trip:
            ida_min = total_min // 2
            out["duration_minutes_round_trip"] = total_min
            out["duration_human_round_trip"] = _duration_human(total_min)
            out["duration_minutes_ida"] = ida_min
            out["duration_human_ida"] = _duration_human(ida_min)
        else:
            out["duration_minutes_ida"] = total_min
            out["duration_human_ida"] = _duration_human(total_min)

    return out
