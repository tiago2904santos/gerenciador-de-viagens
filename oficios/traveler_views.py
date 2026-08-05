import logging
from django.contrib import messages
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST
from core.autosave import AutosavePayloadError
from core.autosave import autosave_json_response
from core.autosave import filter_allowed_fields
from core.autosave import parse_autosave_payload
from .forms import OficioDadosViajantesForm
from .forms import OficioTransporteForm
from .models import Oficio
from .presenters import apresentar_oficio_wizard_summary
from .selectors import get_oficio_by_id
from .services import atualizar_oficio_dados_viajantes
from .services import atualizar_oficio_transporte
from .services import avaliar_oficio_dados_viajantes
from .services import avaliar_oficio_transporte
from .services import OficioNumeroConflitoError
from .view_navigation import cadastro_create_url as _cadastro_create_url
from .view_navigation import oficio_back_label as _oficio_back_label
from .view_navigation import oficio_back_url as _oficio_back_url
from .view_navigation import url_with_next as _url_with_next
from core.wizard import normalizar_acao_do_wizard

from .view_helpers import _redirect_lista_oficio, _wizard_persist_action_para_dados_viajantes, _wizard_footer_ctx, _wizard_shell_ctx, _motorista_oficio_numero_display, _prepare_dados_viajantes_form, _prepare_transporte_form, _merge_payload_fields, _oficio_dados_viajantes_autosave_data, _oficio_transporte_autosave_data, _oficio_autosave_version, _autosave_form_errors


def _wizard_dados_viajantes_context(
    *,
    form,
    transporte_form,
    oficio,
    avaliacao=None,
    mostrar_pendencias_documento=False,
):
    avaliacao = avaliacao or avaliar_oficio_dados_viajantes(oficio=oficio, form=form)
    pendencias = avaliacao["pendencias"]
    summary = apresentar_oficio_wizard_summary(oficio)
    custeio_value = ""
    if form.is_bound:
        custeio_value = form.data.get("custeio", "")
    else:
        custeio_value = getattr(form.instance, "custeio", "") if getattr(form, "instance", None) else ""
    mostrar_custeio_observacao = custeio_value == "OUTRA_INSTITUICAO"
    modelos_queryset = form.fields["modelo_motivo"].queryset
    equipe_ids = list(oficio.servidores.values_list("pk", flat=True))
    modo_motorista = oficio.motorista_modo or Oficio.MOTORISTA_MODO_SERVIDOR
    servidores_attrs = form.fields["servidores"].widget.attrs
    if oficio.motorista_id and oficio.motorista_id in equipe_ids:
        servidores_attrs["data-picker-driver-value"] = str(oficio.motorista_id)
    else:
        servidores_attrs.pop("data-picker-driver-value", None)
    # Card de motorista externo: só aparece quando viatura selecionada + motorista não é da equipe
    _driver_in_equipe = bool(oficio.motorista_id) and oficio.motorista_id in equipe_ids
    show_motorista_card = bool(oficio.viatura_id) and not _driver_in_equipe
    # Campos de protocolo do motorista: visíveis no card (sempre que o card aparece)
    motorista_extras_visivel = show_motorista_card
    if transporte_form.is_bound:
        ref_raw = (transporte_form.data.get("motorista_oficio_referencia") or "").strip()
    else:
        ref_raw = (oficio.motorista_oficio_referencia or "").strip()

    # Dados auxiliares para o card de viatura selecionada (modo edição).
    viatura_selecionada_unidade = ""
    viatura_selecionada_edit_url = ""
    viatura_selecionada_modelo = ""
    viatura_selecionada_combustivel = ""
    viatura_selecionada_tipo = ""
    if oficio.viatura_id and oficio.viatura:
        v = oficio.viatura
        viatura_selecionada_unidade = str(v.unidade) if v.unidade_id else "—"
        viatura_selecionada_modelo = v.modelo or ""
        viatura_selecionada_combustivel = str(v.combustivel) if v.combustivel_id else ""
        viatura_selecionada_tipo = v.tipo or ""
        try:
            viatura_selecionada_edit_url = reverse(
                "cadastros:viatura_update", args=[oficio.viatura_id]
            )
        except Exception:
            viatura_selecionada_edit_url = ""

    return {
        "page_title": "Cadastro de ofício",
        **_wizard_shell_ctx(
            oficio=oficio,
            etapa_atual="dados_viajantes",
            dados_viajantes_status=avaliacao["status"],
        ),
        "pendencias": pendencias,
        "mostrar_pendencias_documento": mostrar_pendencias_documento,
        "wizard_summary": summary,
        "mostrar_custeio_observacao": mostrar_custeio_observacao,
        "modelos_motivo_url": _url_with_next(
            "oficios:modelos_motivo_index",
            reverse("oficios:dados_viajantes", args=[oficio.pk]),
        ),
        "tem_modelos_motivo": modelos_queryset.exists(),
        "modelo_motivo_selecionado": bool(form["modelo_motivo"].value()),
        "servidor_create_url": _cadastro_create_url(
            "cadastros:servidor_create",
            reverse("oficios:dados_viajantes", args=[oficio.pk]),
        ),
        "viatura_create_url": _cadastro_create_url(
            "cadastros:viatura_create",
            reverse("oficios:dados_viajantes", args=[oficio.pk]),
        ),
        "api_viatura_placa_url": reverse("oficios:api_viatura_por_placa", args=[oficio.pk]),
        "equipe_servidor_ids_csv": ",".join(str(pk) for pk in equipe_ids),
        "viatura_selecionada_unidade": viatura_selecionada_unidade,
        "viatura_selecionada_edit_url": viatura_selecionada_edit_url,
        "viatura_selecionada_modelo": viatura_selecionada_modelo,
        "viatura_selecionada_combustivel": viatura_selecionada_combustivel,
        "viatura_selecionada_tipo": viatura_selecionada_tipo,
        "show_motorista_card": show_motorista_card,
        "motorista_extras_visivel": motorista_extras_visivel,
        "motorista_oficio_ano": oficio.ano or timezone.localdate().year,
        "oficio_numero_ano_hint": f"/ {oficio.ano}" if oficio.ano else "",
        "motorista_oficio_numero_inicial": _motorista_oficio_numero_display(ref_raw),
        "motorista_compact_widget": mark_safe(
            transporte_form["motorista"].as_widget(attrs={"data-picker-variant": "compact"})
        ),
        "form": form,
        "transporte_form": transporte_form,
        "oficio": oficio,
        "wizard_back_url": _oficio_back_url(oficio),
        "wizard_back_label": _oficio_back_label(oficio),
        "wizard_footer_mode": "step1_minimal",
        "wizard_show_document_actions": False,
        "wizard_show_save_draft": False,
        "wizard_autosave_url": reverse("oficios:dados_viajantes_autosave", args=[oficio.pk]),
        "wizard_autosave_step": "dados_viajantes",
        **_wizard_footer_ctx(oficio),
    }


def _redirect_after_dados_viajantes_save(request, oficio, *, nav_action: str, created=False):
    if nav_action in ("wizard_back", "save_draft_list"):
        return _redirect_lista_oficio(
            request,
            oficio,
            "Ofício cadastrado com sucesso."
            if created
            else "Dados e viajantes salvos.",
        )
    if nav_action == "wizard_next":
        messages.success(
            request,
            "Ofício cadastrado com sucesso."
            if created
            else "Dados e viajantes atualizados com sucesso.",
        )
        return redirect("oficios:wizard_roteiro", pk=oficio.pk)
    messages.success(
        request,
        "Ofício cadastrado com sucesso." if created else "Dados e viajantes atualizados com sucesso.",
    )
    return redirect("oficios:dados_viajantes", pk=oficio.pk)


def _wizard_transporte_context(*, form, oficio):
    dados_av = avaliar_oficio_dados_viajantes(oficio=oficio)
    transp_av = avaliar_oficio_transporte(oficio)
    summary = apresentar_oficio_wizard_summary(oficio)
    equipe_ids = list(oficio.servidores.values_list("pk", flat=True))
    modo_motorista = oficio.motorista_modo or Oficio.MOTORISTA_MODO_SERVIDOR
    motorista_extras_visivel = modo_motorista == Oficio.MOTORISTA_MODO_MANUAL or (
        bool(oficio.motorista_id) and oficio.motorista_id not in equipe_ids
    )
    ano_motorista_ctx = oficio.ano or timezone.localdate().year
    if form.is_bound:
        ref_raw = (form.data.get("motorista_oficio_referencia") or "").strip()
    else:
        ref_raw = (oficio.motorista_oficio_referencia or "").strip()
    return {
        "page_title": "Cadastro de ofício",
        **_wizard_shell_ctx(
            oficio=oficio,
            etapa_atual="transporte",
            dados_viajantes_status=dados_av["status"],
            transporte_status=transp_av["status"],
        ),
        "wizard_summary": summary,
        "form": form,
        "oficio": oficio,
        "viatura_create_url": _cadastro_create_url(
            "cadastros:viatura_create",
            reverse("oficios:transporte", args=[oficio.pk]),
        ),
        "servidor_create_url": _cadastro_create_url(
            "cadastros:servidor_create",
            reverse("oficios:transporte", args=[oficio.pk]),
        ),
        "equipe_servidor_ids_csv": ",".join(str(pk) for pk in equipe_ids),
        "motorista_extras_visivel": motorista_extras_visivel,
        "motorista_oficio_ano": ano_motorista_ctx,
        "motorista_oficio_numero_inicial": _motorista_oficio_numero_display(ref_raw),
        "api_viatura_placa_url": reverse("oficios:api_viatura_por_placa", args=[oficio.pk]),
        "wizard_back_url": _oficio_back_url(oficio),
        "wizard_back_label": _oficio_back_label(oficio),
        "wizard_show_document_actions": True,
        "wizard_show_save_draft": True,
        "wizard_autosave_url": reverse("oficios:transporte_autosave", args=[oficio.pk]),
        "wizard_autosave_step": "transporte",
        **_wizard_footer_ctx(oficio),
    }


def _redirect_after_transporte_save(request, oficio, *, nav_action: str):
    if nav_action == "wizard_back":
        messages.success(request, "Transporte salvo.")
        return redirect("oficios:dados_viajantes", pk=oficio.pk)
    if nav_action == "save_draft_list":
        return _redirect_lista_oficio(request, oficio, "Transporte salvo.")
    if nav_action == "wizard_next":
        messages.success(request, "Transporte salvo. Continue para a próxima etapa quando estiver pronto.")
        return redirect("oficios:wizard_roteiro", pk=oficio.pk)
    messages.success(request, "Rascunho do transporte salvo.")
    return redirect("oficios:transporte", pk=oficio.pk)


def dados_viajantes(request, pk):
    oficio = get_oficio_by_id(pk)
    form = OficioDadosViajantesForm(request.POST or None, instance=oficio)
    transporte_form = OficioTransporteForm(request.POST or None, instance=Oficio.objects.get(pk=oficio.pk))
    _prepare_dados_viajantes_form(form)
    _prepare_transporte_form(transporte_form)
    if request.method == "POST":
        nav_action = normalizar_acao_do_wizard(request.POST)
        dados_ok = form.is_valid()
        save_transport = request.POST.get("transporte_embed") == "1"
        transporte_valido = bool(save_transport and transporte_form.is_valid())
        transp_ok = (not save_transport) or transporte_valido or nav_action == "wizard_next"
        if dados_ok and transp_ok:
            persist_action = _wizard_persist_action_para_dados_viajantes(nav_action)
            try:
                oficio = atualizar_oficio_dados_viajantes(oficio, form, action=persist_action)
            except OficioNumeroConflitoError as exc:
                form.add_error("numero", str(exc))
            else:
                if transporte_valido:
                    transporte_form = OficioTransporteForm(request.POST, instance=oficio)
                    _prepare_transporte_form(transporte_form)
                    transporte_form.is_valid()
                    oficio = atualizar_oficio_transporte(
                        oficio,
                        transporte_form,
                        action="save_continue" if nav_action == "wizard_next" else "save_draft",
                    )
                return _redirect_after_dados_viajantes_save(request, oficio, nav_action=nav_action, created=False)
    avaliacao = avaliar_oficio_dados_viajantes(form=form, oficio=oficio)
    mostrar_pendencias_documento = request.GET.get("documento_incompleto") == "1"
    return render(
        request,
        "oficios/wizard_dados_viajantes.html",
        _wizard_dados_viajantes_context(
            form=form,
            transporte_form=transporte_form,
            oficio=oficio,
            avaliacao=avaliacao,
            mostrar_pendencias_documento=mostrar_pendencias_documento,
        ),
    )


@require_POST
def dados_viajantes_autosave(request, pk):
    oficio = get_oficio_by_id(pk)
    try:
        payload = parse_autosave_payload(request, expected_model="oficio")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    dados_fields = set(OficioDadosViajantesForm.Meta.fields) | {"modelo_motivo"}
    transporte_fields = set(OficioTransporteForm.Meta.fields)
    allowed_fields = dados_fields | transporte_fields
    clean_fields = filter_allowed_fields(payload.fields, payload.dirty_fields, allowed_fields)
    if not clean_fields:
        return autosave_json_response(ok=True, object_id=oficio.pk, version=_oficio_autosave_version(oficio))

    data = _merge_payload_fields(_oficio_dados_viajantes_autosave_data(oficio), clean_fields)
    dirty_names = set(clean_fields)
    if dirty_names & dados_fields:
        form = OficioDadosViajantesForm(data, instance=oficio)
        _prepare_dados_viajantes_form(form)
        if not form.is_valid():
            return autosave_json_response(
                ok=False,
                message="Alguns campos ainda precisam de ajuste antes do autosave.",
                errors=_autosave_form_errors(form),
            )
        try:
            oficio = atualizar_oficio_dados_viajantes(oficio, form, action="save_draft")
        except OficioNumeroConflitoError as exc:
            form.add_error("numero", str(exc))
            return autosave_json_response(
                ok=False,
                message=str(exc),
                errors=_autosave_form_errors(form),
            )

    if dirty_names & transporte_fields:
        transporte_form = OficioTransporteForm(data, instance=oficio)
        _prepare_transporte_form(transporte_form)
        if not transporte_form.is_valid():
            return autosave_json_response(
                ok=False,
                message="Alguns campos de transporte ainda precisam de ajuste antes do autosave.",
                errors=_autosave_form_errors(transporte_form),
            )
        oficio = atualizar_oficio_transporte(oficio, transporte_form, action="save_draft")

    return autosave_json_response(ok=True, object_id=oficio.pk, version=_oficio_autosave_version(oficio))


def transporte(request, pk):
    oficio = get_oficio_by_id(pk)
    form = OficioTransporteForm(request.POST or None, instance=oficio)
    _prepare_transporte_form(form)
    if request.method == "POST" and form.is_valid():
        nav_action = normalizar_acao_do_wizard(request.POST)
        oficio = atualizar_oficio_transporte(
            oficio,
            form,
            action="save_continue" if nav_action == "wizard_next" else "save_draft",
        )
        return _redirect_after_transporte_save(request, oficio, nav_action=nav_action)
    return render(
        request,
        "oficios/wizard_transporte.html",
        _wizard_transporte_context(form=form, oficio=oficio),
    )


@require_POST
def transporte_autosave(request, pk):
    oficio = get_oficio_by_id(pk)
    try:
        payload = parse_autosave_payload(request, expected_model="oficio")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    clean_fields = filter_allowed_fields(
        payload.fields,
        payload.dirty_fields,
        set(OficioTransporteForm.Meta.fields),
    )
    if not clean_fields:
        return autosave_json_response(ok=True, object_id=oficio.pk, version=_oficio_autosave_version(oficio))

    data = _merge_payload_fields(_oficio_transporte_autosave_data(oficio), clean_fields)
    form = OficioTransporteForm(data, instance=oficio)
    _prepare_transporte_form(form)
    if not form.is_valid():
        return autosave_json_response(
            ok=False,
            message="Alguns campos de transporte ainda precisam de ajuste antes do autosave.",
            errors=_autosave_form_errors(form),
        )

    oficio = atualizar_oficio_transporte(oficio, form, action="save_draft")
    return autosave_json_response(ok=True, object_id=oficio.pk, version=_oficio_autosave_version(oficio))
