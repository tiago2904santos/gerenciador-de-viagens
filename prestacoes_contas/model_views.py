"""CRUD dos modelos de texto reutilizáveis do relatório técnico."""

from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse

from core.normalizers import remove_accents
from core.deletion import DelecaoProtegidaError
from core.presenters.meta import build_meta
from core.retorno import com_next
from core.retorno import next_valido
from core.tenancy import filter_queryset_by_area

from .forms import ModeloTextoRelatorioTecnicoForm
from .models import ModeloTextoRelatorioTecnico
from .services import excluir_modelo_texto

# NOVO-03: ficou em `views.py` quando estas quatro views vieram para cá, e as duas
# leituras abaixo viravam `NameError` em rota viva. Mora aqui, junto de quem lê.
_CAMPO_LABELS = dict(ModeloTextoRelatorioTecnico.CAMPO_CHOICES)


def modelos_index(request):
    q = (request.GET.get("q") or "").strip()
    return_url = next_valido(request)
    index_url = reverse("prestacoes_contas:modelos_index")
    quick_add_campo = (request.POST.get("quick_add_campo") or "").strip()
    campo_solicitado = quick_add_campo or (request.GET.get("campo") or "").strip()
    campo_ativo = campo_solicitado if campo_solicitado in _CAMPO_LABELS else ModeloTextoRelatorioTecnico.CAMPO_CHOICES[0][0]

    abas = []
    for campo, label in ModeloTextoRelatorioTecnico.CAMPO_CHOICES:
        params = {"campo": campo}
        if q:
            params["q"] = q
        if return_url:
            params["next"] = return_url
        abas.append(
            {
                "campo": campo,
                "label": label,
                "url": f"{index_url}?{urlencode(params)}",
                "is_active": campo == campo_ativo,
            }
        )

    grupos = []
    for campo, label in ModeloTextoRelatorioTecnico.CAMPO_CHOICES:
        if campo != campo_ativo:
            continue
        prefixo = f"modelo-{campo}"
        quick_add_form = ModeloTextoRelatorioTecnicoForm(
            request.POST if request.method == "POST" and quick_add_campo == campo else None,
            initial={"campo": campo},
            prefix=prefixo,
        )
        if request.method == "POST" and quick_add_campo == campo and quick_add_form.is_valid():
            modelo = quick_add_form.save(commit=False)
            modelo.area = getattr(request, "area", None)
            modelo.save()
            messages.success(request, "Modelo criado com sucesso.")
            destino = com_next(_voltar_modelos_url(campo), return_url)
            return redirect(f"{destino}#grupo-{campo}")

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
                    "edit_url": reverse("prestacoes_contas:modelo_update", args=[modelo.pk]),
                    "delete_url": reverse("prestacoes_contas:modelo_delete", args=[modelo.pk]),
                }
            )

        grupos.append(
            {
                "campo": campo,
                "label": label,
                "rows": rows,
                "section_id": f"grupo-{campo}",
                "quick_add_form": quick_add_form,
                "quick_add_panel_id": f"quick-add-modelo-{campo}",
                "quick_add_action": f"{com_next(index_url, return_url)}#grupo-{campo}",
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
            "abas": abas,
            "campo_ativo": campo_ativo,
            "back_url": return_url,
            "back_label": "Voltar para o relatório técnico",
            "next_url": return_url,
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
        try:
            excluir_modelo_texto(modelo)
        except DelecaoProtegidaError as exc:
            messages.error(request, str(exc))
            return redirect(_voltar_modelos_url(campo))
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
