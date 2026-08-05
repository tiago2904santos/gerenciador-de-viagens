"""Limite de tentativas de login, compartilhado pelas duas portas de entrada (QA-01).

A lógica nasceu dentro de `core.views.LoginView` e valia só para `core:login`. O
Django Admin tem view de login própria, servida por `AdminSite`, que não passa
por lá — e `/admin/` concede superusuário. Medido antes de mexer: 10 POSTs de
senha errada em `/admin/login/` devolviam 200 dez vezes, enquanto `/` bloqueava
no sexto com 429.

Este módulo é o dono único da regra. `core.views.LoginView` e o wrapper do admin
consomem as mesmas funções, para que o limite não possa divergir entre as portas.

Depende de cache compartilhado entre processos: com `LocMemCache` cada worker tem
o próprio balde. Por isso `config/settings/prod.py` exige `REDIS_URL` (QA-02).
"""

from __future__ import annotations

import hashlib
import ipaddress

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest

LIMITE = 5
JANELA_SEGUNDOS = 15 * 60
MENSAGEM = "Muitas tentativas de acesso. Aguarde 15 minutos e tente novamente."


def _ip_do_cliente(request: HttpRequest) -> str:
    """IP real, honrando `X-Real-IP` apenas de proxy declarado como confiável."""
    remote_ip = request.META.get("REMOTE_ADDR", "")
    confiavel = remote_ip in settings.TRUSTED_PROXY_IPS
    candidato = request.META.get("HTTP_X_REAL_IP", "") if confiavel else remote_ip
    try:
        return str(ipaddress.ip_address(candidato))
    except ValueError:
        return "invalid"


def chave_de_tentativa(request: HttpRequest) -> str:
    """Balde por (IP, usuário): errar a senha de um não tranca a conta do outro."""
    usuario = (request.POST.get("username") or "").strip().casefold()
    digest = hashlib.sha256(f"{_ip_do_cliente(request)}|{usuario}".encode()).hexdigest()
    return f"login-attempt:{digest}"


def excedeu_limite(request: HttpRequest) -> bool:
    return cache.get(chave_de_tentativa(request), 0) >= LIMITE


def registrar_falha(request: HttpRequest) -> None:
    chave = chave_de_tentativa(request)
    try:
        cache.incr(chave)
    except ValueError:
        cache.set(chave, 1, timeout=JANELA_SEGUNDOS)
