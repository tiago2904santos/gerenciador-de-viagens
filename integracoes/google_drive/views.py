import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.errors import capture
from core.tenancy import filter_queryset_by_area
from integracoes.google_drive.models import (
    DriveCredenciais,
    DriveReorganizacaoJob,
)

logger = logging.getLogger(__name__)
from integracoes.google_drive.services import (
    _SCOPES,
    _reset_client,
    client_config_dict,
    esta_autorizado,
    get_credenciais,
    get_client,
    get_pasta_raiz_id,
)


def _usuario_atual(request):
    user = getattr(request, "user", None)
    return user if user is not None and user.is_authenticated else None


def _credenciais_queryset(usuario):
    if usuario is None:
        return DriveCredenciais.objects.filter(usuario__isnull=True)
    return DriveCredenciais.objects.filter(usuario=usuario)


def _jobs_queryset(usuario, area):
    return DriveReorganizacaoJob.objects.filter(usuario=usuario, area=area)


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------

def _oauth_redirect_uri(request):
    """Monta o redirect_uri a partir do host real da requisição.

    Evita o mismatch de cookie de sessão que ocorre quando `GOOGLE_REDIRECT_URI`
    fixa um host (ex.: localhost:8000) diferente do host usado para acessar a
    aplicação (ex.: domínio de túnel/produção): o Google redireciona para o
    host configurado, que não recebe o cookie de sessão gravado no host de
    origem, e a troca do código falha com "Missing code verifier".
    """
    from django.urls import reverse

    return request.build_absolute_uri(reverse("google_drive:oauth_callback"))


@login_required
def oauth_iniciar(request):
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        client_config_dict(),
        scopes=_SCOPES,
        redirect_uri=_oauth_redirect_uri(request),
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    request.session["gdrive_oauth_state"] = state
    request.session["gdrive_code_verifier"] = getattr(flow, "code_verifier", None)
    usuario = _usuario_atual(request)
    request.session["gdrive_oauth_usuario_id"] = usuario.pk if usuario else None
    return redirect(auth_url)


def oauth_callback(request):
    """Endpoint público — o Google redireciona aqui após autorização."""
    from datetime import timezone as dt_tz

    from google_auth_oauthlib.flow import Flow

    state = request.session.get("gdrive_oauth_state")

    if "error" in request.GET:
        messages.error(request, f"Autorização recusada: {request.GET['error']}")
        return redirect("core:perfil")

    try:
        flow = Flow.from_client_config(
            client_config_dict(),
            scopes=_SCOPES,
            redirect_uri=_oauth_redirect_uri(request),
            state=state,
        )
        code_verifier = request.session.get("gdrive_code_verifier")
        if code_verifier:
            flow.code_verifier = code_verifier
        flow.fetch_token(authorization_response=request.build_absolute_uri())
        creds = flow.credentials

        usuario = _usuario_atual(request)
        _credenciais_queryset(usuario).delete()
        expiry = creds.expiry
        if expiry and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=dt_tz.utc)

        DriveCredenciais.objects.create(
            usuario=usuario,
            access_token=creds.token,
            refresh_token=creds.refresh_token or "",
            token_expiry=expiry,
            scope=" ".join(creds.scopes or []),
        )
        _reset_client()
        messages.success(request, "Conta Google conectada com sucesso!")
    except Exception as exc:
        capture(exc, "drive.views.oauth_callback")  # pragma: no cover
        messages.error(request, f"Erro ao completar autorização: {exc}")

    return redirect("core:perfil")


@login_required
@require_POST
def oauth_revogar(request):
    _credenciais_queryset(_usuario_atual(request)).delete()
    _reset_client()
    messages.success(request, "Conta Google desconectada.")
    return redirect("core:perfil")


# ---------------------------------------------------------------------------
# API de pastas (AJAX)
# ---------------------------------------------------------------------------

@login_required
def api_listar_pastas(request):
    pai_id = request.GET.get("pai_id") or None
    try:
        client = get_client(_usuario_atual(request))
        pastas = client.listar_pastas(pai_id=pai_id)
        return JsonResponse({"pastas": pastas})
    except Exception as exc:
        capture(exc, "drive.views.api_listar_pastas")  # pragma: no cover
        return JsonResponse({"erro": str(exc)}, status=500)


@login_required
def api_listar_drives_compartilhados(request):
    try:
        client = get_client(_usuario_atual(request))
        drives = client.listar_drives_compartilhados()
        return JsonResponse({"pastas": drives})
    except Exception as exc:
        capture(exc, "drive.views.api_listar_drives_compartilhados")  # pragma: no cover
        return JsonResponse({"erro": str(exc)}, status=500)


@login_required
def api_listar_compartilhados_comigo(request):
    try:
        client = get_client(_usuario_atual(request))
        pastas = client.listar_compartilhados_comigo()
        return JsonResponse({"pastas": pastas})
    except Exception as exc:
        capture(exc, "drive.views.api_listar_compartilhados_comigo")  # pragma: no cover
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
        client = get_client(_usuario_atual(request))
        pasta = client.criar_pasta(nome, pai_id=pai_id)
        return JsonResponse({"pasta": pasta})
    except Exception as exc:
        capture(exc, "drive.views.api_criar_pasta")  # pragma: no cover
        return JsonResponse({"erro": str(exc)}, status=500)


@login_required
@require_POST
def salvar_pasta_raiz(request):
    pasta_id = (request.POST.get("pasta_raiz_id") or "").strip()
    pasta_nome = (request.POST.get("pasta_raiz_nome") or "").strip()

    if not pasta_id:
        messages.error(request, "Nenhuma pasta selecionada.")
        return redirect("core:perfil")

    usuario = _usuario_atual(request)
    creds = get_credenciais(usuario)
    if not creds:
        messages.error(request, "Conta Google não conectada.")
        return redirect("core:perfil")

    if not pasta_nome:
        try:
            pasta_nome = get_client(usuario).nome_pasta(pasta_id)
        except Exception as exc:
            capture(exc, "drive.views.salvar_pasta_raiz")  # pragma: no cover
            pasta_nome = pasta_id

    creds.pasta_raiz_id = pasta_id
    creds.pasta_raiz_nome = pasta_nome
    creds.save(update_fields=["pasta_raiz_id", "pasta_raiz_nome", "atualizado_em"])
    _reset_client()
    messages.success(request, f"Pasta \"{pasta_nome}\" definida como diretório de destino.")
    return redirect("core:perfil")


# ---------------------------------------------------------------------------
# Organização em massa
# ---------------------------------------------------------------------------

def _pode_reorganizar(usuario=None) -> bool:
    cfg = getattr(settings, "GOOGLE_DRIVE", {})
    modo = cfg.get("MODO", "mock").lower()
    return bool(get_pasta_raiz_id(usuario)) and (esta_autorizado(usuario) or modo == "mock")


def _executar_reorganizacao(job_id: int, usuario, area, *, encerrar_conexao: bool = True) -> None:
    """Roda a reorganização e atualiza o job. Pensado para rodar numa thread.

    ``encerrar_conexao=False`` quando a execução é inline no thread do request:
    a conexão é de quem chamou, e fechá-la derruba a transação em andamento.
    """
    from django.db import connection

    from integracoes.google_drive import organizer

    def progress(processados, total):
        DriveReorganizacaoJob.objects.filter(pk=job_id).update(
            eventos_processados=processados, total_eventos=total
        )

    try:
        resumo = organizer.reorganizar_tudo(progress=progress, usuario=usuario, area=area)
        DriveReorganizacaoJob.objects.filter(pk=job_id).update(
            status=DriveReorganizacaoJob.STATUS_CONCLUIDA,
            total_eventos=resumo["eventos"],
            eventos_processados=resumo["eventos"],
            avulsos=resumo["avulsos"],
            erros=resumo["erros"],
            finalizado_em=timezone.now(),
        )
    except Exception as exc:  # noqa: BLE001
        capture(exc, "drive.views._executar_reorganizacao")  # pragma: no cover
        logger.error("[Drive] reorganização (job %s) falhou: %s", job_id, exc, exc_info=True)
        DriveReorganizacaoJob.objects.filter(pk=job_id).update(
            status=DriveReorganizacaoJob.STATUS_ERRO,
            mensagem=str(exc),
            finalizado_em=timezone.now(),
        )
    finally:
        # Threads abrem a própria conexão; fechá-la evita vazamento.
        if encerrar_conexao:
            connection.close()


@login_required
@require_POST
def reorganizar_tudo(request):
    usuario = _usuario_atual(request)
    area = getattr(request, "area", None)
    if not _pode_reorganizar(usuario):
        messages.error(
            request,
            "Conecte a conta Google e defina a pasta de destino antes de reorganizar.",
        )
        return redirect("core:perfil")

    if _jobs_queryset(usuario, area).filter(status=DriveReorganizacaoJob.STATUS_EM_ANDAMENTO).exists():
        messages.info(request, "Já existe uma reorganização em andamento. Aguarde concluir.")
        return redirect("core:perfil")

    job = DriveReorganizacaoJob.objects.create(
        usuario=usuario,
        area=area,
        status=DriveReorganizacaoJob.STATUS_EM_ANDAMENTO,
    )

    # Em testes (ou se configurado), roda de forma síncrona para ser determinístico.
    sincrono = getattr(settings, "GOOGLE_DRIVE", {}).get("REORG_SINCRONO", False)
    if sincrono:
        _executar_reorganizacao(job.pk, usuario, area, encerrar_conexao=False)
    else:
        from .tasks import reorganizar_drive

        try:
            reorganizar_drive.delay(job.pk, usuario.pk, getattr(area, "pk", None))
        except Exception as exc:
            capture(exc, "drive.views.reorganizar_tudo")  # pragma: no cover
            job.status = DriveReorganizacaoJob.STATUS_ERRO
            job.mensagem = "Não foi possível enviar a tarefa ao processador assíncrono."
            job.finalizado_em = timezone.now()
            job.save(update_fields=["status", "mensagem", "finalizado_em"])
            messages.error(request, job.mensagem)
            return redirect("core:perfil")

    messages.success(
        request,
        "Reorganização iniciada em segundo plano. O andamento aparece neste card — "
        "pode sair desta página; a tarefa continua rodando.",
    )
    return redirect("core:perfil")


def _job_para_json(job: DriveReorganizacaoJob | None) -> dict:
    if job is None:
        return {"existe": False}
    return {
        "existe": True,
        "status": job.status,
        "status_display": job.get_status_display(),
        "total_eventos": job.total_eventos,
        "eventos_processados": job.eventos_processados,
        "avulsos": job.avulsos,
        "erros": job.erros,
        "mensagem": job.mensagem,
        "em_andamento": job.status == DriveReorganizacaoJob.STATUS_EM_ANDAMENTO,
        "iniciado_em": job.iniciado_em.isoformat(),
        "finalizado_em": job.finalizado_em.isoformat() if job.finalizado_em else None,
    }


@login_required
def status_reorganizacao(request):
    """JSON do job de reorganização mais recente (para polling na página)."""
    job = _jobs_queryset(_usuario_atual(request), getattr(request, "area", None)).order_by("-iniciado_em").first()
    return JsonResponse(_job_para_json(job))


@login_required
def previa_reorganizacao(request):
    """Lista os caminhos planejados (dry-run) sem tocar no Drive.

    Cada evento/ofício é planejado isoladamente: um erro num único item (ex.:
    dados incompletos) só pula aquele item — não derruba a prévia inteira,
    como acontecia antes com o try/except único ao redor de todo o loop.
    """
    from eventos.models import Evento
    from oficios.models import Oficio
    from integracoes.google_drive import organizer

    limite = 500
    linhas: list[str] = []
    truncado = False
    itens_com_erro = 0
    area = getattr(request, "area", None)

    for evento in filter_queryset_by_area(Evento.objects, area=area).iterator():
        try:
            linhas.extend(organizer.planejar_evento(evento))
        except Exception as exc:
            capture(exc, "drive.views.previa_reorganizacao")  # pragma: no cover
            itens_com_erro += 1
            logger.warning("[Drive] falha ao planejar prévia do evento %s", evento.pk, exc_info=True)
            continue
        if len(linhas) >= limite:
            truncado = True
            break
    if not truncado:
        for oficio in filter_queryset_by_area(Oficio.objects, area=area).filter(evento__isnull=True).iterator():
            try:
                linhas.extend(organizer.planejar_oficio(oficio))
            except Exception as exc:
                capture(exc, "drive.views.previa_reorganizacao")  # pragma: no cover
                itens_com_erro += 1
                logger.warning("[Drive] falha ao planejar prévia do ofício %s", oficio.pk, exc_info=True)
                continue
            if len(linhas) >= limite:
                truncado = True
                break

    return JsonResponse(
        {
            "linhas": linhas[:limite],
            "truncado": truncado,
            "total": len(linhas),
            "itens_com_erro": itens_com_erro,
        }
    )


# ---------------------------------------------------------------------------
# Pendências (retry manual)
# ---------------------------------------------------------------------------

_TASK_POR_MODELO = None  # populado sob demanda (evita import de tasks/Celery no boot)


def _task_por_modelo() -> dict:
    global _TASK_POR_MODELO
    if _TASK_POR_MODELO is None:
        from integracoes.google_drive import tasks

        _TASK_POR_MODELO = {
            "documentoartefato": tasks.processar_artefato,
            "prestacaocontas": tasks.processar_prestacao,
            "eventoanexo": tasks.processar_evento_anexo,
            "eventodocumentosolicitacao": tasks.processar_solicitacao_evento,
        }
    return _TASK_POR_MODELO


def _reprocessar_pendencias_em_thread(usuario, area, *, encerrar_conexao: bool = True) -> None:
    """Roda o reenvio de pendências fora do request (ver ``reprocessar_pendencias``).

    ``encerrar_conexao=False`` na execução inline, pelo mesmo motivo descrito
    em ``_executar_reorganizacao``.
    """
    from django.db import connection

    from integracoes.google_drive import status

    try:
        mapa = _task_por_modelo()
        for pendencia in status.listar_pendencias(limite=500, usuario=usuario, area=area):
            task = mapa.get(pendencia.content_type.model)
            if task is None:
                continue
            try:
                task.delay(pendencia.object_id, usuario_id=getattr(usuario, "pk", None))
            except Exception as exc:
                capture(exc, "drive.views._reprocessar_pendencias_em_thread")  # pragma: no cover
                logger.warning("[Drive] falha ao reagendar pendência %s: %s", pendencia.pk, exc)
    finally:
        if encerrar_conexao:
            connection.close()


@login_required
@require_POST
def reprocessar_pendencias(request):
    """Reagenda (via Celery) o reenvio de tudo que está marcado como pendência.

    Roda em segundo plano (thread) em vez de bloquear o request: ``task.delay()``
    depende de conseguir falar com o broker (Redis) e, se o worker Celery não
    estiver configurado ou a rede estiver instável (ou ``CELERY_TASK_ALWAYS_EAGER``
    estiver ligado, o que roda cada reenvio na hora, sequencialmente, dentro do
    próprio ``.delay()``), o botão "Tentar novamente agora" ficava com a página
    carregando até todas as pendências (até 500) serem tentadas uma a uma.
    """
    # Em testes (mesma flag usada por reorganizar_tudo), roda de forma síncrona
    # para ser determinístico.
    usuario = _usuario_atual(request)
    area = getattr(request, "area", None)
    sincrono = getattr(settings, "GOOGLE_DRIVE", {}).get("REORG_SINCRONO", False)
    if sincrono:
        _reprocessar_pendencias_em_thread(usuario, area, encerrar_conexao=False)
    else:
        from .tasks import reprocessar_pendencias

        try:
            reprocessar_pendencias.delay(usuario.pk, getattr(area, "pk", None))
        except Exception as exc:
            capture(exc, "drive.views.reprocessar_pendencias")  # pragma: no cover
            logger.exception("[Drive] falha ao agendar reprocessamento de pendências")
            messages.error(request, "Não foi possível iniciar o reenvio agora.")
            return redirect("core:perfil")
    messages.success(
        request,
        "Reenvio das pendências iniciado em segundo plano. "
        "Atualize a página em instantes para ver a lista diminuir.",
    )
    return redirect("core:perfil")
