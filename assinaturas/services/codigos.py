from __future__ import annotations

import re
import secrets

CODIGO_RE = re.compile(r"CV-\d{4}-[A-Z0-9]{6}-[A-Z0-9]{4}")


def normalizar_codigo_verificacao(codigo: str) -> str:
    return (codigo or "").strip().upper()


def codigo_tem_formato_valido(codigo: str) -> bool:
    c = normalizar_codigo_verificacao(codigo)
    return bool(CODIGO_RE.fullmatch(c))


def gerar_codigo_verificacao() -> str:
    """Gera código único no formato CV-ANO-XXXXXX-XXXX."""
    from django.utils import timezone

    from assinaturas.models import AssinaturaDigital

    ano = timezone.localdate().year
    while True:
        codigo = f"CV-{ano}-{secrets.token_hex(3).upper()}-{secrets.token_hex(2).upper()}"
        if not codigo_tem_formato_valido(codigo):
            continue
        if not AssinaturaDigital.objects.filter(codigo_verificacao=codigo).exists():
            return codigo
