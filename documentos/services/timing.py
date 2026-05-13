"""
Medição de tempo por etapa da geração documental (logging apenas; sem impacto na UI).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger("documentos.timing")


@contextmanager
def measure_step(label: str, metadata: dict[str, Any] | None = None) -> Iterator[None]:
    """
    Regista duração em milissegundos no logger ``documentos.timing``.

    Nunca propaga falhas de logging para não interferir na geração do documento.
    """
    meta = dict(metadata or {})
    t0 = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        try:
            parts: list[str] = ["[documentos]"]
            for key in sorted(meta.keys()):
                val = meta[key]
                if val is None or val == "":
                    continue
                parts.append(f"{key}={val}")
            parts.append(f"etapa={label}")
            parts.append(f"duration_ms={duration_ms}")
            logger.info(" ".join(parts))
        except Exception:
            pass
