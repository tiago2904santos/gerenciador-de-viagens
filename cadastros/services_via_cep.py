import requests


class ViaCEPServiceError(Exception):
    pass


class ViaCEPNotFoundError(Exception):
    pass


def consultar_cep(cep_limpo):
    try:
        response = requests.get(f"https://viacep.com.br/ws/{cep_limpo}/json/", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ViaCEPServiceError from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise ViaCEPServiceError from exc

    if data.get("erro"):
        raise ViaCEPNotFoundError

    uf_sigla = (data.get("uf") or "").strip().upper()

    return {
        "cep": data.get("cep") or f"{cep_limpo[:5]}-{cep_limpo[5:]}",
        "logradouro": data.get("logradouro") or "",
        "bairro": data.get("bairro") or "",
        "cidade": data.get("localidade") or "",
        "uf": uf_sigla,
        "estado": _nome_estado_por_sigla(uf_sigla) or (data.get("estado") or ""),
    }


def _nome_estado_por_sigla(sigla):
    """Retorna o nome do estado (ex.: PARANÁ) a partir da sigla (ex.: PR)."""
    sigla = (sigla or "").strip().upper()
    if not sigla:
        return ""
    from .models import Estado

    estado = Estado.objects.filter(sigla=sigla).only("nome").first()
    return estado.nome if estado else ""
