import json
import logging
import threading

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from integracoes.google_drive.models import (
    DriveArquivo,
    DriveCredenciais,
    DriveReorganizacaoJob,
)

logger = logging.getLogger(__name__)
from integracoes.google_drive.services import (
    _SCOPES,
    _reset_client,
    client_config_dict,
    escopo_faltante,
    esta_autorizado,
    get_credenciais,
    get_client,
    get_pasta_raiz_id,
    is_mock,
)


def _area_atual(request):
    return getattr(request, "area", None)


def _credenciais_queryset(area):
    if area is None:
        return DriveCredenciais.objects.filter(area__isnull=True)
    return DriveCredenciais.objects.filter(area=area)


@login_required
def index(request):
    from eventos.models import Evento

    from integracoes.google_drive import status

    cfg = getattr(settings, "GOOGLE_DRIVE", {})
    area = _area_atual(request)
    creds = get_credenciais(area)
    pasta_raiz_id = get_pasta_raiz_id(area)
    modo = cfg.get("MODO", "mock").lower()
    autorizado = esta_autorizado(area)

    return render(
        request,
        "integracoes/google_drive/index.html",
        {
            "page_title": "Google Drive",
            "page_description": "Configuração da integração com o Google Drive.",
            "modo": modo,
            "autorizado": autorizado,
            "escopo_faltante": escopo_faltante(area),
            "creds": creds,
            "pasta_raiz_id": pasta_raiz_id,
            "pasta_raiz_nome": creds.pasta_raiz_nome if creds else "",
            "total_arquivos": DriveArquivo.objects.count(),
            "modo_ativo": modo != "mock",
            "pode_reorganizar": bool(pasta_raiz_id) and (autorizado or modo == "mock"),
            "total_eventos": Evento.objects.count(),
            "job_reorg": DriveReorganizacaoJob.objects.order_by("-iniciado_em").first(),
            "total_pendencias": status.contagem_pendencias(),
            "pendencias": status.listar_pendencias(limite=20),
        },
    )


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
    area = _area_atual(request)
    request.session["gdrive_oauth_area_id"] = area.pk if area else None
    return redirect(auth_url)


def oauth_callback(request):
    """Endpoint público — o Google redireciona aqui após autorização."""
    from datetime import timezone as dt_tz

    from google_auth_oauthlib.flow import Flow

    state = request.session.get("gdrive_oauth_state")

    if "error" in request.GET:
        messages.error(request, f"Autorização recusada: {request.GET['error']}")
        return redirect("google_drive:index")

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

        area = _area_atual(request)
        _credenciais_queryset(area).delete()
        expiry = creds.expiry
        if expiry and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=dt_tz.utc)

        DriveCredenciais.objects.create(
            area=area,
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
    _credenciais_queryset(_area_atual(request)).delete()
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
        client = get_client(_area_atual(request))
        pastas = client.listar_pastas(pai_id=pai_id)
        return JsonResponse({"pastas": pastas})
    except Exception as exc:
        return JsonResponse({"erro": str(exc)}, status=500)


@login_required
def api_listar_drives_compartilhados(request):
    try:
        client = get_client(_area_atual(request))
        drives = client.listar_drives_compartilhados()
        return JsonResponse({"pastas": drives})
    except Exception as exc:
        return JsonResponse({"erro": str(exc)}, status=500)


@login_required
def api_listar_compartilhados_comigo(request):
    try:
        client = get_client(_area_atual(request))
        pastas = client.listar_compartilhados_comigo()
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
        client = get_client(_area_atual(request))
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
        return redirect("google_drive:index")

    area = _area_atual(request)
    creds = get_credenciais(area)
    if not creds:
        messages.error(request, "Conta Google não conectada.")
        return redirect("cadastros:configuracao")

    if not pasta_nome:
        try:
            pasta_nome = get_client(area).nome_pasta(pasta_id)
        except Exception:
            pasta_nome = pasta_id

    creds.pasta_raiz_id = pasta_id
    creds.pasta_raiz_nome = pasta_nome
    creds.save(update_fields=["pasta_raiz_id", "pasta_raiz_nome", "atualizado_em"])
    _reset_client()
    messages.success(request, f"Pasta \"{pasta_nome}\" definida como diretório de destino.")
    return redirect("google_drive:index")


# ---------------------------------------------------------------------------
# Organização em massa
# ---------------------------------------------------------------------------

def _pode_reorganizar(area=None) -> bool:
    cfg = getattr(settings, "GOOGLE_DRIVE", {})
    modo = cfg.get("MODO", "mock").lower()
    return bool(get_pasta_raiz_id(area)) and (esta_autorizado(area) or modo == "mock")


def _executar_reorganizacao(job_id: int) -> None:
    """Roda a reorganização e atualiza o job. Pensado para rodar numa thread."""
    from django.db import connection

    from integracoes.google_drive import organizer

    def progress(processados, total):
        DriveReorganizacaoJob.objects.filter(pk=job_id).update(
            eventos_processados=processados, total_eventos=total
        )

    try:
        resumo = organizer.reorganizar_tudo(progress=progress)
        DriveReorganizacaoJob.objects.filter(pk=job_id).update(
            status=DriveReorganizacaoJob.STATUS_CONCLUIDA,
            total_eventos=resumo["eventos"],
            eventos_processados=resumo["eventos"],
            avulsos=resumo["avulsos"],
            erros=resumo["erros"],
            finalizado_em=timezone.now(),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("[Drive] reorganização (job %s) falhou: %s", job_id, exc, exc_info=True)
        DriveReorganizacaoJob.objects.filter(pk=job_id).update(
            status=DriveReorganizacaoJob.STATUS_ERRO,
            mensagem=str(exc),
            finalizado_em=timezone.now(),
        )
    finally:
        # Threads abrem a própria conexão; fechá-la evita vazamento.
        connection.close()


@login_required
@require_POST
def reorganizar_tudo(request):
    if not _pode_reorganizar(_area_atual(request)):
        messages.error(
            request,
            "Conecte a conta Google e defina a pasta de destino antes de reorganizar.",
        )
        return redirect("google_drive:index")

    if DriveReorganizacaoJob.objects.filter(status=DriveReorganizacaoJob.STATUS_EM_ANDAMENTO).exists():
        messages.info(request, "Já existe uma reorganização em andamento. Aguarde concluir.")
        return redirect("google_drive:index")

    job = DriveReorganizacaoJob.objects.create(status=DriveReorganizacaoJob.STATUS_EM_ANDAMENTO)

    # Em testes (ou se configurado), roda de forma síncrona para ser determinístico.
    sincrono = getattr(settings, "GOOGLE_DRIVE", {}).get("REORG_SINCRONO", False)
    if sincrono:
        _executar_reorganizacao(job.pk)
    else:
        threading.Thread(target=_executar_reorganizacao, args=(job.pk,), daemon=True).start()

    messages.success(
        request,
        "Reorganização iniciada em segundo plano. O andamento aparece neste card — "
        "pode sair desta página; a tarefa continua rodando.",
    )
    return redirect("google_drive:index")


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
    job = DriveReorganizacaoJob.objects.order_by("-iniciado_em").first()
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

    for evento in Evento.objects.all().iterator():
        try:
            linhas.extend(organizer.planejar_evento(evento))
        except Exception:
            itens_com_erro += 1
            logger.warning("[Drive] falha ao planejar prévia do evento %s", evento.pk, exc_info=True)
            continue
        if len(linhas) >= limite:
            truncado = True
            break
    if not truncado:
        for oficio in Oficio.objects.filter(evento__isnull=True).iterator():
            try:
                linhas.extend(organizer.planejar_oficio(oficio))
            except Exception:
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


def _reprocessar_pendencias_em_thread() -> None:
    """Roda o reenvio de pendências fora do request (ver ``reprocessar_pendencias``)."""
    from django.db import connection

    from integracoes.google_drive import status

    try:
        mapa = _task_por_modelo()
        for pendencia in status.listar_pendencias(limite=500):
            task = mapa.get(pendencia.content_type.model)
            if task is None:
                continue
            try:
                task.delay(pendencia.object_id)
            except Exception as exc:
                logger.warning("[Drive] falha ao reagendar pendência %s: %s", pendencia.pk, exc)
    finally:
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
    sincrono = getattr(settings, "GOOGLE_DRIVE", {}).get("REORG_SINCRONO", False)
    if sincrono:
        _reprocessar_pendencias_em_thread()
    else:
        threading.Thread(target=_reprocessar_pendencias_em_thread, daemon=True).start()
    messages.success(
        request,
        "Reenvio das pendências iniciado em segundo plano. "
        "Atualize a página em instantes para ver a lista diminuir.",
    )
    return redirect("cadastros:configuracao")
