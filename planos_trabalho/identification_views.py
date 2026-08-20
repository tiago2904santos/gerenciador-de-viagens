from __future__ import annotations
import json
from django.contrib import messages
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST
from core.autosave import AutosavePayloadError
from core.autosave import autosave_json_response
from core.autosave import filter_allowed_fields
from core.autosave import parse_autosave_payload
from core.retorno import com_next
from core.retorno import daqui
from .forms import PlanoIdentificacaoForm
from .models import PlanoTrabalho
from .identificacao_services import flags_automaticas
from .identificacao_services import salvar_identificacao_do_autosave
from .identificacao_services import salvar_identificacao_do_wizard
from .presenters import apresentar_resumo_evento_card
from .presenters import apresentar_resumo_header
from .services import eventos_para_cards
from .services import texto_padrao_consideracao_final
from .services import texto_padrao_coordenacao
from .services import texto_padrao_contextualizacao
from .services import textos_padrao_templates
from core.wizard import normalizar_acao_do_wizard

from .view_helpers import _get_plano, _redirect_plano_lista, _wizard_shell_ctx, _plano_autosave_version, _querydict_from_pairs, _merge_payload_fields, _autosave_form_errors


def _plano_identificacao_autosave_data(plano: PlanoTrabalho):
    data = {
        "programa": plano.programa_id or "",
        "programa_outros": plano.programa_outros or "",
        "destino_estado": plano.destino_estado_id or "",
        "destino_cidade": plano.destino_cidade_id or "",
        "data_evento_inicio": plano.data_evento_inicio.isoformat() if plano.data_evento_inicio else "",
        "data_evento_fim": plano.data_evento_fim.isoformat() if plano.data_evento_fim else "",
        "horario_atendimento": plano.horario_atendimento or "",
        "contextualizacao": plano.contextualizacao or "",
        "coordenacao": plano.coordenacao or "",
        "consideracao_final": plano.consideracao_final or "",
        "coordenador_adm_modo": plano.coordenador_adm_modo or PlanoTrabalho.COORDENADOR_MODO_SERVIDOR,
        "coordenador_adm": plano.coordenador_adm_id or "",
        "coordenador_adm_nome_manual": plano.coordenador_adm_nome_manual or "",
        "coordenador_adm_cargo_manual": plano.coordenador_adm_cargo_manual or "",
        "coordenador_adm_genero": plano.coordenador_adm_genero or PlanoTrabalho.COORDENADOR_GENERO_MASCULINO,
        "coordenador_op_modo": plano.coordenador_op_modo or PlanoTrabalho.COORDENADOR_MODO_SERVIDOR,
        "coordenador_op": plano.coordenador_op_id or "",
        "coordenador_op_nome_manual": plano.coordenador_op_nome_manual or "",
        "coordenador_op_cargo_manual": plano.coordenador_op_cargo_manual or "",
        "coordenador_op_genero": plano.coordenador_op_genero or PlanoTrabalho.COORDENADOR_GENERO_MASCULINO,
    }
    destinos = list(plano.destinos.filter(evento__isnull=True).order_by("ordem", "pk"))
    for idx, destino in enumerate(destinos[1:], 1):
        data[f"destino_estado_{idx}"] = destino.estado_id
        data[f"destino_cidade_{idx}"] = destino.cidade_id
    return _querydict_from_pairs(data)


def _evento_selected_dates_json(form):
    def as_iso(value):
        if not value:
            return ""
        if hasattr(value, "isoformat"):
            return value.isoformat()
        value = str(value).strip()
        if len(value) == 10 and value[4:5] == "-" and value[7:8] == "-":
            return value
        return ""

    if form.is_bound:
        inicio = as_iso(form.data.get("data_evento_inicio"))
        fim = as_iso(form.data.get("data_evento_fim"))
    else:
        inicio = as_iso(getattr(form.instance, "data_evento_inicio", None))
        fim = as_iso(getattr(form.instance, "data_evento_fim", None))

    if not inicio and not fim:
        return "[]"
    if inicio and not fim:
        return json.dumps([inicio])
    if fim and not inicio:
        return json.dumps([fim])
    if inicio == fim:
        return json.dumps([inicio])
    return json.dumps([inicio, fim])


def _evento_display_values(form):
    def as_display(value):
        if not value:
            return ""
        if hasattr(value, "strftime"):
            return value.strftime("%d/%m/%Y")
        value = str(value).strip()
        if len(value) == 10 and value[4:5] == "-" and value[7:8] == "-":
            partes = value.split("-")
            return f"{partes[2]}/{partes[1]}/{partes[0]}"
        return value

    if form.is_bound:
        return {
            "inicio": as_display(form.data.get("data_evento_inicio")),
            "fim": as_display(form.data.get("data_evento_fim")),
        }
    return {
        "inicio": as_display(getattr(form.instance, "data_evento_inicio", None)),
        "fim": as_display(getattr(form.instance, "data_evento_fim", None)),
    }


def _texto_auto_flag(form, plano, post_name, attr):
    if form.is_bound:
        return (form.data.get(post_name, "1") or "0").strip() != "0"
    return getattr(plano, attr)


def _identificacao_context(*, form, plano, request):
    eventos_commitados = eventos_para_cards(plano)
    eventos_resumo = [apresentar_resumo_evento_card(e) for e in eventos_commitados]
    return {
        "page_title": "Plano de Trabalho",
        **_wizard_shell_ctx(plano=plano, etapa_atual="identificacao"),
        "form": form,
        "api_cidades_por_estado_url": reverse("roteiros:api_cidades_por_estado", kwargs={"estado_id": 0}),
        "evento_selected_dates_json": _evento_selected_dates_json(form),
        "evento_display": _evento_display_values(form),
        "cargos_url": com_next(reverse("cadastros:cargos_index"), daqui(request)),
        "programas_url": com_next(reverse("planos_trabalho:programas_index"), daqui(request)),
        "horarios_url": com_next(reverse("planos_trabalho:horarios_index"), daqui(request)),
        "wizard_autosave_url": reverse("planos_trabalho:identificacao_autosave", args=[plano.pk]),
        "wizard_autosave_step": "identificacao",
        "coordenador_adm_modo_atual": plano.coordenador_adm_modo,
        "coordenador_op_modo_atual": plano.coordenador_op_modo,
        "pt_textos_padrao_templates": textos_padrao_templates(),
        "contextualizacao_auto": _texto_auto_flag(form, plano, "contextualizacao_auto", "contextualizacao_auto"),
        "coordenacao_auto": _texto_auto_flag(form, plano, "coordenacao_auto", "coordenacao_auto"),
        "consideracao_auto": _texto_auto_flag(form, plano, "consideracao_auto", "consideracao_auto"),
        # Multi-evento
        "is_multi_evento": plano.is_multi_evento,
        "eventos_resumo": eventos_resumo,
        "resumo_header": apresentar_resumo_header(plano),
        "total_eventos_commitados": len(eventos_resumo),
        "em_edicao_evento": plano.evento_em_edicao_id,
    }


def wizard_identificacao(request, pk):
    plano = _get_plano(pk)
    form = PlanoIdentificacaoForm(request.POST or None, instance=plano)
    if request.method == "POST":
        nav_action = normalizar_acao_do_wizard(request.POST)
        if form.is_valid():
            plano = salvar_identificacao_do_wizard(
                form, flags=flags_automaticas(request.POST)
            )
            if nav_action == "wizard_next":
                messages.success(request, "Identificação salva. Continue com o efetivo e as diárias.")
                return redirect("planos_trabalho:wizard_efetivo_diarias", pk=plano.pk)
            if nav_action == "save_draft_list":
                messages.success(request, "Plano salvo. Retornamos à lista.")
                return _redirect_plano_lista(plano)
            messages.success(request, "Identificação salva.")
            return redirect("planos_trabalho:wizard_identificacao", pk=plano.pk)
    else:
        # GET: mostra o texto padrão já preenchido (destino + programa) enquanto o
        # campo estiver no modo automático — o usuário pode sobrescrever quando quiser.
        if plano.contextualizacao_auto:
            form.initial["contextualizacao"] = texto_padrao_contextualizacao(plano)
        if plano.coordenacao_auto:
            form.initial["coordenacao"] = texto_padrao_coordenacao(plano)
        if plano.consideracao_auto:
            form.initial["consideracao_final"] = texto_padrao_consideracao_final(plano)
    return render(
        request,
        "planos_trabalho/wizard_identificacao.html",
        _identificacao_context(form=form, plano=plano, request=request),
    )


@require_POST
def identificacao_autosave(request, pk):
    plano = _get_plano(pk)
    try:
        payload = parse_autosave_payload(request, expected_model="plano_trabalho")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    allowed_fields = set(PlanoIdentificacaoForm.Meta.fields)
    clean_fields = filter_allowed_fields(payload.fields, payload.dirty_fields, allowed_fields)
    if not clean_fields:
        return autosave_json_response(ok=True, object_id=plano.pk, version=_plano_autosave_version(plano))

    data = _merge_payload_fields(_plano_identificacao_autosave_data(plano), clean_fields)
    form = PlanoIdentificacaoForm(data, instance=plano)
    if not form.is_valid():
        return autosave_json_response(
            ok=False,
            message="Alguns campos ainda precisam de ajuste antes do autosave.",
            errors=_autosave_form_errors(form),
        )
    plano = salvar_identificacao_do_autosave(form, campos_editados=clean_fields)
    return autosave_json_response(ok=True, object_id=plano.pk, version=_plano_autosave_version(plano))
