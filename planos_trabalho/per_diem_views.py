from __future__ import annotations
import json
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from core.autosave import AutosavePayloadError
from core.autosave import autosave_json_response
from core.autosave import filter_allowed_fields
from core.autosave import parse_autosave_payload
from core.retorno import com_next
from core.retorno import daqui
from .efetivo_services import salvar_efetivo_do_autosave
from .efetivo_services import salvar_efetivo_e_diarias
from .forms import EfetivoPlanoFormSet
from .forms import PlanoDiariasForm
from .models import PlanoTrabalho
from .selectors import get_evento_do_plano_by_id
from .services import calcular_diarias_combinadas
from .services import calcular_diarias_plano
from .services import adicionar_evento_ao_plano
from .services import editar_evento_no_scratchpad
from .services import remover_evento
from core.wizard import normalizar_acao_do_wizard

from .view_helpers import _get_plano, _redirect_plano_lista, _wizard_shell_ctx, _plano_autosave_version, _querydict_from_pairs, _merge_payload_fields, _autosave_form_errors


def _diarias_selected_dates_json(form):
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
        saida = as_iso(form.data.get("saida_sede_data"))
        chegada = as_iso(form.data.get("chegada_sede_data"))
    else:
        saida = as_iso(getattr(form.instance, "saida_sede_data", None))
        chegada = as_iso(getattr(form.instance, "chegada_sede_data", None))

    dates = [d for d in [saida, chegada] if d]
    dates = list(dict.fromkeys(dates))  # dedup preservando ordem
    return json.dumps(dates)


def _efetivo_diarias_context(*, formset, diarias_form, plano, request, resultado=None):
    resultado = resultado or calcular_diarias_plano(plano)
    return {
        "page_title": "Plano de Trabalho",
        **_wizard_shell_ctx(plano=plano, etapa_atual="efetivo_diarias"),
        "formset": formset,
        "diarias_form": diarias_form,
        "diarias_display": _diarias_display_values(diarias_form),
        "diarias_selected_dates_json": _diarias_selected_dates_json(diarias_form),
        "diarias_resultado": resultado,
        "cargos_url": com_next(reverse("cadastros:cargos_index"), daqui(request)),
        "api_calcular_diarias_url": reverse("planos_trabalho:api_calcular_diarias", args=[plano.pk]),
        "wizard_autosave_url": reverse("planos_trabalho:efetivo_diarias_autosave", args=[plano.pk]),
        "wizard_autosave_step": "efetivo_diarias",
    }


def _plano_diarias_autosave_data(plano: PlanoTrabalho):
    data = {
        "saida_sede_data": plano.saida_sede_data.isoformat() if plano.saida_sede_data else "",
        "saida_sede_hora": plano.saida_sede_hora.strftime("%H:%M") if plano.saida_sede_hora else "",
        "chegada_sede_data": plano.chegada_sede_data.isoformat() if plano.chegada_sede_data else "",
        "chegada_sede_hora": plano.chegada_sede_hora.strftime("%H:%M") if plano.chegada_sede_hora else "",
    }
    return _querydict_from_pairs(data)


def _efetivo_rows_from_formset(formset):
    """Converte o formset inline de efetivo em linhas para `reconciliar_efetivo`.

    Usa o `id` enviado (preenchido pelo autosave) em vez de depender do
    management form (INITIAL_FORMS), que pode estar defasado quando o autosave
    criou registros após o carregamento da página.
    """
    rows = []
    for index, form in enumerate(formset.forms):
        cleaned = getattr(form, "cleaned_data", None)
        if not cleaned or cleaned.get("DELETE"):
            continue
        unidade = cleaned.get("unidade")
        cargo = cleaned.get("cargo")
        pk = form.instance.pk or _to_int_or_none(form.data.get(form.add_prefix("id")))
        rows.append(
            {
                "idx": index,
                "id": pk,
                "unidade": unidade.pk if unidade else None,
                "cargo": cargo.pk if cargo else None,
                "quantidade": cleaned.get("quantidade"),
            }
        )
    return rows


def _to_int_or_none(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _diarias_display_values(form):
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
            "saida_data": as_display(form.data.get("saida_sede_data")),
            "chegada_data": as_display(form.data.get("chegada_sede_data")),
        }
    return {
        "saida_data": as_display(getattr(form.instance, "saida_sede_data", None)),
        "chegada_data": as_display(getattr(form.instance, "chegada_sede_data", None)),
    }


def wizard_efetivo_diarias(request, pk):
    plano = _get_plano(pk)
    formset = EfetivoPlanoFormSet(request.POST or None, instance=plano, prefix="efetivo")
    diarias_form = PlanoDiariasForm(request.POST or None, instance=plano)
    if request.method == "POST":
        nav_action = normalizar_acao_do_wizard(request.POST)
        if formset.is_valid() and diarias_form.is_valid():
            resultado = salvar_efetivo_e_diarias(
                plano, rows=_efetivo_rows_from_formset(formset), diarias_form=diarias_form
            ).diarias
            if nav_action == "wizard_back":
                messages.success(request, "Efetivo e diárias salvos.")
                return redirect("planos_trabalho:wizard_identificacao", pk=plano.pk)
            if nav_action == "wizard_next":
                if not resultado["ok"]:
                    for erro in resultado["erros"]:
                        messages.warning(request, erro)
                messages.success(request, "Efetivo e diárias salvos.")
                return redirect("planos_trabalho:wizard_atividades", pk=plano.pk)
            if nav_action == "save_draft_list":
                messages.success(request, "Plano salvo. Retornamos à lista.")
                return _redirect_plano_lista(plano)
            messages.success(request, "Efetivo e diárias salvos.")
            return redirect("planos_trabalho:wizard_efetivo_diarias", pk=plano.pk)
    return render(
        request,
        "planos_trabalho/wizard_efetivo_diarias.html",
        _efetivo_diarias_context(formset=formset, diarias_form=diarias_form, plano=plano, request=request),
    )


@require_POST
def api_calcular_diarias(request, pk):
    """Cálculo ao vivo das diárias sem persistir (card de resultado da etapa 2)."""
    plano = _get_plano(pk)
    try:
        payload = json.loads(request.body or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "erros": ["Payload inválido."]}, status=400)

    data = _querydict_from_pairs(
        {
            "saida_sede_data": payload.get("saida_sede_data") or "",
            "saida_sede_hora": payload.get("saida_sede_hora") or "",
            "chegada_sede_data": payload.get("chegada_sede_data") or "",
            "chegada_sede_hora": payload.get("chegada_sede_hora") or "",
        }
    )
    form = PlanoDiariasForm(data, instance=plano)
    if not form.is_valid():
        return JsonResponse({"ok": False, "erros": _autosave_form_errors(form)}, status=200)

    # Aplica os valores no objeto em memória (sem save) e calcula.
    for campo, valor in form.cleaned_data.items():
        setattr(plano, campo, valor)

    total_efetivo = payload.get("total_efetivo")
    if total_efetivo is not None:
        try:
            total_efetivo = max(0, int(total_efetivo))
        except (TypeError, ValueError):
            total_efetivo = None

    # Modo multi-evento: se vier "eventos" no payload, calcula por evento + combinado.
    if plano.is_multi_evento:
        resultado_combinado = calcular_diarias_combinadas(plano)
        per_evento = []
        from .services import calcular_diarias_evento
        for evento in plano.eventos.order_by("ordem", "data_evento_inicio", "pk"):
            r = calcular_diarias_evento(plano, evento)
            per_evento.append(
                {
                    "evento_id": evento.pk,
                    "ordem": evento.ordem,
                    "ok": r["ok"],
                    "composicao": r.get("composicao", ""),
                    "valor_unitario_display": r.get("valor_unitario_display", ""),
                    "valor_total_display": r.get("valor_total_display", ""),
                    "valor_unitario_extenso": r.get("valor_unitario_extenso", ""),
                    "valor_total_extenso": r.get("valor_total_extenso", ""),
                    "quantidade_servidores": r.get("quantidade_servidores", 0),
                    "erros": r.get("erros", []),
                }
            )
        combinada = {
            "ok": resultado_combinado["ok"],
            "composicao": resultado_combinado.get("composicao", ""),
            "valor_unitario_display": resultado_combinado.get("valor_unitario_display", ""),
            "valor_total_display": resultado_combinado.get("valor_total_display", ""),
            "valor_unitario_extenso": resultado_combinado.get("valor_unitario_extenso", ""),
            "valor_total_extenso": resultado_combinado.get("valor_total_extenso", ""),
            "quantidade_servidores": resultado_combinado.get("quantidade_servidores", 0),
            "erros": resultado_combinado.get("erros", []),
        }
        # O card ao vivo compartilha o mesmo contrato nos modos simples e
        # multi. O detalhamento continua aninhado, mas o total combinado também
        # precisa estar no topo para os consumidores comuns da etapa 2.
        return JsonResponse(
            {
                **combinada,
                "modo": "multi",
                "per_evento": per_evento,
                "combinada": combinada,
            }
        )

    resultado = calcular_diarias_plano(plano, total_efetivo=total_efetivo)
    if not resultado["ok"]:
        return JsonResponse({"ok": False, "erros": resultado["erros"]})
    return JsonResponse(
        {
            "ok": True,
            "composicao": resultado["composicao"],
            "valor_unitario_display": resultado["valor_unitario_display"],
            "valor_total_display": resultado["valor_total_display"],
            "valor_unitario_extenso": resultado["valor_unitario_extenso"],
            "valor_total_extenso": resultado["valor_total_extenso"],
            "quantidade_servidores": resultado["quantidade_servidores"],
        }
    )


@require_POST
def evento_adicionar(request, pk):
    """Commita o rascunho atual como um evento e devolve à etapa 1 em branco.

    Chamado pelo botão "Adicionar evento ao plano" na etapa 4. No primeiro uso, o
    plano vira multi-evento. Se o rascunho estiver vazio, nada é criado.
    """
    plano = _get_plano(pk)
    evento = adicionar_evento_ao_plano(plano)
    if evento is None:
        messages.warning(request, "Preencha os dados do evento antes de adicioná-lo ao plano.")
        return redirect("planos_trabalho:wizard_documentos", pk=plano.pk)
    messages.success(
        request,
        f"Evento {evento.ordem} salvo. Preencha a etapa 1 para adicionar o próximo evento.",
    )
    return redirect("planos_trabalho:wizard_identificacao", pk=plano.pk)


@require_POST
def evento_editar(request, pk, evento_pk):
    """Carrega um evento commitado no rascunho para edição (salvando o rascunho atual)."""
    plano = _get_plano(pk)
    evento = get_evento_do_plano_by_id(plano, evento_pk)
    editar_evento_no_scratchpad(plano, evento)
    messages.success(request, f"Editando o evento {evento.ordem}.")
    return redirect("planos_trabalho:wizard_identificacao", pk=plano.pk)


@require_POST
def evento_remover(request, pk, evento_pk):
    plano = _get_plano(pk)
    evento = get_evento_do_plano_by_id(plano, evento_pk)
    remover_evento(plano, evento)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "is_multi_evento": plano.is_multi_evento})
    messages.success(request, "Evento removido do plano.")
    return redirect("planos_trabalho:wizard_identificacao", pk=plano.pk)


@require_POST
def efetivo_diarias_autosave(request, pk):
    plano = _get_plano(pk)
    try:
        payload = parse_autosave_payload(request, expected_model="plano_trabalho")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    # Campos planos da etapa 2 (saída/chegada na sede)
    allowed_fields = set(PlanoDiariasForm.Meta.fields)
    clean_fields = filter_allowed_fields(payload.fields, payload.dirty_fields, allowed_fields)
    diarias_form = None
    if clean_fields:
        data = _merge_payload_fields(_plano_diarias_autosave_data(plano), clean_fields)
        diarias_form = PlanoDiariasForm(data, instance=plano)
        if not diarias_form.is_valid():
            return autosave_json_response(
                ok=False,
                message="Alguns campos ainda precisam de ajuste antes do autosave.",
                errors=_autosave_form_errors(diarias_form),
            )

    # Snapshot do efetivo (formset inline)
    efetivo_snapshot = payload.snapshots.get("efetivo")
    resultado = salvar_efetivo_do_autosave(
        plano,
        rows=efetivo_snapshot if isinstance(efetivo_snapshot, list) else None,
        diarias_form=diarias_form,
    )

    snapshots_payload = {}
    if resultado.efetivo is not None:
        snapshots_payload["efetivo"] = resultado.efetivo

    now = timezone.localtime()
    return JsonResponse(
        {
            "ok": True,
            "object_id": plano.pk,
            "created": False,
            "saved_at": now.isoformat(),
            "saved_at_display": now.strftime("%d/%m/%Y %H:%M"),
            "version": _plano_autosave_version(plano),
            "snapshots": snapshots_payload,
        }
    )
