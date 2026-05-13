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

    return {
        "cep": data.get("cep") or f"{cep_limpo[:5]}-{cep_limpo[5:]}",
        "logradouro": data.get("logradouro") or "",
        "bairro": data.get("bairro") or "",
        "cidade": data.get("localidade") or "",
        "uf": data.get("uf") or "",
    }
