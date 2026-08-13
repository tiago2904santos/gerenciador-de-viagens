from roteiros.services.editor_parser import parse_int


def build_roteiro_bate_volta_diario_state(data=None):
    payload = data or {}
    return {
        "ativo": bool(payload.get("ativo")),
        "data_inicio": payload.get("data_inicio") or "",
        "data_fim": payload.get("data_fim") or "",
        "ida_saida_hora": payload.get("ida_saida_hora") or "",
        "ida_tempo_min": payload.get("ida_tempo_min") or "",
        "volta_saida_hora": payload.get("volta_saida_hora") or "",
        "volta_tempo_min": payload.get("volta_tempo_min") or "",
    }


def _roteiro_values_equal(a, b):
    return str(a or "").strip() == str(b or "").strip()


def _roteiro_minutes_equal(a, b):
    parsed_a = parse_int(a)
    parsed_b = parse_int(b)
    if parsed_a is None or parsed_b is None:
        return True
    return parsed_a == parsed_b


def roteiro_trecho_duplica_retorno(trecho, retorno, sede_estado_id=None, sede_cidade_id=None):
    if not trecho or not retorno:
        return False
    if sede_estado_id and parse_int(trecho.get("destino_estado_id")) != parse_int(sede_estado_id):
        return False
    if sede_cidade_id and parse_int(trecho.get("destino_cidade_id")) != parse_int(sede_cidade_id):
        return False
    checks = (
        ("saida_data", "saida_data"),
        ("saida_hora", "saida_hora"),
        ("chegada_data", "chegada_data"),
        ("chegada_hora", "chegada_hora"),
    )
    if any(not _roteiro_values_equal(trecho.get(a), retorno.get(b)) for a, b in checks):
        return False
    if not _roteiro_minutes_equal(
        trecho.get("tempo_cru_estimado_min"),
        retorno.get("tempo_cru_estimado_min"),
    ):
        return False
    if not _roteiro_minutes_equal(
        trecho.get("tempo_adicional_min"),
        retorno.get("tempo_adicional_min"),
    ):
        return False
    if not _roteiro_minutes_equal(
        trecho.get("duracao_estimada_min"),
        retorno.get("duracao_estimada_min"),
    ):
        return False
    retorno_saida = str(retorno.get("saida_cidade") or retorno.get("origem_nome") or "").strip()
    retorno_chegada = str(retorno.get("chegada_cidade") or retorno.get("destino_nome") or "").strip()
    if retorno_saida and not _roteiro_values_equal(trecho.get("origem_nome"), retorno_saida):
        return False
    if retorno_chegada and not _roteiro_values_equal(trecho.get("destino_nome"), retorno_chegada):
        return False
    return True


def dedupe_roteiro_loop_retorno_final(state):
    """Remove do payload de ida o deslocamento já representado no bloco Retorno."""
    bate_volta_diario = build_roteiro_bate_volta_diario_state((state or {}).get("bate_volta_diario"))
    trechos = (state or {}).get("trechos") or []
    if not bate_volta_diario["ativo"] or not trechos:
        return state
    retorno = (state or {}).get("retorno") or {}
    if roteiro_trecho_duplica_retorno(
        trechos[-1],
        retorno,
        sede_estado_id=(state or {}).get("sede_estado_id"),
        sede_cidade_id=(state or {}).get("sede_cidade_id"),
    ):
        state["trechos"] = trechos[:-1]
    return state
