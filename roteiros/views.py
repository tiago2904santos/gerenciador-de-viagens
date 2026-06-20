import json
import logging
from datetime import datetime
from datetime import time
from urllib.parse import urlencode

from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import RoteiroForm
from core.autosave import (
    AutosavePayloadError,
    autosave_json_response,
    filter_allowed_fields,
    parse_autosave_payload,
)
from eventos.services import build_evento_document_seed
from eventos.services import resolve_evento_from_request
from .services.routing.route_exceptions import (
    RouteAuthenticationError,
    RouteConfigurationError,
    RouteCoordinateError,
    RouteDailyRoundTripBlockedError,
    RouteNotFoundError,
    RouteProviderUnavailable,
    RouteRateLimitError,
    RouteServiceError,
    RouteTimeoutError,
    RouteValidationError,
)
from .services.routing.route_service import calcular_rota_para_roteiro
from .services.routing.route_preview_service import calculate_route_preview

logger = logging.getLogger(__name__)
from .models import Roteiro
from .presenters import (
    apresentar_contexto_formulario_roteiro_avulso,
    apresentar_pagina_detalhe_roteiro,
    apresentar_roteiro_card,
)
from .selectors import (
    get_roteiro_by_id,
    listar_cidades_para_select,
    listar_roteiros,
    listar_trechos_do_roteiro,
)
from .services import (
    atualizar_roteiro,
    calcular_diarias_roteiro_request,
    carregar_opcoes_rotas_avulsas_salvas,
    criar_roteiro,
    excluir_roteiro,
    normalizar_destinos_e_trechos_apos_erro_post,
    obter_initial_roteiro,
    preparar_estado_editor_roteiro_para_get,
    preparar_querysets_formulario_roteiro,
    validar_submissao_editor_roteiro,
)
from .services.autosave import (
    ROTEIRO_AUTOSAVE_FIELDS,
    apply_roteiro_autosave,
    build_roteiro_draft,
    has_minimum_roteiro_content,
)
from .services.estimativa_local import ROTA_FONTE_ESTIMATIVA_LOCAL
from .services.routing.trecho_route_service import calcular_rota_trecho


def _evento_etapa_url(evento_id):
    if evento_id:
        return reverse("eventos:guiado_etapa", kwargs={"pk": evento_id, "etapa": 2})
    return ""


def _roteiro_return_url(roteiro=None, evento=None):
    evento_id = getattr(evento, "pk", None) or getattr(roteiro, "evento_id", None)
    return _evento_etapa_url(evento_id) or reverse("roteiros:index")


def _roteiro_form_action(request, evento=None):
    if evento is None:
        return request.path
    return f"{request.path}?{urlencode({'evento': evento.pk})}"


def _initial_roteiro_evento(evento):
    initial = obter_initial_roteiro()
    if evento is None:
        return initial
    seed = build_evento_document_seed(evento)
    cidade = seed.get("cidade")
    estado = seed.get("estado")
    if estado:
        initial["destino_estado"] = estado.pk
        initial["destino_estado_id"] = estado.pk
    if cidade:
        initial["destino_cidade"] = cidade.pk
        initial["destino_cidade_id"] = cidade.pk
    inicio = seed.get("data_inicio")
    fim = seed.get("data_fim") or inicio
    if inicio:
        saida_hora = evento.horario_inicio or time(8, 0)
        saida_dt = datetime.combine(inicio, saida_hora)
        initial["saida_dt"] = saida_dt
        initial["saida_data"] = inicio.isoformat()
    if fim:
        retorno_hora = evento.horario_fim or time(16, 0)
        retorno_dt = datetime.combine(fim, retorno_hora)
        initial["retorno_saida_dt"] = retorno_dt
        initial["retorno_data"] = fim.isoformat()
    initial["seed_source_label"] = "Pre-preenchido pelo evento."
    return initial


def index(request):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    roteiros = listar_roteiros(q=q, status=status or None)
    cards = [apresentar_roteiro_card(roteiro) for roteiro in roteiros]
    return render(
        request,
        "roteiros/index.html",
        {
            "page_title": "Roteiros",
            "page_description": "Sede, destinos, período, trechos e diárias prontos para reutilizar em documentos.",
            "create_url": reverse("roteiros:novo"),
            "search_clear_url": reverse("roteiros:index"),
            "empty_message": "Nenhum roteiro cadastrado ainda.",
            "cards": cards,
            "q": q,
            "status": status,
            "status_options": [{"value": "", "label": "Todos os status"}]
            + [{"value": value, "label": label} for value, label in Roteiro.STATUS_CHOICES],
        },
    )


def novo(request):
    evento = resolve_evento_from_request(request)
    initial = _initial_roteiro_evento(evento)
    form = RoteiroForm(request.POST or None, initial=initial)
    form.instance.evento = evento
    form.instance.tipo = Roteiro.TIPO_EVENTO if evento is not None else Roteiro.TIPO_AVULSO
    if request.method != "POST" and initial:
        form.instance.origem_cidade_id = initial.get("origem_cidade")
        form.instance.origem_estado_id = initial.get("origem_estado")

    preparar_querysets_formulario_roteiro(
        form, method=request.method, post=request.POST, instance=None
    )
    route_options, route_state_map = carregar_opcoes_rotas_avulsas_salvas()

    if request.method == "POST":
        roteiro_state, validated, diarias_resultado = validar_submissao_editor_roteiro(
            request.POST, route_state_map, roteiro=None
        )
        if form.is_valid() and validated["ok"]:
            roteiro = criar_roteiro(form, roteiro_state, validated, diarias_resultado, evento=evento)
            messages.success(request, "Roteiro cadastrado com sucesso.")
            if evento is not None:
                return redirect("eventos:guiado_etapa", pk=evento.pk, etapa=2)
            return redirect("roteiros:detalhe", pk=roteiro.pk)
        for error in validated.get("errors", []):
            form.add_error(None, error)
        destinos_atuais, trechos_list = normalizar_destinos_e_trechos_apos_erro_post(roteiro_state)
    else:
        destinos_atuais, trechos_list, roteiro_state = preparar_estado_editor_roteiro_para_get(
            initial=initial
        )

    context = apresentar_contexto_formulario_roteiro_avulso(
        evento=evento,
        form=form,
        obj=None,
        destinos_atuais=destinos_atuais,
        trechos_list=trechos_list,
        roteiro_state=roteiro_state,
        route_options=route_options,
    )
    return render(
        request,
        "roteiros/roteiro_form_page.html",
        {
            "page_title": "Novo roteiro",
            "page_description": "Sede, destinos, trechos, retorno e diárias no mesmo fluxo do legacy.",
            "back_url": _roteiro_return_url(evento=evento),
            "wizard_header": {
                "title": "Novo roteiro",
                "description": "Roteiro e diárias",
                "status_label": "",
                "status_variant": "",
            },
            "wizard_back_label": "Dados do evento" if evento is not None else "Voltar para lista",
            "wizard_back_url": _roteiro_return_url(evento=evento),
            "wizard_page_steps": [],
            "roteiro_editor_oficio": True,
            "roteiro_form_action": _roteiro_form_action(request, evento),
            **context,
        },
    )


def detalhe(request, pk):
    roteiro = get_roteiro_by_id(pk)
    trechos = listar_trechos_do_roteiro(roteiro)
    context = apresentar_pagina_detalhe_roteiro(roteiro, trechos)
    if roteiro.evento_id:
        context["back_url"] = _roteiro_return_url(roteiro=roteiro)
    return render(
        request,
        "roteiros/detail.html",
        context,
    )


def _next_url_seguro(request):
    """URL local de retorno (?next=), validada contra open redirect."""
    from django.utils.http import url_has_allowed_host_and_scheme

    candidato = request.GET.get("next") or ""
    if candidato and url_has_allowed_host_and_scheme(
        candidato, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidato
    return ""


def editar(request, pk):
    roteiro = get_roteiro_by_id(pk)
    evento = roteiro.evento if roteiro.evento_id else None
    next_url = _next_url_seguro(request)
    form = RoteiroForm(request.POST or None, instance=roteiro)

    preparar_querysets_formulario_roteiro(
        form, method=request.method, post=request.POST, instance=roteiro
    )
    route_options, route_state_map = carregar_opcoes_rotas_avulsas_salvas()

    if request.method == "POST":
        roteiro_state, validated, diarias_resultado = validar_submissao_editor_roteiro(
            request.POST, route_state_map, roteiro=roteiro
        )
        if form.is_valid() and validated["ok"]:
            atualizar_roteiro(roteiro, form, roteiro_state, validated, diarias_resultado)
            messages.success(request, "Roteiro atualizado com sucesso.")
            if next_url:
                return redirect(next_url)
            if roteiro.evento_id:
                return redirect("eventos:guiado_etapa", pk=roteiro.evento_id, etapa=2)
            return redirect("roteiros:detalhe", pk=roteiro.pk)
        for error in validated.get("errors", []):
            form.add_error(None, error)
        destinos_atuais, trechos_list = normalizar_destinos_e_trechos_apos_erro_post(roteiro_state)
    else:
        destinos_atuais, trechos_list, roteiro_state = preparar_estado_editor_roteiro_para_get(
            roteiro=roteiro
        )

    context = apresentar_contexto_formulario_roteiro_avulso(
        evento=evento,
        form=form,
        obj=roteiro,
        destinos_atuais=destinos_atuais,
        trechos_list=trechos_list,
        roteiro_state=roteiro_state,
        route_options=route_options,
    )
    roteiro_status_label = roteiro.get_status_display() if hasattr(roteiro, "get_status_display") else ""
    roteiro_status_variant = "draft" if roteiro.status == Roteiro.STATUS_RASCUNHO else "active"
    return render(
        request,
        "roteiros/roteiro_form_page.html",
        {
            "page_title": "Editar roteiro",
            "page_description": "Ajuste sede, destinos, trechos e retorno.",
            "back_url": next_url or (_roteiro_return_url(roteiro=roteiro) if roteiro.evento_id else reverse("roteiros:detalhe", args=[roteiro.pk])),
            "delete_url": reverse("roteiros:excluir", args=[roteiro.pk]),
            "wizard_header": {
                "title": "Editar roteiro",
                "description": "Roteiro e diárias",
                "status_label": roteiro_status_label,
                "status_variant": roteiro_status_variant,
            },
            "wizard_back_label": "Voltar" if next_url else ("Dados do evento" if roteiro.evento_id else "Voltar para detalhes"),
            "wizard_back_url": next_url or (_roteiro_return_url(roteiro=roteiro) if roteiro.evento_id else reverse("roteiros:detalhe", args=[roteiro.pk])),
            "wizard_page_steps": [],
            "roteiro_editor_oficio": True,
            "roteiro_form_action": request.get_full_path(),
            **context,
        },
    )


def excluir(request, pk):
    roteiro = get_roteiro_by_id(pk)
    evento_id = roteiro.evento_id
    if request.method == "POST":
        if not excluir_roteiro(roteiro):
            messages.error(request, "Este roteiro possui vínculos e não pode ser excluído.")
            if evento_id:
                return redirect("eventos:guiado_etapa", pk=evento_id, etapa=2)
            return redirect("roteiros:detalhe", pk=roteiro.pk)
        messages.success(request, "Roteiro excluído com sucesso.")
        if evento_id:
            return redirect("eventos:guiado_etapa", pk=evento_id, etapa=2)
        return redirect("roteiros:index")

    return render(
        request,
        "roteiros/confirm_delete.html",
        {
            "page_title": "Excluir roteiro",
            "page_description": "Confirme a exclusão do roteiro selecionado.",
            "object": roteiro,
            "back_url": _roteiro_return_url(roteiro=roteiro) if evento_id else reverse("roteiros:detalhe", args=[roteiro.pk]),
        },
    )


def api_cidades_por_estado(request, estado_id):
    q = request.GET.get("q", "").strip()
    cidades = listar_cidades_para_select(estado_id=estado_id, q=q or None)
    payload = [{"id": c.pk, "nome": str(c.nome)} for c in cidades]
    return JsonResponse(payload, safe=False)


@require_http_methods(["POST"])
def calcular_diarias(request):
    try:
        _, _, validated, resultado = calcular_diarias_roteiro_request(request)
    except ValueError as exc:
        return JsonResponse(
            {
                "ok": False,
                "error": str(exc) or "Revise os dados do roteiro antes de calcular as diárias.",
                "errors": [str(exc)] if str(exc) else [],
            },
            status=400,
        )
    if not validated["ok"]:
        return JsonResponse(
            {
                "ok": False,
                "error": "Revise os dados do roteiro antes de calcular as diárias.",
                "errors": validated["errors"],
            },
            status=400,
        )
    if not resultado:
        return JsonResponse(
            {"ok": False, "error": "Revise os dados do roteiro antes de calcular as diárias."},
            status=400,
        )
    payload = {"ok": True, "roteiros_disponiveis": 0}
    payload.update(resultado)
    if resultado and resultado.get("totais"):
        payload["quantidade_servidores"] = resultado["totais"].get("quantidade_servidores")
    return JsonResponse(payload)


@require_http_methods(["POST"])
def calcular_rota(request):
    """Calcula rota consolidada via backend (OpenRouteService); nunca expõe chave de API."""
    try:
        body = json.loads(request.body or "{}")
    except (json.JSONDecodeError, TypeError):
        body = {}
    if "openrouteservice_api_key" in body or "api_key" in body:
        logger.warning("calcular_rota: tentativa de enviar chave de API no payload.")
        return JsonResponse(
            {
                "ok": False,
                "message": "Requisição inválida.",
            },
            status=400,
        )
    roteiro_id = body.get("roteiro_id")
    force = bool(body.get("force_recalculate"))
    try:
        rid = int(roteiro_id)
    except (TypeError, ValueError):
        rid = None
    if not rid:
        return JsonResponse(
            {
                "ok": False,
                "message": "Salve o roteiro antes de calcular a rota no mapa.",
            },
            status=400,
        )
    try:
        roteiro = get_roteiro_by_id(rid)
    except Http404:
        return JsonResponse(
            {"ok": False, "message": "Roteiro não encontrado."},
            status=404,
        )
    try:
        payload = calcular_rota_para_roteiro(roteiro, force_recalculate=force)
        return JsonResponse(payload)
    except RouteAuthenticationError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=401)
    except RouteConfigurationError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=503)
    except RouteCoordinateError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=400)
    except RouteDailyRoundTripBlockedError as exc:
        return JsonResponse(
            {
                "ok": False,
                "blocked": True,
                "reason": exc.reason,
                "message": exc.user_message,
            },
            status=400,
        )
    except RouteValidationError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=400)
    except RouteTimeoutError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=504)
    except RouteRateLimitError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=429)
    except RouteNotFoundError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=404)
    except RouteProviderUnavailable as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=502)
    except RouteServiceError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=400)
    except Exception as exc:
        logger.exception("calcular_rota falhou: %s", exc)
        return JsonResponse(
            {
                "ok": False,
                "message": "Não foi possível calcular a rota automaticamente. Você pode preencher a distância e o tempo manualmente.",
            },
            status=500,
        )


@require_http_methods(["POST"])
def trechos_estimar(request):
    """Estima um trecho operacional (origem → destino). Usa OpenRouteService se configurado; senão estimativa local."""
    try:
        body = json.loads(request.body or "{}")
        origem_id = body.get("origem_cidade_id")
        destino_id = body.get("destino_cidade_id")
    except (json.JSONDecodeError, TypeError):
        origem_id = destino_id = None
    if not origem_id or not destino_id:
        return JsonResponse(
            {
                "ok": False,
                "distancia_km": None,
                "duracao_estimada_min": None,
                "duracao_estimada_hhmm": "",
                "tempo_cru_estimado_min": None,
                "tempo_adicional_sugerido_min": None,
                "rota_fonte": ROTA_FONTE_ESTIMATIVA_LOCAL,
                "ors_fallback": False,
                "erro": "Informe origem_cidade_id e destino_cidade_id.",
            }
        )
    raw = calcular_rota_trecho(origem_id, destino_id)
    if not raw.get("ok"):
        return JsonResponse(
            {
                "ok": False,
                "distancia_km": None,
                "duracao_estimada_min": None,
                "duracao_estimada_hhmm": "",
                "tempo_cru_estimado_min": None,
                "tempo_adicional_sugerido_min": None,
                "rota_fonte": raw.get("rota_fonte") or ROTA_FONTE_ESTIMATIVA_LOCAL,
                "ors_fallback": raw.get("ors_fallback", False),
                "erro": raw.get("erro") or "Não foi possível estimar o trecho.",
            }
        )

    dist_km = raw.get("distancia_km")
    return JsonResponse(
        {
            "ok": True,
            "origem": raw.get("origem"),
            "destino": raw.get("destino"),
            "distancia_km": float(dist_km) if dist_km is not None else None,
            "distancia_linha_reta_km": raw.get("distancia_linha_reta_km"),
            "distancia_rodoviaria_km": raw.get("distancia_rodoviaria_km"),
            "duracao_estimada_min": raw.get("duracao_estimada_min"),
            "duracao_estimada_hhmm": raw.get("duracao_estimada_hhmm"),
            "tempo_viagem_estimado_min": raw.get("tempo_viagem_estimado_min"),
            "tempo_viagem_estimado_hhmm": raw.get("tempo_viagem_estimado_hhmm"),
            "buffer_operacional_sugerido_min": raw.get("buffer_operacional_sugerido_min"),
            "tempo_cru_estimado_min": raw.get("tempo_cru_estimado_min"),
            "tempo_adicional_sugerido_min": raw.get("tempo_adicional_sugerido_min"),
            "correcao_final_min": raw.get("correcao_final_min"),
            "velocidade_media_kmh": raw.get("velocidade_media_kmh"),
            "perfil_rota": raw.get("perfil_rota"),
            "corredor": raw.get("corredor"),
            "corredor_macro": raw.get("corredor_macro"),
            "corredor_fino": raw.get("corredor_fino"),
            "rota_fonte": raw.get("rota_fonte"),
            "fallback_usado": raw.get("fallback_usado"),
            "ors_fallback": raw.get("ors_fallback"),
            "confianca_estimativa": raw.get("confianca_estimativa"),
            "refs_predominantes": raw.get("refs_predominantes") or [],
            "pedagio_presente": raw.get("pedagio_presente", False),
            "travessia_urbana_presente": raw.get("travessia_urbana_presente", False),
            "serra_presente": raw.get("serra_presente", False),
            "erro": raw.get("erro") or "",
            "duration_human": raw.get("duration_human"),
        }
    )


@require_http_methods(["POST"])
def calcular_rota_preview(request):
    """
    Preview de rota sem persistência para rascunho de tela (novo roteiro sem salvar).
    """
    try:
        body = json.loads(request.body or "{}")
    except (json.JSONDecodeError, TypeError):
        body = {}
    if "openrouteservice_api_key" in body or "api_key" in body:
        logger.warning("calcular_rota_preview: tentativa de enviar chave de API no payload.")
        return JsonResponse({"ok": False, "message": "Requisição inválida."}, status=400)
    try:
        return JsonResponse(calculate_route_preview(body))
    except RouteAuthenticationError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=401)
    except RouteConfigurationError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=503)
    except RouteCoordinateError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=400)
    except RouteDailyRoundTripBlockedError as exc:
        return JsonResponse(
            {
                "ok": False,
                "blocked": True,
                "reason": exc.reason,
                "message": exc.user_message,
            },
            status=400,
        )
    except RouteValidationError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=400)
    except RouteTimeoutError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=504)
    except RouteRateLimitError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=429)
    except RouteNotFoundError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=404)
    except RouteProviderUnavailable as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=502)
    except RouteServiceError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=400)
    except Exception as exc:
        logger.exception("calcular_rota_preview falhou: %s", exc)
        return JsonResponse(
            {
                "ok": False,
                "message": "Não foi possível calcular a rota automaticamente. Você pode preencher a distância e o tempo manualmente.",
            },
            status=500,
        )


@require_http_methods(["POST"])
def roteiro_autosave_create(request):
    evento = resolve_evento_from_request(request)
    try:
        payload = parse_autosave_payload(request, expected_model="roteiro")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    clean_fields = filter_allowed_fields(payload.fields, payload.dirty_fields, ROTEIRO_AUTOSAVE_FIELDS)
    if not has_minimum_roteiro_content(clean_fields, payload.snapshots):
        return autosave_json_response(ok=False, message="Conteúdo insuficiente para criar rascunho.")

    roteiro = build_roteiro_draft()
    if evento is not None:
        roteiro.evento = evento
        roteiro.tipo = Roteiro.TIPO_EVENTO
        roteiro.save(update_fields=["evento", "tipo", "updated_at"])
    version = apply_roteiro_autosave(roteiro, clean_fields, payload.snapshots)
    return autosave_json_response(ok=True, object_id=roteiro.pk, created=True, version=version)


@require_http_methods(["POST"])
def roteiro_autosave(request, pk):
    roteiro = get_roteiro_by_id(pk)
    try:
        payload = parse_autosave_payload(request, expected_model="roteiro")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    clean_fields = filter_allowed_fields(payload.fields, payload.dirty_fields, ROTEIRO_AUTOSAVE_FIELDS)
    version = apply_roteiro_autosave(roteiro, clean_fields, payload.snapshots)
    return autosave_json_response(ok=True, object_id=roteiro.pk, created=False, version=version)
