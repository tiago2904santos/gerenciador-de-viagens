"""Login do Django Admin com o mesmo limite de tentativas do login da aplicação (QA-01).

`/admin/` concede superusuário e era a porta **sem nenhuma fricção** contra força
bruta: `AdminSite.login` usa a `LoginView` do `django.contrib.auth`, que não passa
por `core.views.LoginView`. Medido antes: 10 POSTs de senha errada em
`/admin/login/` devolviam 200 dez vezes; no login da aplicação o sexto já vinha
429. A única barreira era a política de senha (mínimo 12 caracteres).

Por que um wrapper de URL e não um `AdminSite` próprio: trocar o site exigiria
reregistrar todos os modelos que hoje usam `@admin.register(...)` no site padrão.
O wrapper entra antes de `admin.site.urls` em `config/urls.py`, aplica a regra e
delega o resto para o Django — o formulário, o template e o `next` continuam sendo
os do admin.
"""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.decorators import login_not_required
from django.shortcuts import render

from core import login_throttle


@login_not_required
def admin_login_com_limite(request, extra_context=None):
    if request.method == "POST" and login_throttle.excedeu_limite(request):
        return render(request, "core/login_bloqueado.html", {"mensagem": login_throttle.MENSAGEM}, status=429)

    resposta = admin.site.login(request, extra_context)

    # Uma tentativa que falha volta 200 renderizando o formulário com erro; a que
    # dá certo redireciona e deixa o usuário autenticado. Contar pelo resultado
    # evita depender da estrutura interna da view do admin.
    if request.method == "POST" and not request.user.is_authenticated:
        login_throttle.registrar_falha(request)

    return resposta
