"""Política de navegação compartilhada pelas views de ofícios."""

from urllib.parse import urlencode

from django.urls import reverse

from core.retorno import url_de_cadastro
from core.retorno import voltar_para


def evento_etapa_url(evento_id, etapa):
    if evento_id:
        return reverse(
            "eventos:guiado_etapa",
            kwargs={"pk": evento_id, "etapa": etapa},
        )
    return ""


def oficio_back_url(oficio):
    return evento_etapa_url(getattr(oficio, "evento_id", None), 3) or reverse(
        "oficios:index",
    )


def oficio_back_label(oficio):
    return "Dados do evento" if getattr(oficio, "evento_id", None) else "Voltar à lista"


def cadastro_create_url(create_url_name, next_url):
    return f"{reverse(create_url_name)}?{urlencode({'next': next_url})}"


def url_with_next(url_name, next_url):
    """Mantido como fachada: `core.retorno` e o dono da politica (`NOVO-15`)."""
    return url_de_cadastro(url_name, next_url)


def safe_next_url(request, fallback_url):
    """Mantido como fachada: `core.retorno` e o dono da politica (`NOVO-15`)."""
    return voltar_para(request, fallback_url)
