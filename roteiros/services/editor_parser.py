import re
from datetime import datetime
from decimal import Decimal, InvalidOperation


def parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_roteiro_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_roteiro_time(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:5], "%H:%M").time().replace(second=0, microsecond=0)
    except ValueError:
        return None


def roteiro_date_input(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value
    return value.strftime("%Y-%m-%d")


def roteiro_time_input(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value[:5]
    return value.strftime("%H:%M")


def parse_destinos_post(post):
    prefix_estado = "destino_estado_"
    prefix_cidade = "destino_cidade_"
    indices = set()
    for key in post:
        if key.startswith(prefix_estado):
            try:
                idx = int(key[len(prefix_estado) :])
                indices.add(idx)
            except ValueError:
                continue
    destinos = []
    for idx in sorted(indices):
        estado_id = post.get(f"{prefix_estado}{idx}")
        cidade_id = post.get(f"{prefix_cidade}{idx}")
        if estado_id and cidade_id:
            try:
                destinos.append((int(estado_id), int(cidade_id)))
            except (TypeError, ValueError):
                continue
    return destinos


def extract_roteiro_posted_trechos(post):
    pattern = re.compile(r"^trecho_(\d+)_(.+)$")
    indexed = {}
    for key in post:
        match = pattern.match(key)
        if not match:
            continue
        idx = int(match.group(1))
        field_name = match.group(2)
        indexed.setdefault(idx, {})[field_name] = post.get(key)
    return [indexed[idx] for idx in sorted(indexed)]


def parse_roteiro_decimal(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if "," in raw and "." in raw:
            if raw.rfind(",") > raw.rfind("."):
                raw = raw.replace(".", "").replace(",", ".")
            else:
                raw = raw.replace(",", "")
        else:
            raw = raw.replace(",", ".")
        return Decimal(raw)
    except (InvalidOperation, TypeError, ValueError):
        return None


def roteiro_decimal_input(value):
    decimal_value = parse_roteiro_decimal(value)
    if decimal_value is None:
        return ""
    return f"{decimal_value.quantize(Decimal('0.01')):.2f}"
