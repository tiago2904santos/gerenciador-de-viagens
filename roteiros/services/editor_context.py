from roteiros.services.diarias import locations_equivalent


def roteiro_local_label(cidade=None, estado=None):
    cidade_nome = ""
    estado_sigla = ""
    if cidade:
        cidade_nome = cidade.nome
        estado_sigla = getattr(getattr(cidade, "estado", None), "sigla", "") or estado_sigla
    if estado and not estado_sigla:
        estado_sigla = estado.sigla
    if cidade_nome and estado_sigla:
        return f"{cidade_nome}/{estado_sigla}"
    return cidade_nome or estado_sigla or ""


def roteiro_get_local_parts(cidade=None, estado=None, nome=""):
    cidade_nome = ""
    estado_sigla = ""
    if cidade:
        cidade_nome = getattr(cidade, "nome", "") or ""
        estado_sigla = getattr(getattr(cidade, "estado", None), "sigla", "") or ""
    if estado and not estado_sigla:
        estado_sigla = getattr(estado, "sigla", "") or ""
    if nome and not cidade_nome:
        raw_nome = str(nome or "").strip()
        if "/" in raw_nome:
            cidade_nome, _, maybe_uf = raw_nome.partition("/")
            if not estado_sigla:
                estado_sigla = maybe_uf.strip().upper()
        else:
            cidade_nome = raw_nome
    return cidade_nome.strip(), estado_sigla.strip().upper()


def roteiro_locations_equivalent(
    *, cidade_a=None, estado_a=None, nome_a="", cidade_b=None, estado_b=None, nome_b=""
):
    cidade_a_nome, estado_a_sigla = roteiro_get_local_parts(
        cidade=cidade_a,
        estado=estado_a,
        nome=nome_a,
    )
    cidade_b_nome, estado_b_sigla = roteiro_get_local_parts(
        cidade=cidade_b,
        estado=estado_b,
        nome=nome_b,
    )
    return locations_equivalent(cidade_a_nome, estado_a_sigla, cidade_b_nome, estado_b_sigla)
