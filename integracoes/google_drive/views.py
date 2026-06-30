import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from integracoes.google_drive.models import DriveArquivo, DriveCredenciais
from integracoes.google_drive.services import (
    _SCOPES,
    _reset_client,
    client_config_dict,
    esta_autorizado,
    get_client,
    get_pasta_raiz_id,
    is_mock,
)


@login_required
def index(request):
    cfg = getattr(settings, "GOOGLE_DRIVE", {})
    creds = DriveCredenciais.objects.first()
    pasta_raiz_id = get_pasta_raiz_id()

    return render(
        request,
        "integracoes/google_drive/index.html",
        {
            "page_title": "Google Drive",
            "page_description": "Configuração da integração com o Google Drive.",
            "modo": cfg.get("MODO", "mock"),
            "autorizado": esta_autorizado(),
            "creds": creds,
            "pasta_raiz_id": pasta_raiz_id,
            "pasta_raiz_nome": creds.pasta_raiz_nome if creds else "",
            "total_arquivos": DriveArquivo.objects.count(),
            "modo_ativo": cfg.get("MODO", "mock").lower() != "mock",
        },
    )


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------

@login_required
def oauth_iniciar(request):
    from google_auth_oauthlib.flow import Flow

    cfg = getattr(settings, "GOOGLE_DRIVE", {})
    flow = Flow.from_client_config(
        client_config_dict(),
        scopes=_SCOPES,
        redirect_uri=cfg.get("REDIRECT_URI", ""),
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    request.session["gdrive_oauth_state"] = state
    request.session["gdrive_code_verifier"] = getattr(flow, "code_verifier", None)
    return redirect(auth_url)


def oauth_callback(request):
    """Endpoint público — o Google redireciona aqui após autorização."""
    from datetime import timezone as dt_tz

    from google_auth_oauthlib.flow import Flow

    cfg = getattr(settings, "GOOGLE_DRIVE", {})
    state = request.session.get("gdrive_oauth_state")

    if "error" in request.GET:
        messages.error(request, f"Autorização recusada: {request.GET['error']}")
        return redirect("cadastros:configuracao")

    try:
        flow = Flow.from_client_config(
            client_config_dict(),
            scopes=_SCOPES,
            redirect_uri=cfg.get("REDIRECT_URI", ""),
            state=state,
        )
        code_verifier = request.session.get("gdrive_code_verifier")
        if code_verifier:
            flow.code_verifier = code_verifier
        flow.fetch_token(authorization_response=request.build_absolute_uri())
        creds = flow.credentials

        DriveCredenciais.objects.all().delete()
        expiry = creds.expiry
        if expiry and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=dt_tz.utc)

        DriveCredenciais.objects.create(
            access_token=creds.token,
            refresh_token=creds.refresh_token or "",
            token_expiry=expiry,
            scope=" ".join(creds.scopes or []),
        )
        _reset_client()
        messages.success(request, "Conta Google conectada com sucesso!")
    except Exception as exc:
        messages.error(request, f"Erro ao completar autorização: {exc}")

    return redirect("cadastros:configuracao")


@login_required
@require_POST
def oauth_revogar(request):
    DriveCredenciais.objects.all().delete()
    _reset_client()
    messages.success(request, "Conta Google desconectada.")
    return redirect("cadastros:configuracao")


# ---------------------------------------------------------------------------
# API de pastas (AJAX)
# ---------------------------------------------------------------------------

@login_required
def api_listar_pastas(request):
    pai_id = request.GET.get("pai_id") or None
    try:
        client = get_client()
        pastas = client.listar_pastas(pai_id=pai_id)
        return JsonResponse({"pastas": pastas})
    except Exception as exc:
        return JsonResponse({"erro": str(exc)}, status=500)


@login_required
@require_POST
def api_criar_pasta(request):
    try:
        body = json.loads(request.body)
        nome = (body.get("nome") or "").strip()
        pai_id = (body.get("pai_id") or "").strip() or None
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"erro": "JSON inválido"}, status=400)

    if not nome:
        return JsonResponse({"erro": "Nome é obrigatório"}, status=400)

    try:
        client = get_client()
        pasta = client.criar_pasta(nome, pai_id=pai_id)
        return JsonResponse({"pasta": pasta})
    except Exception as exc:
        return JsonResponse({"erro": str(exc)}, status=500)


@login_required
@require_POST
def salvar_pasta_raiz(request):
    pasta_id = (request.POST.get("pasta_raiz_id") or "").strip()
    pasta_nome = (request.POST.get("pasta_raiz_nome") or "").strip()

    if not pasta_id:
        messages.error(request, "Nenhuma pasta selecionada.")
        return redirect("cadastros:configuracao")

    creds = DriveCredenciais.objects.first()
    if not creds:
        messages.error(request, "Conta Google não conectada.")
        return redirect("cadastros:configuracao")

    if not pasta_nome:
        try:
            pasta_nome = get_client().nome_pasta(pasta_id)
        except Exception:
            pasta_nome = pasta_id

    creds.pasta_raiz_id = pasta_id
    creds.pasta_raiz_nome = pasta_nome
    creds.save(update_fields=["pasta_raiz_id", "pasta_raiz_nome", "atualizado_em"])
    _reset_client()
    messages.success(request, f"Pasta \"{pasta_nome}\" definida como diretório de destino.")
    return redirect("cadastros:configuracao")
