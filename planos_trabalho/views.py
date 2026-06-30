from __future__ import annotations

import json

from django.contrib import messages
from django.db.models import Max
from django.http import Http404
from django.http import JsonResponse
from django.http import QueryDict
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST

from urllib.parse import urlencode

from django.utils.http import url_has_allowed_host_and_scheme

from core.autosave import AutosavePayloadError
from core.presenters.badges import build_badge
from core.presenters.meta import build_meta
from core.autosave import autosave_json_response
from core.autosave import filter_allowed_fields
from core.autosave import parse_autosave_payload
from documentos.services.responses import build_inline_pdf_response_from_download_response
from documentos.services.timing import measure_step
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo
from eventos.services import resolve_evento_from_request

from .forms import AtividadePlanoTrabalhoForm
from .forms import AtividadePlanoTrabalhoQuickAddForm
from .forms import EfetivoPlanoFormSet
from .forms import HorarioAtendimentoForm
from .forms import PlanoDiariasForm
from .forms import PlanoIdentificacaoForm
from .forms import ProgramaSolicitanteForm
from .models import AtividadePlanoTrabalho
from .models import EventoPlano
from .models import PlanoTrabalho
from .models import HorarioAtendimento
from .models import ProgramaSolicitante
from .presenters import apresentar_plano_card
from .presenters import apresentar_resumo_documentos
from .presenters import apresentar_resumo_evento_card
from .presenters import apresentar_resumo_header
from .presenters import apresentar_plano_wizard_header
from .presenters import apresentar_plano_wizard_page_steps
from .presenters import apresentar_plano_wizard_steps
from .presenters import apresentar_plano_wizard_summary
from .services import atividades_catalogo_ativas
from .services import atualizar_snapshot_diarias
from .services import atualizar_snapshot_diarias_combinadas
from .services import calcular_diarias_combinadas
from .services import avaliar_etapa_atividades
from .services import avaliar_etapa_efetivo_diarias
from .services import avaliar_etapa_identificacao
from .services import avaliar_pendencias_documento
from .services import calcular_diarias_plano
from .services import criar_plano_rascunho
from .services import gerar_resposta_plano_documento
from .services import marcar_plano_gerado
from .services import montar_efetivo_texto
from .services import adicionar_evento_ao_plano
from .services import editar_evento_no_scratchpad
from .services import eventos_para_cards
from .services import remover_evento
from .services import sincronizar_scratchpad
from .services import sincronizar_atividades
from .services import montar_texto_coordenacao
from .services import montar_valor_do_plano_texto
from .services import sincronizar_textos_padrao
from .services import texto_padrao_consideracao_final
from .services import texto_padrao_coordenacao
from .services import texto_padrao_contextualizacao
from .services import textos_padrao_templates


# ── Helpers do wizard (clone do shell de ofícios) ───────────────────────────


def _get_plano(pk) -> PlanoTrabalho:
    return get_object_or_404(
        PlanoTrabalho.objects.select_related(
            "evento",
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


def _evento_etapa_url(evento_id):
    if evento_id:
        return reverse("eventos:guiado_etapa", kwargs={"pk": evento_id, "etapa": 4})
    return ""


def _plano_lista_url(plano=None):
    return _evento_etapa_url(getattr(plano, "evento_id", None)) or reverse("planos_trabalho:index")


def _plano_lista_label(plano=None):
    return "Dados do evento" if getattr(plano, "evento_id", None) else "Voltar a lista"


def _redirect_plano_lista(plano):
    if getattr(plano, "evento_id", None):
        return redirect("eventos:guiado_etapa", pk=plano.evento_id, etapa=4)
    return redirect("planos_trabalho:index")


def _wizard_steps_ctx(*, plano=None, etapa_atual="identificacao"):
    steps = apresentar_plano_wizard_steps(
        plano=plano,
        etapa_atual=etapa_atual,
        identificacao_status=avaliar_etapa_identificacao(plano) if plano else None,
        efetivo_diarias_status=avaliar_etapa_efetivo_diarias(plano) if plano else None,
        atividades_status=avaliar_etapa_atividades(plano) if plano else None,
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
        "wizard_back_url": _plano_lista_url(plano),
        "wizard_back_label": _plano_lista_label(plano),
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
    temporal = request.GET.get("temporal", "").strip()
    viagem_de = request.GET.get("viagem_de", "").strip()
    viagem_ate = request.GET.get("viagem_ate", "").strip()
    sort = request.GET.get("sort", "").strip()

    planos = PlanoTrabalho.objects.select_related(
        "programa",
        "destino_cidade__estado",
        "coordenador_adm__cargo",
    )
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

    hoje = timezone.localdate()
    if temporal == "futuro":
        planos = planos.filter(data_evento_inicio__gt=hoje)
    elif temporal == "andamento":
        planos = planos.filter(data_evento_inicio__lte=hoje, data_evento_fim__gte=hoje)
    elif temporal == "passado":
        planos = planos.filter(data_evento_fim__lt=hoje)

    viagem_de_date = parse_date(viagem_de) if viagem_de else None
    viagem_ate_date = parse_date(viagem_ate) if viagem_ate else None
    if viagem_de_date:
        planos = planos.filter(data_evento_fim__gte=viagem_de_date)
    if viagem_ate_date:
        planos = planos.filter(data_evento_inicio__lte=viagem_ate_date)

    sort_map = {
        "numero_desc": ("-ano", "-numero", "-created_at"),
        "numero_asc": ("ano", "numero", "created_at"),
        "criacao_desc": ("-created_at",),
        "criacao_asc": ("created_at",),
        "viagem_asc": ("data_evento_inicio", "-ano", "-numero"),
        "viagem_desc": ("-data_evento_inicio", "-ano", "-numero"),
    }
    planos = planos.order_by(*sort_map.get(sort or "numero_desc", sort_map["numero_desc"]))

    cards = [apresentar_plano_card(plano) for plano in planos]
    has_filters = any([q, status, temporal, viagem_de, viagem_ate, sort])
    return render(
        request,
        "planos_trabalho/index.html",
        {
            "page_title": "Planos de Trabalho",
            "page_description": "Cadastre e gerencie planos de trabalho com numeração própria.",
            "q": q,
            "status": status,
            "temporal": temporal,
            "viagem_de": viagem_de,
            "viagem_ate": viagem_ate,
            "sort": sort,
            "has_filters": has_filters,
            "cards": cards,
            "create_url": reverse("planos_trabalho:novo"),
            "search_clear_url": reverse("planos_trabalho:index"),
            "programas_url": reverse("planos_trabalho:programas_index"),
            "horarios_url": reverse("planos_trabalho:horarios_index"),
            "status_options": [{"value": "", "label": "Todos os status"}]
            + [{"value": v, "label": l} for v, l in PlanoTrabalho.STATUS_CHOICES],
            "temporal_options": [
                {"value": "", "label": "Qualquer período"},
                {"value": "futuro", "label": "Futuras"},
                {"value": "andamento", "label": "Em andamento"},
                {"value": "passado", "label": "Passadas"},
            ],
            "sort_options": [
                {"value": "numero_desc", "label": "Número: maior"},
                {"value": "numero_asc", "label": "Número: menor"},
                {"value": "criacao_desc", "label": "Criação: mais recente"},
                {"value": "criacao_asc", "label": "Criação: mais antiga"},
                {"value": "viagem_asc", "label": "Viagem: mais próxima"},
                {"value": "viagem_desc", "label": "Viagem: mais distante"},
            ],
            "empty_message": "Nenhum plano de trabalho encontrado.",
        },
    )

def novo(request):
    evento = resolve_evento_from_request(request)
    plano = criar_plano_rascunho(evento=evento)
    messages.success(request, f"Plano de Trabalho {plano.numero_formatado} criado como rascunho.")
    return redirect("planos_trabalho:wizard_identificacao", pk=plano.pk)


def editar(request, pk):
    plano = _get_plano(pk)
    return redirect("planos_trabalho:wizard_identificacao", pk=plano.pk)


# ── Etapa 1 — Identificação e atuação ───────────────────────────────────────


def _texto_auto_flag(form, plano, post_name, attr):
    if form.is_bound:
        return (form.data.get(post_name, "1") or "0").strip() != "0"
    return getattr(plano, attr)


def _identificacao_context(*, form, plano):
    eventos_commitados = eventos_para_cards(plano)
    eventos_resumo = [apresentar_resumo_evento_card(e) for e in eventos_commitados]
    return {
        "page_title": "Plano de Trabalho",
        **_wizard_shell_ctx(plano=plano, etapa_atual="identificacao"),
        "form": form,
        "api_cidades_por_estado_url": reverse("roteiros:api_cidades_por_estado", kwargs={"estado_id": 0}),
        "evento_selected_dates_json": _evento_selected_dates_json(form),
        "evento_display": _evento_display_values(form),
        "cargos_url": reverse("cadastros:cargos_index"),
        "programas_url": reverse("planos_trabalho:programas_index"),
        "horarios_url": reverse("planos_trabalho:horarios_index"),
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
        nav_action = _wizard_normalizar_acao(request.POST)
        if form.is_valid():
            plano = form.save()
            plano.contextualizacao_auto = (request.POST.get("contextualizacao_auto", "1") or "0").strip() != "0"
            plano.coordenacao_auto = (request.POST.get("coordenacao_auto", "1") or "0").strip() != "0"
            plano.consideracao_auto = (request.POST.get("consideracao_auto", "1") or "0").strip() != "0"
            campos_texto = sincronizar_textos_padrao(plano)
            plano.save(
                update_fields=[
                    *{*campos_texto, "contextualizacao_auto", "coordenacao_auto", "consideracao_auto"},
                    "updated_at",
                ],
            )
            if plano.saida_sede_data and plano.chegada_sede_data:
                atualizar_snapshot_diarias(plano)
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
    plano = form.save()
    # Edição direta do texto desliga o modo automático; mudança de destino/programa
    # mantém o texto padrão sincronizado quando ainda estiver no modo automático.
    flag_updates: list[str] = []
    if "contextualizacao" in clean_fields:
        plano.contextualizacao_auto = False
        flag_updates.append("contextualizacao_auto")
    if "coordenacao" in clean_fields:
        plano.coordenacao_auto = False
        flag_updates.append("coordenacao_auto")
    if "consideracao_final" in clean_fields:
        plano.consideracao_auto = False
        flag_updates.append("consideracao_auto")
    campos_texto = sincronizar_textos_padrao(plano)
    if campos_texto or flag_updates:
        plano.save(update_fields=[*{*campos_texto, *flag_updates}, "updated_at"])
    return autosave_json_response(ok=True, object_id=plano.pk, version=_plano_autosave_version(plano))


# ── Etapa 2 — Efetivo e diárias ──────────────────────────────────────────────


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


def _efetivo_diarias_context(*, formset, diarias_form, plano, resultado=None):
    resultado = resultado or calcular_diarias_plano(plano)
    return {
        "page_title": "Plano de Trabalho",
        **_wizard_shell_ctx(plano=plano, etapa_atual="efetivo_diarias"),
        "formset": formset,
        "diarias_form": diarias_form,
        "diarias_display": _diarias_display_values(diarias_form),
        "diarias_selected_dates_json": _diarias_selected_dates_json(diarias_form),
        "diarias_resultado": resultado,
        "cargos_url": reverse("cadastros:cargos_index"),
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
    """Converte o formset inline de efetivo em linhas para `_apply_efetivo_snapshot`.

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


def _apply_efetivo_snapshot(plano: PlanoTrabalho, rows):
    """Reconcilia o efetivo do plano com o snapshot recebido do autosave.

    Linhas com `cargo` e `quantidade` válidos são criadas/atualizadas; linhas
    incompletas são ignoradas (placeholders no formulário). IDs ausentes no
    snapshot são removidos do banco para refletir o estado atual da tela.
    """
    from cadastros.models import Cargo, Unidade  # import lazy para evitar ciclos

    existentes = {efetivo.pk: efetivo for efetivo in plano.efetivos.all()}
    mantidos: set[int] = set()
    saida: list[dict] = []
    vistos: set[tuple] = set()

    for index, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        cargo_id = _to_int_or_none(row.get("cargo"))
        quantidade = _to_int_or_none(row.get("quantidade"))
        unidade_id = _to_int_or_none(row.get("unidade"))
        client_idx = _to_int_or_none(row.get("idx"))
        if client_idx is None:
            client_idx = index
        if not cargo_id or not quantidade or quantidade <= 0:
            continue
        if not Cargo.objects.filter(pk=cargo_id).exists():
            continue
        if unidade_id and not Unidade.objects.filter(pk=unidade_id).exists():
            unidade_id = None
        chave = (unidade_id, cargo_id)
        if chave in vistos:
            continue
        vistos.add(chave)
        row_id = _to_int_or_none(row.get("id"))
        if row_id and row_id in existentes:
            efetivo = existentes[row_id]
            efetivo.unidade_id = unidade_id
            efetivo.cargo_id = cargo_id
            efetivo.quantidade = quantidade
            efetivo.save(update_fields=["unidade", "cargo", "quantidade", "updated_at"])
            mantidos.add(row_id)
        else:
            efetivo = plano.efetivos.create(unidade_id=unidade_id, cargo_id=cargo_id, quantidade=quantidade)
            mantidos.add(efetivo.pk)
        saida.append({"idx": client_idx, "id": efetivo.pk})

    remover = [pk for pk in existentes if pk not in mantidos]
    if remover:
        plano.efetivos.filter(pk__in=remover).delete()
    return saida


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
        nav_action = _wizard_normalizar_acao(request.POST)
        if formset.is_valid() and diarias_form.is_valid():
            # Reconcilia por id (e não via management form), pois o autosave pode
            # ter criado efetivos após o carregamento da página — o que deixaria
            # INITIAL_FORMS defasado e faria o formset.save() inserir duplicatas.
            _apply_efetivo_snapshot(plano, _efetivo_rows_from_formset(formset))
            plano = diarias_form.save()
            resultado = atualizar_snapshot_diarias(plano)
            if plano.is_multi_evento:
                atualizar_snapshot_diarias_combinadas(plano)
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
        return JsonResponse(
            {
                "ok": resultado_combinado["ok"],
                "modo": "multi",
                "per_evento": per_evento,
                "combinada": {
                    "ok": resultado_combinado["ok"],
                    "composicao": resultado_combinado.get("composicao", ""),
                    "valor_unitario_display": resultado_combinado.get("valor_unitario_display", ""),
                    "valor_total_display": resultado_combinado.get("valor_total_display", ""),
                    "valor_unitario_extenso": resultado_combinado.get("valor_unitario_extenso", ""),
                    "valor_total_extenso": resultado_combinado.get("valor_total_extenso", ""),
                    "quantidade_servidores": resultado_combinado.get("quantidade_servidores", 0),
                    "erros": resultado_combinado.get("erros", []),
                },
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
    evento = get_object_or_404(EventoPlano, pk=evento_pk, plano=plano)
    editar_evento_no_scratchpad(plano, evento)
    messages.success(request, f"Editando o evento {evento.ordem}.")
    return redirect("planos_trabalho:wizard_identificacao", pk=plano.pk)


@require_POST
def evento_remover(request, pk, evento_pk):
    plano = _get_plano(pk)
    evento = get_object_or_404(EventoPlano, pk=evento_pk, plano=plano)
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
    if clean_fields:
        data = _merge_payload_fields(_plano_diarias_autosave_data(plano), clean_fields)
        diarias_form = PlanoDiariasForm(data, instance=plano)
        if not diarias_form.is_valid():
            return autosave_json_response(
                ok=False,
                message="Alguns campos ainda precisam de ajuste antes do autosave.",
                errors=_autosave_form_errors(diarias_form),
            )
        plano = diarias_form.save()

    # Snapshot do efetivo (formset inline)
    efetivo_result = None
    efetivo_snapshot = payload.snapshots.get("efetivo")
    if isinstance(efetivo_snapshot, list):
        efetivo_result = _apply_efetivo_snapshot(plano, efetivo_snapshot)

    if plano.saida_sede_data and plano.chegada_sede_data:
        # Sempre atualiza a diária do rascunho (evento atual); em multi, também a combinada.
        atualizar_snapshot_diarias(plano)
        if plano.is_multi_evento:
            atualizar_snapshot_diarias_combinadas(plano)

    snapshots_payload = {}
    if efetivo_result is not None:
        snapshots_payload["efetivo"] = efetivo_result

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


# ── Etapa 3 — Atividades, metas e recursos ───────────────────────────────────


def _atividades_context(*, plano, catalogo, selected_codes):
    """Monta catálogo (com flag de seleção), JSON p/ o preview ao vivo e listas iniciais."""
    catalogo_view = [
        {
            "codigo": item.codigo,
            "nome": item.nome,
            "meta": item.meta,
            "recurso_necessario": item.recurso_necessario,
            "selected": item.codigo in selected_codes,
        }
        for item in catalogo
    ]
    catalogo_data = [
        {
            "codigo": item.codigo,
            "nome": item.nome,
            "meta": item.meta,
            "recurso": item.recurso_necessario,
        }
        for item in catalogo
    ]
    selecionados = [item for item in catalogo if item.codigo in selected_codes]
    metas_preview = []
    vistas = set()
    for item in selecionados:
        meta = (item.meta or "").strip()
        if meta and meta not in vistas:
            vistas.add(meta)
            metas_preview.append(meta)
    recursos_preview = []
    vistos = set()
    for item in selecionados:
        recurso = (item.recurso_necessario or "").strip()
        if recurso and recurso not in vistos:
            vistos.add(recurso)
            recursos_preview.append(recurso)
    return {
        "page_title": "Plano de Trabalho",
        **_wizard_shell_ctx(plano=plano, etapa_atual="atividades"),
        "atividades_catalogo": catalogo_view,
        "atividades_catalogo_data": catalogo_data,
        "atividades_selecionadas_total": len(selecionados),
        "atividades_counter_label": f"{len(selecionados)} selecionadas",
        "metas_preview": metas_preview,
        "recursos_preview": recursos_preview,
        "atividades_manager_url": (
            reverse("planos_trabalho:atividades_index")
            + "?"
            + urlencode({"next": reverse("planos_trabalho:wizard_atividades", args=[plano.pk])})
        ),
        "wizard_autosave_url": reverse("planos_trabalho:atividades_autosave", args=[plano.pk]),
        "wizard_autosave_step": "atividades",
    }


@require_POST
def atividades_autosave(request, pk):
    plano = _get_plano(pk)
    try:
        payload = parse_autosave_payload(request, expected_model="plano_trabalho")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    snapshot = payload.snapshots.get("atividades")
    if isinstance(snapshot, dict):
        raw_codigos = snapshot.get("codigos") or []
        if not isinstance(raw_codigos, list):
            return autosave_json_response(ok=False, message="Códigos inválidos no autosave.")
        codigos = [str(item).strip() for item in raw_codigos if str(item).strip()]
        catalogo = atividades_catalogo_ativas()
        selecionadas = [item for item in catalogo if item.codigo in codigos]
        plano.atividades_selecionadas.set(selecionadas)
        sincronizar_atividades(plano)

    return autosave_json_response(ok=True, object_id=plano.pk, version=_plano_autosave_version(plano))


def wizard_atividades(request, pk):
    plano = _get_plano(pk)
    catalogo = atividades_catalogo_ativas()
    if request.method == "POST":
        nav_action = _wizard_normalizar_acao(request.POST)
        codigos = request.POST.getlist("atividades_codigos")
        selecionadas = [item for item in catalogo if item.codigo in codigos]
        plano.atividades_selecionadas.set(selecionadas)
        sincronizar_atividades(plano)
        if nav_action == "wizard_back":
            messages.success(request, "Atividades salvas.")
            return redirect("planos_trabalho:wizard_efetivo_diarias", pk=plano.pk)
        if nav_action == "save_draft_list":
            messages.success(request, "Plano salvo. Retornamos à lista.")
            return _redirect_plano_lista(plano)
        if nav_action == "wizard_next":
            messages.success(request, "Atividades salvas. Continue com o resumo e os documentos.")
            return redirect("planos_trabalho:wizard_documentos", pk=plano.pk)
        messages.success(request, "Atividades salvas.")
        return redirect("planos_trabalho:wizard_atividades", pk=plano.pk)

    selected_codes = set(plano.atividades_selecionadas.values_list("codigo", flat=True))
    return render(
        request,
        "planos_trabalho/wizard_atividades.html",
        _atividades_context(plano=plano, catalogo=catalogo, selected_codes=selected_codes),
    )


# ── Catálogo de atividades (clone do CRUD de programas) ──────────────────────


def _truncar(texto: str, limite: int = 90) -> str:
    texto = (texto or "").strip()
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def _atividades_back_url(request):
    """URL de retorno do gerenciador: etapa 3 do plano (via ?next=) ou a lista."""
    candidato = request.POST.get("next") or request.GET.get("next") or ""
    if candidato and url_has_allowed_host_and_scheme(candidato, allowed_hosts={request.get_host()}):
        return candidato
    return reverse("planos_trabalho:index")


def _atividade_quick_add_field_values(atividade):
    return json.dumps(
        {
            "nome": atividade.nome,
            "recurso_necessario": atividade.recurso_necessario,
            "meta": atividade.meta,
        },
        ensure_ascii=False,
    )


def atividades_index(request):
    from django.db.models import Q

    q = request.GET.get("q", "").strip()
    back_url = _atividades_back_url(request)
    form = AtividadePlanoTrabalhoQuickAddForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Atividade cadastrada.")
        return redirect(_atividades_index_url(back_url))

    atividades = AtividadePlanoTrabalho.objects.order_by("ordem", "nome")
    if q:
        atividades = atividades.filter(
            Q(nome__icontains=q) | Q(codigo__icontains=q) | Q(meta__icontains=q)
        )
    linhas = [
        {
            "title": atividade.nome,
            "badges": [build_badge("Inativa", "neutral")] if not atividade.ativo else [],
            "meta": [
                build_meta("Recurso", _truncar(atividade.recurso_necessario) or "—"),
                build_meta("Meta", _truncar(atividade.meta)),
            ],
            "edit_url": _atividades_index_url(back_url, base=reverse("planos_trabalho:atividade_editar", args=[atividade.pk])),
            "edit_fields_json": _atividade_quick_add_field_values(atividade),
            "delete_url": reverse("planos_trabalho:atividade_excluir", args=[atividade.pk]),
            "delete_modal": True,
        }
        for atividade in atividades
    ]
    is_wizard_back = back_url != reverse("planos_trabalho:index")
    return render(
        request,
        "planos_trabalho/atividades/index.html",
        {
            "page_title": "Gerenciamento de atividades",
            "page_description": "Cadastre, edite e organize atividades com metas e recursos.",
            "q": q,
            "linhas": linhas,
            "quick_add_form": form,
            "quick_add_next_url": back_url if is_wizard_back else "",
            "back_url": back_url,
            "back_label": "Voltar pra plano de trabalho" if is_wizard_back else "Voltar",
        },
    )


def _atividades_index_url(back_url, base=None):
    """URL do gerenciador (ou de uma ação) preservando o retorno à etapa 3."""
    base = base or reverse("planos_trabalho:atividades_index")
    if back_url and back_url != reverse("planos_trabalho:index"):
        return f"{base}?{urlencode({'next': back_url})}"
    return base


def atividade_novo(request):
    form = AtividadePlanoTrabalhoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Atividade cadastrada.")
        return redirect("planos_trabalho:atividades_index")
    return render(
        request,
        "planos_trabalho/atividades/form.html",
        {
            "page_title": "Nova atividade",
            "page_description": "Ao adicionar uma atividade, o preenchimento de meta é obrigatório.",
            "form": form,
            "back_url": reverse("planos_trabalho:atividades_index"),
        },
    )


def atividade_editar(request, pk):
    """Edição inline via quick add: processa o POST do painel e volta ao gerenciador."""
    atividade = get_object_or_404(AtividadePlanoTrabalho, pk=pk)
    back_url = _atividades_back_url(request)
    if request.method == "POST":
        form = AtividadePlanoTrabalhoQuickAddForm(request.POST, instance=atividade)
        if form.is_valid():
            form.save()
            messages.success(request, "Atividade atualizada.")
        else:
            for erros in form.errors.values():
                for erro in erros:
                    messages.error(request, erro)
    return redirect(_atividades_index_url(back_url))


def atividade_excluir(request, pk):
    atividade = get_object_or_404(AtividadePlanoTrabalho, pk=pk)
    if request.method == "POST":
        nome = atividade.nome
        atividade.delete()
        messages.success(request, f"Atividade “{nome}” excluída.")
        return redirect("planos_trabalho:atividades_index")
    return render(
        request,
        "planos_trabalho/atividades/confirm_delete.html",
        {
            "page_title": "Excluir atividade",
            "atividade": atividade,
            "cancel_url": reverse("planos_trabalho:atividades_index"),
        },
    )


# ── Etapa 4 — Resumo e documentos ────────────────────────────────────────────


def wizard_documentos(request, pk):
    plano = _get_plano(pk)
    # Em multi-evento, garante que o rascunho atual esteja refletido como evento
    # antes de avaliar pendências e gerar o documento (sem limpar o rascunho).
    sincronizar_scratchpad(plano)
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
            return _redirect_plano_lista(plano)
        if nav_action == "wizard_back":
            return redirect("planos_trabalho:wizard_atividades", pk=pk)
        if nav_action == "save_draft_list":
            messages.success(request, "Retornamos à lista de planos.")
            return _redirect_plano_lista(plano)
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
            "is_multi_evento": plano.is_multi_evento,
            "evento_adicionar_url": reverse("planos_trabalho:evento_adicionar", args=[plano.pk]),
            "pdf_inline_url": reverse("planos_trabalho:pdf_inline", args=[plano.pk]),
            "baixar_docx_url": reverse("planos_trabalho:baixar_documento", args=[plano.pk, "docx"]),
            "baixar_pdf_url": reverse("planos_trabalho:baixar_documento", args=[plano.pk, "pdf"]),
            "resumo_documentos": apresentar_resumo_documentos(plano),
            "resumo": {
                "destino": plano.destino_display,
                "periodo": plano.periodo_display,
                "programa": plano.programa_display or "—",
                "horario": plano.horario_atendimento or "—",
                "efetivo": montar_efetivo_texto(plano) or "—",
                "valor_plano": resumo_diarias or "—",
                "coordenacao": (
                    (plano.coordenacao or "").strip()
                    or (montar_texto_coordenacao(plano) if plano.coordenacao_auto else "")
                    or "—"
                ),
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
        evento_id = plano.evento_id
        plano.delete()
        messages.success(request, f"Plano de Trabalho {numero} excluído.")
        if evento_id:
            return redirect("eventos:guiado_etapa", pk=evento_id, etapa=4)
        return redirect("planos_trabalho:index")
    return render(
        request,
        "planos_trabalho/confirm_delete.html",
        {
            "page_title": "Excluir plano de trabalho",
            "plano": plano,
            "cancel_url": _plano_lista_url(plano),
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
