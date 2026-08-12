from __future__ import annotations

import logging

from django.conf import settings


logger = logging.getLogger(__name__)


def initialize_error_tracking() -> bool:
    """Inicializa o backend externo somente quando um DSN foi configurado."""

    dsn = getattr(settings, "SENTRY_DSN", "").strip()
    if not dsn:
        return False

    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment=getattr(settings, "SENTRY_ENVIRONMENT", "production"),
            release=getattr(settings, "SENTRY_RELEASE", "") or None,
            send_default_pii=False,
            traces_sample_rate=0.0,
        )
    except Exception:
        logger.exception("Falha ao inicializar rastreamento centralizado de erros")
        return False
    logger.info("Rastreamento centralizado de erros habilitado")
    return True
