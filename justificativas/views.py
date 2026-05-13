from django.contrib import messages
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import ModeloJustificativaForm
from .presenters import apresentar_linha_lista_simples_modelo_justificativa
from .selectors import get_modelo_justificativa_by_id
from .selectors import listar_modelos_justificativa_busca
from .services import atualizar_modelo_justificativa
from .services import criar_modelo_justificativa
from .services import excluir_modelo_justificativa


def modelos_index(request):
    q = request.GET.get("q", "").strip()
    modelos = listar_modelos_justificativa_busca(q=q or None)
    rows = [
        apresentar_linha_lista_simples_modelo_justificativa(
            modelo,
            edit_url=reverse("justificativas:modelo_editar", args=[modelo.pk]),
            delete_url=reverse("justificativas:modelo_excluir", args=[modelo.pk]),
        )
        for modelo in modelos
    ]
    return render(
        request,
        "justificativas/modelos/index.html",
        {
            "page_title": "Modelos de justificativa",
            "page_description": "Cadastre textos reutilizáveis para preencher rapidamente a justificativa dos ofícios.",
            "q": q,
            "rows": rows,
            "new_url": reverse("justificativas:modelo_novo"),
        },
    )


def modelo_novo(request):
    form = ModeloJustificativaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_modelo_justificativa(form)
        messages.success(request, "Modelo de justificativa criado com sucesso.")
        return redirect("justificativas:index")
    return render(
        request,
        "justificativas/modelos/form.html",
        {
            "page_title": "Novo modelo de justificativa",
            "page_description": "Crie textos reutilizáveis para agilizar o preenchimento da justificativa nos ofícios.",
            "form": form,
            "back_url": reverse("justificativas:index"),
            "submit_label": "Salvar modelo",
        },
    )


@require_POST
def modelo_definir_padrao(request, pk):
    modelo = get_modelo_justificativa_by_id(pk)
    modelo.is_padrao = True
    modelo.save()
    messages.success(request, "Modelo definido como padrão.")
    return redirect("justificativas:index")


def modelo_editar(request, pk):
    modelo = get_modelo_justificativa_by_id(pk)
    form = ModeloJustificativaForm(request.POST or None, instance=modelo)
    if request.method == "POST" and form.is_valid():
        atualizar_modelo_justificativa(modelo, form)
        messages.success(request, "Modelo de justificativa atualizado com sucesso.")
        return redirect("justificativas:index")
    return render(
        request,
        "justificativas/modelos/form.html",
        {
            "page_title": "Editar modelo de justificativa",
            "page_description": "Crie textos reutilizáveis para agilizar o preenchimento da justificativa nos ofícios.",
            "form": form,
            "back_url": reverse("justificativas:index"),
            "submit_label": "Salvar alterações",
        },
    )


def modelo_excluir(request, pk):
    modelo = get_modelo_justificativa_by_id(pk)
    if request.method == "POST":
        excluir_modelo_justificativa(modelo)
        messages.success(request, "Modelo de justificativa excluído com sucesso.")
        return redirect("justificativas:index")
    return render(
        request,
        "justificativas/modelos/confirm_delete.html",
        {
            "page_title": "Excluir modelo de justificativa",
            "page_description": "Confirme a remoção deste modelo de justificativa.",
            "object": modelo,
            "back_url": reverse("justificativas:index"),
        },
    )
