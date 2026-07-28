"""Política de navegação compartilhada pelas views de ofícios."""

from urllib.parse import urlencode

from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


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
    return f"{reverse(url_name)}?{urlencode({'next': next_url})}"


def safe_next_url(request, fallback_url):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback_url
