from __future__ import annotations
from django.contrib import messages
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST
from urllib.parse import urlencode
from core.autosave import AutosavePayloadError
from core.autosave import autosave_json_response
from core.autosave import parse_autosave_payload
from .services import atividades_catalogo_ativas
from .services import presets_atividades_ativos
from .services import sincronizar_atividades
from core.wizard import normalizar_acao_do_wizard

from .view_helpers import _get_plano, _redirect_plano_lista, _wizard_shell_ctx, _plano_autosave_version


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
    presets = presets_atividades_ativos()
    presets_data = [
        {
            "id": preset.pk,
            "nome": preset.nome,
            "codigos": [
                atividade.codigo
                for atividade in sorted(preset.atividades.all(), key=lambda a: (a.ordem, a.nome))
                if atividade.ativo
            ],
        }
        for preset in presets
    ]
    preset_padrao = next((preset for preset in presets if preset.is_padrao), None)
    wizard_url = reverse("planos_trabalho:wizard_atividades", args=[plano.pk])
    return {
        "page_title": "Plano de Trabalho",
        **_wizard_shell_ctx(plano=plano, etapa_atual="atividades"),
        "atividades_catalogo": catalogo_view,
        "atividades_catalogo_data": catalogo_data,
        "atividades_presets": presets,
        # As opções do `<select>` de presets já montadas, no formato que o
        # `c-v2.select` consome (`value`/`label`). Antes o template percorria o
        # queryset e escrevia cada `<option>` na mão, com o sufixo "— Padrão"
        # decidido lá dentro: era regra de apresentação num arquivo que não é o
        # presenter, e ela divergia da do cadastro de presets.
        "atividades_presets_options": [
            {"value": "", "label": "Aplicar preset…"},
            *(
                {
                    "value": str(preset.pk),
                    "label": f"{preset.nome} — Padrão" if preset.is_padrao else preset.nome,
                }
                for preset in presets
            ),
        ],
        "atividades_presets_data": presets_data,
        "atividades_preset_padrao_id": preset_padrao.pk if preset_padrao else None,
        "atividades_selecionadas_total": len(selecionados),
        "atividades_counter_label": f"{len(selecionados)} selecionadas",
        "metas_preview": metas_preview,
        "recursos_preview": recursos_preview,
        "atividades_manager_url": (
            reverse("planos_trabalho:atividades_index") + "?" + urlencode({"next": wizard_url})
        ),
        "presets_manager_url": (
            reverse("planos_trabalho:presets_index") + "?" + urlencode({"next": wizard_url})
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
        nav_action = normalizar_acao_do_wizard(request.POST)
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
    if not selected_codes:
        preset_padrao = next((preset for preset in presets_atividades_ativos() if preset.is_padrao), None)
        if preset_padrao:
            catalogo_por_codigo = {item.codigo: item for item in catalogo}
            selecionadas_padrao = [
                catalogo_por_codigo[atividade.codigo]
                for atividade in preset_padrao.atividades.all()
                if atividade.codigo in catalogo_por_codigo
            ]
            if selecionadas_padrao:
                plano.atividades_selecionadas.set(selecionadas_padrao)
                sincronizar_atividades(plano)
                selected_codes = {item.codigo for item in selecionadas_padrao}
    return render(
        request,
        "planos_trabalho/wizard_atividades.html",
        _atividades_context(plano=plano, catalogo=catalogo, selected_codes=selected_codes),
    )
