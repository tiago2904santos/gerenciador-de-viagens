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

from core.pagination import contexto_paginacao

from core.autosave import (
    AutosavePayloadError,
    autosave_json_response,
    filter_allowed_fields,
    parse_autosave_payload,
)
from core.tenancy import filter_queryset_by_area
from eventos.services import build_evento_document_seed
from eventos.services import resolve_evento_from_request
from .forms import RoteiroForm
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
from .services.diarias import capitais_por_uf
from .services.routing.route_preview_service import calculate_route_preview

from .models import Roteiro
from .presenters import (
    apresentar_contexto_formulario_roteiro_avulso,
    apresentar_linha_lista_simples_roteiro,
    apresentar_pagina_editor_roteiro,
    apresentar_roteiro_card,
)
from .selectors import (
    get_roteiro_by_id,
    listar_cidades_para_select,
    listar_roteiros,
)
from .services import (
    calcular_diarias_roteiro_request,
    carregar_opcoes_rotas_avulsas_salvas,
    excluir_roteiro,
    obter_initial_roteiro,
    preparar_estado_editor_roteiro_para_get,
    preparar_querysets_formulario_roteiro,
    processar_submissao_editor,
)
from .services.autosave import (
    ROTEIRO_AUTOSAVE_FIELDS,
    apply_roteiro_autosave,
    build_roteiro_draft,
    has_minimum_roteiro_content,
    pk_de_autosave,
)
from .services.estimativa_local import ROTA_FONTE_ESTIMATIVA_LOCAL
from .services.routing.trecho_route_service import calcular_rota_trecho

logger = logging.getLogger(__name__)

ROTEIROS_PER_PAGE = 15


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
    from django.db.models import OuterRef, Q
    from core import documento_abas as tabs
    from prestacoes_contas.models import PrestacaoServidor

    q = request.GET.get("q", "").strip()
    aba = tabs.normalizar_aba(request.GET.get("aba", ""))
    roteiros = listar_roteiros(q=q)

    # Finalizado = todas as prestações dos ofícios (não cancelados) vinculados
    # a este roteiro já foram finalizadas.
    sub = PrestacaoServidor.objects.filter(
        prestacao__oficio__roteiro=OuterRef("pk"),
        prestacao__oficio__cancelado=False,
    )
    roteiros = tabs.anotar_finalizacao(roteiros, sub, sub.filter(finalizada=False))
    cancelado_q = Q(cancelado=True)
    date_field = "saida_dt__date"

    lista = roteiros.filter(tabs.q_da_aba(aba, date_field=date_field, cancelado_q=cancelado_q))
    contagem = tabs.contar_por_aba(roteiros, date_field=date_field, cancelado_q=cancelado_q)
    abas = tabs.build_abas(
        reverse("roteiros:index"), aba, contagem,
        preserved={"q": q},
    )

    paginacao = contexto_paginacao(
        lista,
        request,
        ROTEIROS_PER_PAGE,
        query_params={"q": q, "aba": aba},
    )
    page_obj = paginacao["page_obj"]
    next_url = request.get_full_path()
    # Uma resolução para a página inteira (NOVO-27). Sem isto cada linha paga a
    # consulta de capitais: 15 linhas = 15 consultas a mais, e o teto do PF-07
    # para `roteiros:index` saiu de 32 para 47.
    capitais = capitais_por_uf()
    linhas = [
        apresentar_linha_lista_simples_roteiro(
            roteiro,
            edit_url=f"{reverse('roteiros:editar', args=[roteiro.pk])}?{urlencode({'next': next_url})}",
            delete_url=reverse("roteiros:excluir", args=[roteiro.pk]),
            delete_modal=True,
            capitais=capitais,
        )
        for roteiro in page_obj.object_list
    ]
    return render(
        request,
        "roteiros/index.html",
        {
            "page_title": "Roteiros",
            "page_description": "Sede, destinos, período, trechos e diárias prontos para reutilizar em documentos.",
            "create_url": reverse("roteiros:novo"),
            "search_clear_url": f"{reverse('roteiros:index')}?aba={aba}",
            "empty_message": "Nenhum roteiro cadastrado ainda.",
            "linhas": linhas,
            "q": q,
            "aba": aba,
            "abas": abas,
            **paginacao,
        },
    )


def _resolver_rascunho_autosave(request):
    pk = pk_de_autosave(request.POST)
    if pk is None:
        return None
    # O escopo do fluxo avulso é a área ativa; o do ofício é a área do ofício
    # (`oficios/route_views.py`). Por isso o `BE-11` compartilhou só o parse.
    return filter_queryset_by_area(Roteiro.objects).filter(pk=pk).first()


def _responder_submissao_editor(
    request, resultado, form, *, evento, msg_sucesso, msg_duplicado, next_url=""
):
    """Traduz o resultado da submissão em redirect, ou em erro no form.

    `BE-11`: o que `novo` e `editar` faziam igual aqui era tudo menos três coisas — o
    texto do sucesso simples, o texto do sucesso por fusão no duplicado (só `editar` fala
    em descarte, porque só lá havia registro a descartar) e o `?next=`, que só `editar`
    aceita. Viraram parâmetros. Devolve `None` quando é para re-renderizar a página.
    """
    if resultado.salvo:
        messages.success(
            request,
            msg_duplicado.format(pk=resultado.duplicado.pk)
            if resultado.fundiu_no_duplicado
            else msg_sucesso,
        )
        if next_url:
            return redirect(next_url)
        if evento is not None:
            return redirect("eventos:guiado_etapa", pk=evento.pk, etapa=2)
        return redirect("roteiros:index")

    if resultado.colisao_sem_saida:
        form.add_error(
            None,
            f"Já existe um roteiro idêntico salvo (#{resultado.duplicado.pk}). "
            "Edite o existente ou ajuste os dados.",
        )
    for error in resultado.erros_de_validacao():
        form.add_error(None, error)
    return None


def novo(request):
    evento = resolve_evento_from_request(request)
    initial = _initial_roteiro_evento(evento)

    rascunho = _resolver_rascunho_autosave(request) if request.method == "POST" else None
    form = RoteiroForm(request.POST or None, initial=initial, instance=rascunho)
    if rascunho is None:
        form.instance.evento = evento
        form.instance.tipo = Roteiro.TIPO_EVENTO if evento is not None else Roteiro.TIPO_AVULSO
    if request.method != "POST" and initial:
        form.instance.origem_cidade_id = initial.get("origem_cidade")
        form.instance.origem_estado_id = initial.get("origem_estado")

    preparar_querysets_formulario_roteiro(
        form, method=request.method, post=request.POST, instance=rascunho
    )
    route_options, route_state_map = carregar_opcoes_rotas_avulsas_salvas(evento=evento)

    if request.method == "POST":
        resultado = processar_submissao_editor(
            request.POST, form, route_state_map, roteiro=rascunho, evento=evento
        )
        resposta = _responder_submissao_editor(
            request,
            resultado,
            form,
            evento=evento,
            msg_sucesso="Roteiro cadastrado com sucesso.",
            msg_duplicado="Já existia um roteiro idêntico (#{pk}); os dados foram atualizados nele.",
        )
        if resposta is not None:
            return resposta
        destinos_atuais, trechos_list, roteiro_state = resultado.estado_para_rerender()
    else:
        destinos_atuais, trechos_list, roteiro_state = preparar_estado_editor_roteiro_para_get(
            initial=initial
        )

    return render(
        request,
        "roteiros/roteiro_form_page.html",
        apresentar_pagina_editor_roteiro(
            contexto_editor=apresentar_contexto_formulario_roteiro_avulso(
                evento=evento,
                form=form,
                obj=None,
                destinos_atuais=destinos_atuais,
                trechos_list=trechos_list,
                roteiro_state=roteiro_state,
                route_options=route_options,
            ),
            titulo="Novo roteiro",
            descricao="Sede, destinos, trechos, retorno e diárias no mesmo fluxo do legacy.",
            back_url=_roteiro_return_url(evento=evento),
            back_label="Dados do evento" if evento is not None else "Voltar para lista",
            form_action=_roteiro_form_action(request, evento),
        ),
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
    route_options, route_state_map = carregar_opcoes_rotas_avulsas_salvas(evento=evento, excluir_pk=roteiro.pk)

    if request.method == "POST":
        resultado = processar_submissao_editor(
            request.POST, form, route_state_map, roteiro=roteiro, evento=evento
        )
        resposta = _responder_submissao_editor(
            request,
            resultado,
            form,
            evento=evento,
            next_url=next_url,
            msg_sucesso="Roteiro atualizado com sucesso.",
            msg_duplicado=(
                "Já existia um roteiro idêntico (#{pk}); os dados foram atualizados "
                "nele e este registro foi descartado."
            ),
        )
        if resposta is not None:
            return resposta
        destinos_atuais, trechos_list, roteiro_state = resultado.estado_para_rerender()
    else:
        destinos_atuais, trechos_list, roteiro_state = preparar_estado_editor_roteiro_para_get(
            roteiro=roteiro
        )

    back_url = next_url or (
        _roteiro_return_url(roteiro=roteiro) if roteiro.evento_id else reverse("roteiros:index")
    )
    return render(
        request,
        "roteiros/roteiro_form_page.html",
        apresentar_pagina_editor_roteiro(
            contexto_editor=apresentar_contexto_formulario_roteiro_avulso(
                evento=evento,
                form=form,
                obj=roteiro,
                destinos_atuais=destinos_atuais,
                trechos_list=trechos_list,
                roteiro_state=roteiro_state,
                route_options=route_options,
            ),
            titulo="Editar roteiro",
            descricao="Ajuste sede, destinos, trechos e retorno.",
            back_url=back_url,
            back_label="Voltar"
            if next_url
            else ("Dados do evento" if roteiro.evento_id else "Voltar para lista"),
            form_action=request.get_full_path(),
            roteiro=roteiro,
        ),
    )


def excluir(request, pk):
    roteiro = get_roteiro_by_id(pk)
    evento_id = roteiro.evento_id
    if request.method == "POST":
        if not excluir_roteiro(roteiro):
            messages.error(request, "Este roteiro possui vínculos e não pode ser excluído.")
            if evento_id:
                return redirect("eventos:guiado_etapa", pk=evento_id, etapa=2)
            return redirect("roteiros:editar", pk=roteiro.pk)
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
            "back_url": _roteiro_return_url(roteiro=roteiro) if evento_id else reverse("roteiros:editar", args=[roteiro.pk]),
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
        _, _, validated, resultado = calcular_diarias_roteiro_request(request.POST)
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
    area = getattr(evento, "area", None) or getattr(request, "area", None)
    if area is None:
        return autosave_json_response(
            ok=False,
            message="Selecione uma área de trabalho antes de criar o roteiro.",
        )
    try:
        payload = parse_autosave_payload(request, expected_model="roteiro")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    clean_fields = filter_allowed_fields(payload.fields, payload.dirty_fields, ROTEIRO_AUTOSAVE_FIELDS)
    if not has_minimum_roteiro_content(clean_fields, payload.snapshots):
        return autosave_json_response(ok=False, message="Conteúdo insuficiente para criar rascunho.")

    roteiro = build_roteiro_draft(area=area)
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
