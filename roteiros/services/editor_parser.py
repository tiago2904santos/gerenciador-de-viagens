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
    """Lê os destinos do POST, na ordem das linhas.

    A primeira linha vem SEM sufixo (`destino_estado`) e as demais numeradas
    (`destino_estado_1`, `_2`...). É como o `c-v2.destination_row` nomeia os
    campos, e é o que termos e ordens de serviço já enviam.

    O formato antigo — todas numeradas a partir de `_0` — continua valendo: é o
    que a etapa de roteiro do wizard de ofício ainda manda, e ler só um dos dois
    descartaria um destino inteiro **em silêncio**, que é o pior jeito de
    perder dado de viagem.
    """
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

    def par(estado_key, cidade_key):
        estado_id = post.get(estado_key)
        cidade_id = post.get(cidade_key)
        if not (estado_id and cidade_id):
            return None
        try:
            return (int(estado_id), int(cidade_id))
        except (TypeError, ValueError):
            return None

    destinos = []
    # A linha sem sufixo é sempre a PRIMEIRA da lista, venha ou não numerada.
    primeiro = par("destino_estado", "destino_cidade")
    if primeiro:
        destinos.append(primeiro)
    for idx in sorted(indices):
        atual = par(f"{prefix_estado}{idx}", f"{prefix_cidade}{idx}")
        if atual:
            destinos.append(atual)
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
