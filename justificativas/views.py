from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import JustificativaQuickAddForm
from .forms import ModeloJustificativaForm
from .presenters import apresentar_linha_lista_simples_justificativa
from .presenters import apresentar_linha_lista_simples_modelo_justificativa
from .selectors import get_modelo_justificativa_by_id
from .selectors import listar_justificativas
from .selectors import listar_modelos_justificativa_busca
from .services import atualizar_modelo_justificativa
from .services import criar_justificativas_quick_add
from .services import criar_modelo_justificativa
from .services import excluir_modelo_justificativa


def index(request):
    form = JustificativaQuickAddForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        justificativas = criar_justificativas_quick_add(form)
        total = len(justificativas)
        messages.success(request, f"{total} justificativa(s) criada(s) com sucesso.")
        return redirect("justificativas:index")

    q = request.GET.get("q", "").strip()
    justificativas = listar_justificativas()
    if q:
        justificativas = justificativas.filter(
            Q(oficio__protocolo__icontains=q)
            | Q(oficio__assunto__icontains=q)
            | Q(texto__icontains=q)
            | Q(modelo__nome__icontains=q)
        )

    rows = [apresentar_linha_lista_simples_justificativa(j) for j in justificativas]
    return render(
        request,
        "justificativas/index.html",
        {
            "page_title": "Justificativas",
            "page_description": "Crie justificativas livres vinculadas a um ou mais oficios.",
            "form": form,
            "q": q,
            "rows": rows,
            "modelos_url": reverse("justificativas:modelos_index"),
        },
    )


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
            "page_description": "Cadastre textos reutilizaveis para preencher rapidamente a justificativa dos oficios.",
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
        return redirect("justificativas:modelos_index")
    return render(
        request,
        "justificativas/modelos/form.html",
        {
            "page_title": "Novo modelo de justificativa",
            "page_description": "Crie textos reutilizaveis para agilizar o preenchimento da justificativa nos oficios.",
            "form": form,
            "back_url": reverse("justificativas:modelos_index"),
            "submit_label": "Salvar modelo",
        },
    )


@require_POST
def modelo_definir_padrao(request, pk):
    modelo = get_modelo_justificativa_by_id(pk)
    modelo.is_padrao = True
    modelo.save()
    messages.success(request, "Modelo definido como padrao.")
    return redirect("justificativas:modelos_index")


def modelo_editar(request, pk):
    modelo = get_modelo_justificativa_by_id(pk)
    form = ModeloJustificativaForm(request.POST or None, instance=modelo)
    if request.method == "POST" and form.is_valid():
        atualizar_modelo_justificativa(modelo, form)
        messages.success(request, "Modelo de justificativa atualizado com sucesso.")
        return redirect("justificativas:modelos_index")
    return render(
        request,
        "justificativas/modelos/form.html",
        {
            "page_title": "Editar modelo de justificativa",
            "page_description": "Crie textos reutilizaveis para agilizar o preenchimento da justificativa nos oficios.",
            "form": form,
            "back_url": reverse("justificativas:modelos_index"),
            "submit_label": "Salvar alteracoes",
        },
    )


def modelo_excluir(request, pk):
    modelo = get_modelo_justificativa_by_id(pk)
    if request.method == "POST":
        excluir_modelo_justificativa(modelo)
        messages.success(request, "Modelo de justificativa excluido com sucesso.")
        return redirect("justificativas:modelos_index")
    return render(
        request,
        "justificativas/modelos/confirm_delete.html",
        {
            "page_title": "Excluir modelo de justificativa",
            "page_description": "Confirme a remocao deste modelo de justificativa.",
            "object": modelo,
            "back_url": reverse("justificativas:modelos_index"),
        },
    )


def legacy_modelos_redirect(request):
    return redirect("justificativas:modelos_index")
