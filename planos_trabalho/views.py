from __future__ import annotations

import json

from django.contrib import messages
from django.http import Http404
from django.http import JsonResponse
from django.http import QueryDict
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST

from core.autosave import AutosavePayloadError
from core.autosave import autosave_json_response
from core.autosave import filter_allowed_fields
from core.autosave import parse_autosave_payload
from documentos.services.responses import build_inline_pdf_response_from_download_response
from documentos.services.timing import measure_step
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo

from .forms import EfetivoPlanoFormSet
from .forms import HorarioAtendimentoForm
from .forms import PlanoDiariasForm
from .forms import PlanoIdentificacaoForm
from .forms import ProgramaSolicitanteForm
from .models import PlanoTrabalho
from .models import HorarioAtendimento
from .models import ProgramaSolicitante
from .presenters import apresentar_plano_card
from .presenters import apresentar_plano_wizard_header
from .presenters import apresentar_plano_wizard_page_steps
from .presenters import apresentar_plano_wizard_steps
from .presenters import apresentar_plano_wizard_summary
from .services import aplicar_textos_padrao
from .services import atualizar_snapshot_diarias
from .services import avaliar_etapa_efetivo_diarias
from .services import avaliar_etapa_identificacao
from .services import avaliar_pendencias_documento
from .services import calcular_diarias_plano
from .services import criar_plano_rascunho
from .services import gerar_resposta_plano_documento
from .services import marcar_plano_gerado
from .services import montar_efetivo_texto
from .services import montar_texto_coordenacao
from .services import montar_valor_do_plano_texto


# ── Helpers do wizard (clone do shell de ofícios) ───────────────────────────


def _get_plano(pk) -> PlanoTrabalho:
    return get_object_or_404(
        PlanoTrabalho.objects.select_related(
            "programa",
            "destino_estado",
            "destino_cidade__estado",
            "coordenador_adm__cargo",
            "coordenador_op__cargo",
        ).prefetch_related("destinos__cidade", "destinos__estado"),
        pk=pk,
    )


def _wizard_normalizar_acao(post, *, default: str = "wizard_next") -> str:
    action = (post.get("action") or default).strip()
    if action == "save_continue":
        return "wizard_next"
    return action


def _wizard_steps_ctx(*, plano=None, etapa_atual="identificacao"):
    steps = apresentar_plano_wizard_steps(
        plano=plano,
        etapa_atual=etapa_atual,
        identificacao_status=avaliar_etapa_identificacao(plano) if plano else None,
        efetivo_diarias_status=avaliar_etapa_efetivo_diarias(plano) if plano else None,
        atividades_status="not_started",
        documentos_status="complete" if plano and plano.status == PlanoTrabalho.STATUS_GERADO else "not_started",
    )
    return {
        "wizard_steps": steps,
        "wizard_page_steps": apresentar_plano_wizard_page_steps(steps),
    }


def _wizard_shell_ctx(*, plano=None, etapa_atual):
    return {
        "wizard_header": apresentar_plano_wizard_header(etapa_atual, plano=plano),
        "wizard_summary": apresentar_plano_wizard_summary(plano) if plano else None,
        "plano": plano,
        "wizard_back_url": reverse("planos_trabalho:index"),
        "wizard_back_label": "Voltar à lista",
        **_wizard_steps_ctx(plano=plano, etapa_atual=etapa_atual),
    }


def _plano_autosave_version(plano: PlanoTrabalho) -> int:
    plano.refresh_from_db()
    return int(timezone.localtime(plano.updated_at).timestamp())


def _querydict_from_pairs(pairs):
    data = QueryDict(mutable=True)
    for name, value in pairs.items():
        if isinstance(value, (list, tuple, set)):
            data.setlist(name, [str(item) for item in value if item not in (None, "")])
        elif value is not None:
            data[name] = str(value)
    return data


def _merge_payload_fields(data, clean_fields):
    for name, value in clean_fields.items():
        if isinstance(value, list):
            data.setlist(name, [str(item) for item in value if item not in (None, "")])
        elif value is None:
            data[name] = ""
        else:
            data[name] = str(value)
    return data


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
        "consideracao_final": plano.consideracao_final or "",
        "coordenador_adm_modo": plano.coordenador_adm_modo or PlanoTrabalho.COORDENADOR_MODO_SERVIDOR,
        "coordenador_adm": plano.coordenador_adm_id or "",
        "coordenador_adm_nome_manual": plano.coordenador_adm_nome_manual or "",
        "coordenador_adm_cargo_manual": plano.coordenador_adm_cargo_manual or "",
        "coordenador_op_modo": plano.coordenador_op_modo or PlanoTrabalho.COORDENADOR_MODO_SERVIDOR,
        "coordenador_op": plano.coordenador_op_id or "",
        "coordenador_op_nome_manual": plano.coordenador_op_nome_manual or "",
        "coordenador_op_cargo_manual": plano.coordenador_op_cargo_manual or "",
    }
    destinos = list(plano.destinos.order_by("ordem", "pk"))
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


def _autosave_form_errors(*forms):
    errors = {}
    for form in forms:
        for field, messages_list in form.errors.items():
            errors[field] = [str(item) for item in messages_list]
    return errors


# ── Listagem ─────────────────────────────────────────────────────────────────


def index(request):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()

    planos = PlanoTrabalho.objects.select_related(
        "programa",
        "destino_cidade__estado",
        "coordenador_adm__cargo",
    ).order_by("-ano", "-numero", "-created_at")
    if status:
        planos = planos.filter(status=status)
    if q:
        from django.db.models import Q

        filtro = (
            Q(destino_cidade__nome__icontains=q)
            | Q(programa__nome__icontains=q)
            | Q(programa_outros__icontains=q)
            | Q(contextualizacao__icontains=q)
        )
        if q.isdigit():
            filtro = filtro | Q(numero=int(q)) | Q(ano=int(q))
        planos = planos.filter(filtro)

    cards = [apresentar_plano_card(plano) for plano in planos]
    return render(
        request,
        "planos_trabalho/index.html",
        {
            "page_title": "Planos de Trabalho",
            "page_description": "Cadastre e gerencie planos de trabalho com numeração própria.",
            "q": q,
            "status": status,
            "has_filters": bool(q or status),
            "cards": cards,
            "create_url": reverse("planos_trabalho:novo"),
            "search_clear_url": reverse("planos_trabalho:index"),
            "programas_url": reverse("planos_trabalho:programas_index"),
            "horarios_url": reverse("planos_trabalho:horarios_index"),
            "status_options": [{"value": "", "label": "Todos os status"}]
            + [{"value": v, "label": l} for v, l in PlanoTrabalho.STATUS_CHOICES],
            "empty_message": "Nenhum plano de trabalho encontrado.",
        },
    )


def novo(request):
    plano = criar_plano_rascunho()
    messages.success(request, f"Plano de Trabalho {plano.numero_formatado} criado como rascunho.")
    return redirect("planos_trabalho:wizard_identificacao", pk=plano.pk)


def editar(request, pk):
    plano = _get_plano(pk)
    return redirect("planos_trabalho:wizard_identificacao", pk=plano.pk)


# ── Etapa 1 — Identificação e atuação ───────────────────────────────────────


def _identificacao_context(*, form, plano):
    return {
        "page_title": "Plano de Trabalho",
        **_wizard_shell_ctx(plano=plano, etapa_atual="identificacao"),
        "form": form,
        "api_cidades_por_estado_url": reverse("roteiros:api_cidades_por_estado", kwargs={"estado_id": 0}),
        "evento_selected_dates_json": _evento_selected_dates_json(form),
        "evento_display": _evento_display_values(form),
        "servidor_create_url": reverse("cadastros:servidor_create"),
        "programas_url": reverse("planos_trabalho:programas_index"),
        "horarios_url": reverse("planos_trabalho:horarios_index"),
        "wizard_autosave_url": reverse("planos_trabalho:identificacao_autosave", args=[plano.pk]),
        "wizard_autosave_step": "identificacao",
        "coordenador_adm_modo_atual": plano.coordenador_adm_modo,
        "coordenador_op_modo_atual": plano.coordenador_op_modo,
    }


def wizard_identificacao(request, pk):
    plano = _get_plano(pk)
    form = PlanoIdentificacaoForm(request.POST or None, instance=plano)
    if request.method == "POST":
        nav_action = _wizard_normalizar_acao(request.POST)
        if form.is_valid():
            plano = form.save()
            campos_texto = aplicar_textos_padrao(plano)
            if campos_texto:
                plano.save(update_fields=[*campos_texto, "updated_at"])
            if plano.saida_sede_data and plano.chegada_sede_data:
                atualizar_snapshot_diarias(plano)
            if nav_action == "wizard_next":
                messages.success(request, "Identificação salva. Continue com o efetivo e as diárias.")
                return redirect("planos_trabalho:wizard_efetivo_diarias", pk=plano.pk)
            if nav_action == "save_draft_list":
                messages.success(request, "Plano salvo. Retornamos à lista.")
                return redirect("planos_trabalho:index")
            messages.success(request, "Identificação salva.")
            return redirect("planos_trabalho:wizard_identificacao", pk=plano.pk)
    return render(
        request,
        "planos_trabalho/wizard_identificacao.html",
        _identificacao_context(form=form, plano=plano),
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
    form.save()
    return autosave_json_response(ok=True, object_id=plano.pk, version=_plano_autosave_version(plano))


# ── Etapa 2 — Efetivo e diárias ──────────────────────────────────────────────


def _efetivo_diarias_context(*, formset, diarias_form, plano, resultado=None):
    resultado = resultado or calcular_diarias_plano(plano)
    return {
        "page_title": "Plano de Trabalho",
        **_wizard_shell_ctx(plano=plano, etapa_atual="efetivo_diarias"),
        "formset": formset,
        "diarias_form": diarias_form,
        "diarias_resultado": resultado,
        "cargo_create_url": reverse("cadastros:cargo_create"),
        "api_calcular_diarias_url": reverse("planos_trabalho:api_calcular_diarias", args=[plano.pk]),
    }


def wizard_efetivo_diarias(request, pk):
    plano = _get_plano(pk)
    formset = EfetivoPlanoFormSet(request.POST or None, instance=plano, prefix="efetivo")
    diarias_form = PlanoDiariasForm(request.POST or None, instance=plano)
    if request.method == "POST":
        nav_action = _wizard_normalizar_acao(request.POST)
        if formset.is_valid() and diarias_form.is_valid():
            formset.save()
            plano = diarias_form.save()
            resultado = atualizar_snapshot_diarias(plano)
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
                return redirect("planos_trabalho:index")
            messages.success(request, "Efetivo e diárias salvos.")
            return redirect("planos_trabalho:wizard_efetivo_diarias", pk=plano.pk)
    return render(
        request,
        "planos_trabalho/wizard_efetivo_diarias.html",
        _efetivo_diarias_context(formset=formset, diarias_form=diarias_form, plano=plano),
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


# ── Etapa 3 — Atividades, metas e recursos (placeholder) ─────────────────────


def wizard_atividades(request, pk):
    plano = _get_plano(pk)
    if request.method == "POST":
        nav_action = _wizard_normalizar_acao(request.POST)
        if nav_action == "wizard_back":
            return redirect("planos_trabalho:wizard_efetivo_diarias", pk=plano.pk)
        if nav_action == "save_draft_list":
            return redirect("planos_trabalho:index")
        return redirect("planos_trabalho:wizard_documentos", pk=plano.pk)
    return render(
        request,
        "planos_trabalho/wizard_atividades.html",
        {
            "page_title": "Plano de Trabalho",
            **_wizard_shell_ctx(plano=plano, etapa_atual="atividades"),
        },
    )


# ── Etapa 4 — Resumo e documentos ────────────────────────────────────────────


def wizard_documentos(request, pk):
    plano = _get_plano(pk)
    pendencias = avaliar_pendencias_documento(plano)

    if request.method == "POST":
        nav_action = _wizard_normalizar_acao(request.POST, default="save_draft")
        if nav_action == "finalizar":
            if pendencias:
                for msg in pendencias:
                    messages.error(request, msg)
                return redirect("planos_trabalho:wizard_documentos", pk=pk)
            marcar_plano_gerado(plano)
            messages.success(request, "Plano de trabalho finalizado com sucesso.")
            return redirect("planos_trabalho:index")
        if nav_action == "wizard_back":
            return redirect("planos_trabalho:wizard_atividades", pk=pk)
        if nav_action == "save_draft_list":
            messages.success(request, "Retornamos à lista de planos.")
            return redirect("planos_trabalho:index")
        return redirect("planos_trabalho:wizard_documentos", pk=pk)

    resumo_diarias = montar_valor_do_plano_texto(plano)
    return render(
        request,
        "planos_trabalho/wizard_documentos.html",
        {
            "page_title": "Plano de Trabalho",
            **_wizard_shell_ctx(plano=plano, etapa_atual="documentos"),
            "pendencias_documentos": pendencias,
            "mostrar_pendencias": bool(pendencias),
            "documento_disponivel": not pendencias,
            "pdf_inline_url": reverse("planos_trabalho:pdf_inline", args=[plano.pk]),
            "baixar_docx_url": reverse("planos_trabalho:baixar_documento", args=[plano.pk, "docx"]),
            "baixar_pdf_url": reverse("planos_trabalho:baixar_documento", args=[plano.pk, "pdf"]),
            "resumo": {
                "destino": plano.destino_display,
                "periodo": plano.periodo_display,
                "programa": plano.programa_display or "—",
                "horario": plano.horario_atendimento or "—",
                "efetivo": montar_efetivo_texto(plano) or "—",
                "valor_plano": resumo_diarias or "—",
                "coordenacao": montar_texto_coordenacao(plano) or "—",
            },
        },
    )


@require_GET
def pdf_inline(request, pk):
    plano = _get_plano(pk)
    pendencias = avaliar_pendencias_documento(plano)
    if pendencias:
        messages.error(request, "Documento não gerado porque o plano está incompleto.")
        return redirect(f"{reverse('planos_trabalho:wizard_documentos', args=[plano.pk])}?documento_incompleto=1")
    reference = f"{plano.numero:02d}-{plano.ano}" if plano.numero and plano.ano else f"plano-{plano.pk}"
    with measure_step("http_plano_trabalho_pdf_inline", {"plano_id": plano.pk}):
        try:
            resp = gerar_resposta_plano_documento(plano, DocumentoFormato.PDF)
        except Exception as exc:  # noqa: BLE001 — superfície amigável p/ erro de motor PDF
            messages.error(request, str(exc))
            return redirect("planos_trabalho:wizard_documentos", pk=plano.pk)
    return build_inline_pdf_response_from_download_response(
        request,
        resp,
        tipo=DocumentoTipo.PLANO_TRABALHO,
        reference=reference,
        now=timezone.now(),
    )


def baixar_documento(request, pk, formato):
    plano = _get_plano(pk)
    try:
        formato_documento = DocumentoFormato(formato)
    except ValueError as exc:
        raise Http404("Formato documental não suportado.") from exc

    pendencias = avaliar_pendencias_documento(plano)
    if pendencias:
        messages.error(request, "Documento não gerado porque o plano está incompleto.")
        return redirect(f"{reverse('planos_trabalho:wizard_documentos', args=[plano.pk])}?documento_incompleto=1")
    with measure_step(
        "http_baixar_plano_trabalho",
        {"plano_id": plano.pk, "formato": formato_documento.value},
    ):
        try:
            response = gerar_resposta_plano_documento(plano, formato_documento)
        except Exception as exc:  # noqa: BLE001
            if formato_documento == DocumentoFormato.PDF:
                messages.error(request, str(exc))
                return redirect("planos_trabalho:wizard_documentos", pk=plano.pk)
            raise
    marcar_plano_gerado(plano)
    return response


def excluir(request, pk):
    plano = _get_plano(pk)
    if request.method == "POST":
        numero = plano.numero_formatado
        plano.delete()
        messages.success(request, f"Plano de Trabalho {numero} excluído.")
        return redirect("planos_trabalho:index")
    return render(
        request,
        "planos_trabalho/confirm_delete.html",
        {
            "page_title": "Excluir plano de trabalho",
            "plano": plano,
            "cancel_url": reverse("planos_trabalho:index"),
        },
    )


# ── Programas solicitantes (clone do CRUD de modelos de motivo) ──────────────


def programas_index(request):
    programas = ProgramaSolicitante.objects.order_by("ordem", "nome")
    linhas = [
        {
            "title": programa.nome,
            "badges": [],
            "meta": [
                {"label": "Status", "value": "Ativo" if programa.ativo else "Inativo"},
                {"label": "Ordem", "value": str(programa.ordem)},
            ],
            "edit_url": reverse("planos_trabalho:programa_editar", args=[programa.pk]),
            "delete_url": reverse("planos_trabalho:programa_excluir", args=[programa.pk]),
        }
        for programa in programas
    ]
    return render(
        request,
        "planos_trabalho/programas/index.html",
        {
            "page_title": "Programas solicitantes",
            "page_description": "Programas exibidos na etapa de identificação do plano de trabalho.",
            "linhas": linhas,
            "create_url": reverse("planos_trabalho:programa_novo"),
            "back_url": reverse("planos_trabalho:index"),
        },
    )


def programa_novo(request):
    form = ProgramaSolicitanteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Programa cadastrado.")
        return redirect("planos_trabalho:programas_index")
    return render(
        request,
        "planos_trabalho/programas/form.html",
        {
            "page_title": "Novo programa solicitante",
            "form": form,
            "back_url": reverse("planos_trabalho:programas_index"),
        },
    )


def programa_editar(request, pk):
    programa = get_object_or_404(ProgramaSolicitante, pk=pk)
    form = ProgramaSolicitanteForm(request.POST or None, instance=programa)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Programa atualizado.")
        return redirect("planos_trabalho:programas_index")
    return render(
        request,
        "planos_trabalho/programas/form.html",
        {
            "page_title": f"Editar programa — {programa.nome}",
            "form": form,
            "programa": programa,
            "back_url": reverse("planos_trabalho:programas_index"),
        },
    )


def programa_excluir(request, pk):
    programa = get_object_or_404(ProgramaSolicitante, pk=pk)
    if request.method == "POST":
        nome = programa.nome
        programa.delete()
        messages.success(request, f"Programa “{nome}” excluído.")
        return redirect("planos_trabalho:programas_index")
    return render(
        request,
        "planos_trabalho/programas/confirm_delete.html",
        {
            "page_title": "Excluir programa",
            "programa": programa,
            "cancel_url": reverse("planos_trabalho:programas_index"),
        },
    )


def horarios_index(request):
    horarios = HorarioAtendimento.objects.order_by("ordem", "faixa")
    linhas = [
        {
            "title": horario.faixa,
            "meta": [
                {"label": "Status", "value": "Ativo" if horario.ativo else "Inativo"},
                {"label": "Ordem", "value": str(horario.ordem)},
            ],
            "edit_url": reverse("planos_trabalho:horario_editar", args=[horario.pk]),
            "delete_url": reverse("planos_trabalho:horario_excluir", args=[horario.pk]),
        }
        for horario in horarios
    ]
    return render(
        request,
        "planos_trabalho/horarios/index.html",
        {
            "page_title": "Horários de atendimento",
            "page_description": "Horários exibidos no select da etapa de identificação do plano de trabalho.",
            "linhas": linhas,
            "q": "",
            "create_url": reverse("planos_trabalho:horario_novo"),
        },
    )


def horario_novo(request):
    form = HorarioAtendimentoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Horário cadastrado.")
        return redirect("planos_trabalho:horarios_index")
    return render(
        request,
        "planos_trabalho/horarios/form.html",
        {
            "page_title": "Novo horário de atendimento",
            "page_description": "Faixa exibida no select da etapa de identificação do plano.",
            "form": form,
            "back_url": reverse("planos_trabalho:horarios_index"),
        },
    )


def horario_editar(request, pk):
    horario = get_object_or_404(HorarioAtendimento, pk=pk)
    form = HorarioAtendimentoForm(request.POST or None, instance=horario)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Horário atualizado.")
        return redirect("planos_trabalho:horarios_index")
    return render(
        request,
        "planos_trabalho/horarios/form.html",
        {
            "page_title": f"Editar horário — {horario.faixa}",
            "page_description": "Atualize a faixa exibida no select da etapa de identificação do plano.",
            "form": form,
            "horario": horario,
            "back_url": reverse("planos_trabalho:horarios_index"),
        },
    )


def horario_excluir(request, pk):
    horario = get_object_or_404(HorarioAtendimento, pk=pk)
    if request.method == "POST":
        faixa = horario.faixa
        horario.delete()
        messages.success(request, f"Horário “{faixa}” excluído.")
        return redirect("planos_trabalho:horarios_index")
    return render(
        request,
        "planos_trabalho/horarios/confirm_delete.html",
        {
            "page_title": "Excluir horário",
            "page_description": "Confirma a exclusão do horário de atendimento.",
            "horario": horario,
            "cancel_url": reverse("planos_trabalho:horarios_index"),
        },
    )
