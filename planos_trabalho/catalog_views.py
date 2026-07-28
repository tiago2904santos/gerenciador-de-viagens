"""Views dos catálogos administráveis usados pelo plano de trabalho."""

from __future__ import annotations

import json
from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.presenters.badges import build_badge
from core.presenters.meta import build_meta
from core.tenancy import filter_queryset_by_area

from .forms import AtividadePlanoTrabalhoQuickAddForm
from .forms import HorarioAtendimentoForm
from .forms import PresetAtividadesQuickAddForm
from .forms import ProgramaSolicitanteForm
from .models import AtividadePlanoTrabalho
from .models import HorarioAtendimento
from .models import PresetAtividadesPlanoTrabalho
from .models import ProgramaSolicitante


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
        atividade = form.save(commit=False)
        atividade.area = getattr(request, "area", None)
        atividade.save()
        messages.success(request, "Atividade cadastrada.")
        return redirect(_atividades_index_url(back_url))

    atividades = filter_queryset_by_area(AtividadePlanoTrabalho.objects).order_by("ordem", "nome")
    if q:
        from core.normalizers import remove_accents

        q_unaccent = remove_accents(q)
        atividades = atividades.filter(
            Q(nome__unaccent__icontains=q_unaccent)
            | Q(codigo__unaccent__icontains=q_unaccent)
            | Q(meta__unaccent__icontains=q_unaccent)
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

def atividade_editar(request, pk):
    """Edição inline via quick add: processa o POST do painel e volta ao gerenciador."""
    atividade = get_object_or_404(filter_queryset_by_area(AtividadePlanoTrabalho.objects), pk=pk)
    back_url = _atividades_back_url(request)
    if request.method == "POST":
        form = AtividadePlanoTrabalhoQuickAddForm(request.POST, instance=atividade)
        if form.is_valid():
            atividade = form.save(commit=False)
            if not atividade.area_id:
                atividade.area = getattr(request, "area", None)
            atividade.save()
            messages.success(request, "Atividade atualizada.")
        else:
            for erros in form.errors.values():
                for erro in erros:
                    messages.error(request, erro)
    return redirect(_atividades_index_url(back_url))

def atividade_excluir(request, pk):
    atividade = get_object_or_404(filter_queryset_by_area(AtividadePlanoTrabalho.objects), pk=pk)
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

def _presets_back_url(request):
    candidato = request.POST.get("next") or request.GET.get("next") or ""
    if candidato and url_has_allowed_host_and_scheme(candidato, allowed_hosts={request.get_host()}):
        return candidato
    return reverse("planos_trabalho:index")

def _presets_index_url(back_url, base=None):
    base = base or reverse("planos_trabalho:presets_index")
    if back_url and back_url != reverse("planos_trabalho:index"):
        return f"{base}?{urlencode({'next': back_url})}"
    return base

def _preset_quick_add_field_values(preset):
    return json.dumps(
        {
            "nome": preset.nome,
            "atividades": [str(pk) for pk in preset.atividades.values_list("pk", flat=True)],
        },
        ensure_ascii=False,
    )

def presets_index(request):
    from django.db.models import Q

    q = request.GET.get("q", "").strip()
    back_url = _presets_back_url(request)
    form = PresetAtividadesQuickAddForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        preset = form.save(commit=False)
        preset.area = getattr(request, "area", None)
        preset.save()
        form.save_m2m()
        messages.success(request, "Preset cadastrado.")
        return redirect(_presets_index_url(back_url))

    presets = (
        filter_queryset_by_area(PresetAtividadesPlanoTrabalho.objects)
        .prefetch_related("atividades")
        .order_by("ordem", "nome")
    )
    if q:
        from core.normalizers import remove_accents

        q_unaccent = remove_accents(q)
        presets = presets.filter(
            Q(nome__unaccent__icontains=q_unaccent)
            | Q(descricao__unaccent__icontains=q_unaccent)
        )
    linhas = []
    for preset in presets:
        atividades = list(preset.atividades.order_by("ordem", "nome"))
        resumo = ", ".join(item.nome for item in atividades[:3]) or "Nenhuma atividade"
        if len(atividades) > 3:
            resumo = f"{resumo} (+{len(atividades) - 3})"
        linhas.append(
            {
                "title": preset.nome,
                "badges": (
                    ([build_badge("Padrão", "warning")] if preset.is_padrao else [])
                    + ([build_badge("Inativo", "neutral")] if not preset.ativo else [])
                ),
                "meta": [
                    build_meta("Atividades", f"{len(atividades)}"),
                    build_meta("Inclui", _truncar(resumo, 110)),
                ],
                "edit_url": _presets_index_url(
                    back_url,
                    base=reverse("planos_trabalho:preset_editar", args=[preset.pk]),
                ),
                "edit_fields_json": _preset_quick_add_field_values(preset),
                "delete_url": reverse("planos_trabalho:preset_excluir", args=[preset.pk]),
                "delete_modal": True,
                "set_default_url": (
                    _presets_index_url(
                        back_url,
                        base=reverse("planos_trabalho:preset_definir_padrao", args=[preset.pk]),
                    )
                    if not preset.is_padrao
                    else None
                ),
            }
        )
    is_wizard_back = back_url != reverse("planos_trabalho:index")
    return render(
        request,
        "planos_trabalho/presets/index.html",
        {
            "page_title": "Gerenciamento de presets",
            "page_description": "Monte conjuntos de atividades para aplicar de uma vez no wizard.",
            "q": q,
            "linhas": linhas,
            "quick_add_form": form,
            "quick_add_next_url": back_url if is_wizard_back else "",
            "back_url": back_url,
            "back_label": "Voltar pra plano de trabalho" if is_wizard_back else "Voltar",
        },
    )

def preset_editar(request, pk):
    preset = get_object_or_404(filter_queryset_by_area(PresetAtividadesPlanoTrabalho.objects), pk=pk)
    back_url = _presets_back_url(request)
    if request.method == "POST":
        form = PresetAtividadesQuickAddForm(request.POST, instance=preset)
        if form.is_valid():
            preset = form.save(commit=False)
            if not preset.area_id:
                preset.area = getattr(request, "area", None)
            preset.save()
            form.save_m2m()
            messages.success(request, "Preset atualizado.")
        else:
            for erros in form.errors.values():
                for erro in erros:
                    messages.error(request, erro)
    return redirect(_presets_index_url(back_url))

@require_POST
def preset_definir_padrao(request, pk):
    preset = get_object_or_404(filter_queryset_by_area(PresetAtividadesPlanoTrabalho.objects), pk=pk)
    back_url = _presets_back_url(request)
    preset.is_padrao = True
    preset.save(update_fields=["is_padrao", "updated_at"])
    messages.success(request, f"Preset “{preset.nome}” definido como padrão.")
    return redirect(_presets_index_url(back_url))

def preset_excluir(request, pk):
    preset = get_object_or_404(filter_queryset_by_area(PresetAtividadesPlanoTrabalho.objects), pk=pk)
    back_url = _presets_back_url(request)
    if request.method == "POST":
        nome = preset.nome
        preset.delete()
        messages.success(request, f"Preset “{nome}” excluído.")
        return redirect(_presets_index_url(back_url))
    return render(
        request,
        "planos_trabalho/presets/confirm_delete.html",
        {
            "page_title": "Excluir preset",
            "preset": preset,
            "cancel_url": _presets_index_url(back_url),
        },
    )

def programas_index(request):
    form = ProgramaSolicitanteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        programa = form.save(commit=False)
        programa.area = getattr(request, "area", None)
        programa.save()
        messages.success(request, "Programa cadastrado.")
        return redirect("planos_trabalho:programas_index")
    programas = filter_queryset_by_area(ProgramaSolicitante.objects).order_by("ordem", "nome")
    linhas = [
        {
            "title": programa.nome,
            "badges": [] if programa.ativo else [build_badge("Inativo", "neutral")],
            "meta": [
                {"label": "Ordem", "value": str(programa.ordem)},
            ],
            "edit_url": reverse("planos_trabalho:programa_editar", args=[programa.pk]),
            "edit_fields_json": json.dumps(
                {"nome": programa.nome, "ativo": programa.ativo, "ordem": programa.ordem},
                ensure_ascii=False,
            ),
            "delete_url": reverse("planos_trabalho:programa_excluir", args=[programa.pk]),
            "delete_modal": True,
        }
        for programa in programas
    ]
    return render(
        request,
        "planos_trabalho/programas/index.html",
        {
            "page_title": "Programas solicitantes",
            "page_description": "Programas exibidos na etapa de identificação do plano de trabalho.",
            "q": "",
            "linhas": linhas,
            "quick_add_form": form,
            "back_url": reverse("planos_trabalho:index"),
        },
    )

def programa_editar(request, pk):
    """Edição inline via quick edit da lista; a página standalone foi removida."""
    programa = get_object_or_404(filter_queryset_by_area(ProgramaSolicitante.objects), pk=pk)
    form = ProgramaSolicitanteForm(request.POST or None, instance=programa)
    if request.method == "POST":
        if form.is_valid():
            programa = form.save(commit=False)
            if not programa.area_id:
                programa.area = getattr(request, "area", None)
            programa.save()
            messages.success(request, "Programa atualizado.")
        else:
            messages.error(request, "Não foi possível salvar o programa. Verifique os dados informados.")
    return redirect("planos_trabalho:programas_index")

def programa_excluir(request, pk):
    programa = get_object_or_404(filter_queryset_by_area(ProgramaSolicitante.objects), pk=pk)
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
    form = HorarioAtendimentoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        horario = form.save(commit=False)
        horario.area = getattr(request, "area", None)
        horario.save()
        messages.success(request, "Horário cadastrado.")
        return redirect("planos_trabalho:horarios_index")
    horarios = filter_queryset_by_area(HorarioAtendimento.objects).order_by("ordem", "faixa")
    linhas = [
        {
            "title": horario.faixa,
            "badges": [] if horario.ativo else [build_badge("Inativo", "neutral")],
            "meta": [
                {"label": "Ordem", "value": str(horario.ordem)},
            ],
            "edit_url": reverse("planos_trabalho:horario_editar", args=[horario.pk]),
            "edit_fields_json": json.dumps(
                {"faixa": horario.faixa, "ativo": horario.ativo, "ordem": horario.ordem},
                ensure_ascii=False,
            ),
            "delete_url": reverse("planos_trabalho:horario_excluir", args=[horario.pk]),
            "delete_modal": True,
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
            "quick_add_form": form,
        },
    )

def horario_editar(request, pk):
    """Edição inline via quick edit da lista; a página standalone foi removida."""
    horario = get_object_or_404(filter_queryset_by_area(HorarioAtendimento.objects), pk=pk)
    form = HorarioAtendimentoForm(request.POST or None, instance=horario)
    if request.method == "POST":
        if form.is_valid():
            horario = form.save(commit=False)
            if not horario.area_id:
                horario.area = getattr(request, "area", None)
            horario.save()
            messages.success(request, "Horário atualizado.")
        else:
            messages.error(request, "Não foi possível salvar o horário. Verifique os dados informados.")
    return redirect("planos_trabalho:horarios_index")

def horario_excluir(request, pk):
    horario = get_object_or_404(filter_queryset_by_area(HorarioAtendimento.objects), pk=pk)
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
