"""CRUD dos modelos de texto reutilizáveis do relatório técnico."""

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse

from core.normalizers import remove_accents
from core.presenters.meta import build_meta
from core.tenancy import filter_queryset_by_area

from .forms import ModeloTextoRelatorioTecnicoForm
from .models import ModeloTextoRelatorioTecnico

# NOVO-03: ficou em `views.py` quando estas quatro views vieram para cá, e as duas
# leituras abaixo viravam `NameError` em rota viva. Mora aqui, junto de quem lê.
_CAMPO_LABELS = dict(ModeloTextoRelatorioTecnico.CAMPO_CHOICES)


def modelos_index(request):
    q = (request.GET.get("q") or "").strip()
    novo_base = reverse("prestacoes_contas:modelo_novo")

    grupos = []
    for campo, label in ModeloTextoRelatorioTecnico.CAMPO_CHOICES:
        modelos = filter_queryset_by_area(ModeloTextoRelatorioTecnico.objects).filter(campo=campo)
        if q:
            q_unaccent = remove_accents(q)
            modelos = modelos.filter(Q(nome__unaccent__icontains=q_unaccent) | Q(texto__unaccent__icontains=q_unaccent))

        rows = []
        for modelo in modelos:
            texto = (modelo.texto or "").strip()
            if len(texto) > 90:
                texto = f"{texto[:90]}..."
            rows.append(
                {
                    "title": modelo.nome,
                    "badges": [],
                    "meta": [build_meta("Prévia", texto or "—")],
                    "edit_url": reverse("prestacoes_contas:modelo_editar", args=[modelo.pk]),
                    "delete_url": reverse("prestacoes_contas:modelo_excluir", args=[modelo.pk]),
                }
            )

        grupos.append(
            {
                "campo": campo,
                "label": label,
                "rows": rows,
                "new_url": f"{novo_base}?campo={campo}",
            }
        )

    return render(
        request,
        "prestacoes_contas/modelos_texto/index.html",
        {
            "page_title": "Modelos de texto do RT",
            "page_description": "Textos reutilizáveis para preencher rapidamente os campos do relatório técnico.",
            "q": q,
            "grupos": grupos,
        },
    )

def modelo_novo(request):
    initial = {}
    campo = (request.GET.get("campo") or "").strip()
    if campo in _CAMPO_LABELS:
        initial["campo"] = campo

    form = ModeloTextoRelatorioTecnicoForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        modelo = form.save(commit=False)
        modelo.area = getattr(request, "area", None)
        modelo.save()
        messages.success(request, "Modelo criado com sucesso.")
        return redirect(_voltar_modelos_url(form.cleaned_data["campo"]))

    return render(
        request,
        "prestacoes_contas/modelos_texto/form.html",
        {
            "page_title": "Novo modelo de texto",
            "page_description": "Crie textos reutilizáveis para agilizar o preenchimento do relatório técnico.",
            "form": form,
            "back_url": reverse("prestacoes_contas:modelos_index"),
            "submit_label": "Salvar modelo",
        },
    )

def modelo_editar(request, pk):
    modelo = get_object_or_404(filter_queryset_by_area(ModeloTextoRelatorioTecnico.objects), pk=pk)
    form = ModeloTextoRelatorioTecnicoForm(request.POST or None, instance=modelo)
    if request.method == "POST" and form.is_valid():
        modelo = form.save(commit=False)
        if not modelo.area_id:
            modelo.area = getattr(request, "area", None)
        modelo.save()
        messages.success(request, "Modelo atualizado com sucesso.")
        return redirect(_voltar_modelos_url(form.cleaned_data["campo"]))

    return render(
        request,
        "prestacoes_contas/modelos_texto/form.html",
        {
            "page_title": "Editar modelo de texto",
            "page_description": "Edite o texto reutilizável usado no relatório técnico.",
            "form": form,
            "back_url": _voltar_modelos_url(modelo.campo),
            "submit_label": "Salvar alterações",
        },
    )

def modelo_excluir(request, pk):
    modelo = get_object_or_404(filter_queryset_by_area(ModeloTextoRelatorioTecnico.objects), pk=pk)
    if request.method == "POST":
        campo = modelo.campo
        modelo.delete()
        messages.success(request, "Modelo excluído com sucesso.")
        return redirect(_voltar_modelos_url(campo))

    return render(
        request,
        "prestacoes_contas/modelos_texto/confirm_delete.html",
        {
            "page_title": "Excluir modelo de texto",
            "page_description": "Confirme a remoção deste modelo.",
            "object": modelo,
            "back_url": _voltar_modelos_url(modelo.campo),
        },
    )

def _voltar_modelos_url(campo) -> str:
    url = reverse("prestacoes_contas:modelos_index")
    if campo in _CAMPO_LABELS:
        return f"{url}?campo={campo}"
    return url
