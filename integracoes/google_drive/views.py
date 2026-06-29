from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import settings as cfg
from .services import (
    GoogleDriveError,
    listar_arquivos,
    obter_url_autorizacao,
    revogar_token,
    trocar_codigo_por_token,
    usuario_esta_conectado,
)

_login = login_required(login_url="core:login")


@_login
def index(request):
    conectado = usuario_esta_conectado(request.user)
    arquivos = []

    if conectado:
        try:
            arquivos = listar_arquivos(request.user)
        except GoogleDriveError as e:
            messages.warning(request, str(e))
            conectado = False

    return render(
        request,
        "integracoes/google_drive/index.html",
        {
            "page_title": "Google Drive",
            "conectado": conectado,
            "arquivos": arquivos,
            "drive_configurado": cfg.esta_configurado(),
        },
    )


@_login
def autorizar(request):
    if not cfg.esta_configurado():
        messages.error(
            request,
            "Google Drive não está configurado. Contate o administrador do sistema.",
        )
        return redirect("google_drive:index")

    url, state = obter_url_autorizacao()
    request.session["google_oauth_state"] = state
    return redirect(url)


@_login
def oauth_callback(request):
    error = request.GET.get("error")
    if error:
        messages.error(request, f"Autorização negada pelo Google: {error}")
        return redirect("google_drive:index")

    code = request.GET.get("code")
    if not code:
        messages.error(request, "Código de autorização ausente na resposta do Google.")
        return redirect("google_drive:index")

    try:
        trocar_codigo_por_token(request.user, code)
        messages.success(request, "Conta Google Drive conectada com sucesso!")
    except Exception as e:
        messages.error(request, f"Erro ao conectar o Google Drive: {e}")

    return redirect("google_drive:index")


@_login
@require_POST
def desconectar(request):
    revogar_token(request.user)
    messages.success(request, "Conta Google Drive desconectada.")
    return redirect("google_drive:index")
