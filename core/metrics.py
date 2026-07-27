from __future__ import annotations

import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

_PREFIX = "cv3:metrics:"
_METRICS = (
    "http_requests_total",
    "http_errors_total",
    "http_request_duration_ms_sum",
    "document_generations_total",
    "document_generation_duration_ms_sum",
    "document_generation_sla_violations_total",
)


def _increment(name: str, amount: int = 1) -> None:
    key = f"{_PREFIX}{name}"
    try:
        if cache.add(key, amount, timeout=None):
            return
        cache.incr(key, amount)
    except Exception:
        logger.warning("Não foi possível atualizar a métrica %s.", name, exc_info=True)


def record_http_request(*, status_code: int, duration_ms: int) -> None:
    _increment("http_requests_total")
    _increment("http_request_duration_ms_sum", max(0, int(duration_ms)))
    if status_code >= 500:
        _increment("http_errors_total")


def record_document_generation(*, duration_ms: int, sla_ms: int = 1000) -> None:
    duration_ms = max(0, int(duration_ms))
    _increment("document_generations_total")
    _increment("document_generation_duration_ms_sum", duration_ms)
    if duration_ms >= sla_ms:
        _increment("document_generation_sla_violations_total")


def prometheus_text() -> str:
    lines = []
    for name in _METRICS:
        value = int(cache.get(f"{_PREFIX}{name}", 0) or 0)
        lines.extend((f"# TYPE cv3_{name} counter", f"cv3_{name} {value}"))
    return "\n".join(lines) + "\n"
