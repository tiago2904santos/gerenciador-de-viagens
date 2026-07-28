"""Gerenciamento dos modelos reutilizáveis de motivo de ofício."""

from django.contrib import messages
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import ModeloMotivoOficioForm
from .presenters import apresentar_linha_lista_simples_modelo_motivo
from .selectors import get_modelo_motivo_by_id
from .selectors import listar_modelos_motivo
from .services import atualizar_modelo_motivo
from .services import criar_modelo_motivo
from .services import excluir_modelo_motivo
from .view_navigation import safe_next_url
from .view_navigation import url_with_next


def modelos_motivo_index(request):
    query = request.GET.get("q", "").strip()
    back_url = safe_next_url(request, reverse("oficios:novo"))
    if back_url.startswith(reverse("ordens_servico:index")):
        back_label = "Voltar para a Ordem de Serviço"
        back_aria_label = "Voltar para o cadastro de Ordem de Serviço"
    else:
        back_label = "Voltar para o ofício"
        back_aria_label = "Voltar para o cadastro de ofício"
    form = ModeloMotivoOficioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_modelo_motivo(form)
        messages.success(request, "Modelo de motivo criado com sucesso.")
        return redirect(url_with_next("oficios:modelos_motivo_index", back_url))
    rows = [
        apresentar_linha_lista_simples_modelo_motivo(
            model,
            edit_url=reverse("oficios:modelo_motivo_editar", args=[model.pk]),
            delete_url=reverse("oficios:modelo_motivo_excluir", args=[model.pk]),
            delete_modal=True,
        )
        for model in listar_modelos_motivo(
            q=query or None,
            incluir_inativos=True,
        )
    ]
    return render(
        request,
        "oficios/modelos_motivo/index.html",
        {
            "page_title": "Modelos de motivo",
            "page_description": (
                "Cadastre textos reutilizáveis para preencher rapidamente "
                "o motivo dos ofícios."
            ),
            "q": query,
            "rows": rows,
            "quick_add_form": form,
            "quick_add_next_url": back_url,
            "back_to_oficio_url": back_url,
            "back_label": back_label,
            "back_aria_label": back_aria_label,
        },
    )


@require_POST
def modelo_motivo_definir_padrao(request, pk):
    model = get_modelo_motivo_by_id(pk)
    model.is_padrao = True
    model.save()
    messages.success(request, "Modelo definido como padrão.")
    return redirect("oficios:modelos_motivo_index")


def modelo_motivo_editar(request, pk):
    model = get_modelo_motivo_by_id(pk)
    form = ModeloMotivoOficioForm(request.POST or None, instance=model)
    if request.method == "POST":
        if form.is_valid():
            atualizar_modelo_motivo(model, form)
            messages.success(request, "Modelo de motivo atualizado com sucesso.")
        else:
            messages.error(
                request,
                "Não foi possível salvar o modelo. Verifique os dados informados.",
            )
    return redirect("oficios:modelos_motivo_index")


def modelo_motivo_excluir(request, pk):
    model = get_modelo_motivo_by_id(pk)
    if request.method == "POST":
        excluir_modelo_motivo(model)
        messages.success(request, "Modelo de motivo excluído com sucesso.")
        return redirect("oficios:modelos_motivo_index")
    return render(
        request,
        "oficios/modelos_motivo/confirm_delete.html",
        {
            "page_title": "Excluir modelo de motivo",
            "page_description": "Confirme a remoção deste modelo de motivo.",
            "object": model,
            "back_url": reverse("oficios:modelos_motivo_index"),
        },
    )
