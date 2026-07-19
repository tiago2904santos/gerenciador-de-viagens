from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.normalizers import remove_accents

from .forms import JustificativaQuickAddForm
from .forms import ModeloJustificativaForm
from .presenters import apresentar_linha_lista_simples_justificativa
from .presenters import apresentar_linha_lista_simples_modelo_justificativa
from .selectors import get_justificativa_by_id
from .selectors import get_modelo_justificativa_by_id
from .selectors import listar_justificativas
from .selectors import listar_modelos_justificativa_busca
from .services import atualizar_modelo_justificativa
from .services import criar_justificativas_quick_add
from .services import criar_modelo_justificativa
from .services import excluir_justificativa
from .services import excluir_modelo_justificativa


JUSTIFICATIVAS_PER_PAGE = 15


def _url_with_next(url_name, next_url):
    return f"{reverse(url_name)}?{urlencode({'next': next_url})}"


def _append_next(url, next_url):
    if not next_url:
        return url
    return f"{url}?{urlencode({'next': next_url})}"


def _safe_next_url(request, fallback_url):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback_url


def _pagination_pages(page_obj, *, on_each_side=1, on_ends=1):
    return [
        page_number if isinstance(page_number, int) else "..."
        for page_number in page_obj.paginator.get_elided_page_range(
            page_obj.number,
            on_each_side=on_each_side,
            on_ends=on_ends,
        )
    ]


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
        q_unaccent = remove_accents(q)
        justificativas = justificativas.filter(
            Q(oficio__protocolo__unaccent__icontains=q_unaccent)
            | Q(oficio__assunto__unaccent__icontains=q_unaccent)
            | Q(texto__unaccent__icontains=q_unaccent)
            | Q(modelo__nome__unaccent__icontains=q_unaccent)
        )

    paginator = Paginator(justificativas, JUSTIFICATIVAS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    rows = [
        apresentar_linha_lista_simples_justificativa(
            j,
            delete_url=reverse("justificativas:justificativa_excluir", args=[j.pk]),
            delete_modal=True,
        )
        for j in page_obj.object_list
    ]
    return render(
        request,
        "justificativas/index.html",
        {
            "page_title": "Justificativas",
            "page_description": "Crie justificativas livres vinculadas a um ou mais oficios.",
            "quick_add_form": form,
            "q": q,
            "rows": rows,
            "modelos_url": reverse("justificativas:modelos_index"),
            "page_obj": page_obj,
            "pagination_pages": _pagination_pages(page_obj),
            "page_querystring": urlencode({"q": q}) if q else "",
        },
    )


@require_POST
def justificativa_excluir(request, pk):
    justificativa = get_justificativa_by_id(pk)
    excluir_justificativa(justificativa)
    messages.success(request, "Justificativa excluída com sucesso.")
    return redirect("justificativas:index")


def modelos_index(request):
    q = request.GET.get("q", "").strip()
    back_url = _safe_next_url(request, reverse("justificativas:index"))
    _oficios_prefix = reverse("oficios:index")
    if back_url.startswith(_oficios_prefix):
        back_label = "Voltar para o ofício"
        back_aria_label = "Voltar para o cadastro de ofício"
    else:
        back_label = "Voltar para as justificativas"
        back_aria_label = "Voltar para a lista de justificativas"
    form = ModeloJustificativaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_modelo_justificativa(form)
        messages.success(request, "Modelo de justificativa criado com sucesso.")
        return redirect(_url_with_next("justificativas:modelos_index", back_url))
    modelos = listar_modelos_justificativa_busca(q=q or None)
    rows = [
        apresentar_linha_lista_simples_modelo_justificativa(
            modelo,
            edit_url=_append_next(
                reverse("justificativas:modelo_editar", args=[modelo.pk]), back_url
            ),
            delete_url=_append_next(
                reverse("justificativas:modelo_excluir", args=[modelo.pk]), back_url
            ),
            delete_modal=True,
            next_url=back_url,
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
            "quick_add_form": form,
            "quick_add_next_url": back_url,
            "back_to_url": back_url,
            "back_label": back_label,
            "back_aria_label": back_aria_label,
        },
    )


@require_POST
def modelo_definir_padrao(request, pk):
    modelo = get_modelo_justificativa_by_id(pk)
    modelo.is_padrao = True
    modelo.save()
    messages.success(request, "Modelo definido como padrao.")
    next_url = _safe_next_url(request, reverse("justificativas:index"))
    return redirect(_append_next(reverse("justificativas:modelos_index"), next_url))


def modelo_editar(request, pk):
    """Edição inline via quick edit da lista; a página standalone foi removida."""
    modelo = get_modelo_justificativa_by_id(pk)
    next_url = _safe_next_url(request, reverse("justificativas:index"))
    form = ModeloJustificativaForm(request.POST or None, instance=modelo)
    if request.method == "POST":
        if form.is_valid():
            atualizar_modelo_justificativa(modelo, form)
            messages.success(request, "Modelo de justificativa atualizado com sucesso.")
        else:
            messages.error(request, "Não foi possível salvar o modelo. Verifique os dados informados.")
    return redirect(_append_next(reverse("justificativas:modelos_index"), next_url))


def modelo_excluir(request, pk):
    modelo = get_modelo_justificativa_by_id(pk)
    next_url = _safe_next_url(request, reverse("justificativas:index"))
    if request.method == "POST":
        excluir_modelo_justificativa(modelo)
        messages.success(request, "Modelo de justificativa excluido com sucesso.")
        return redirect(_append_next(reverse("justificativas:modelos_index"), next_url))
    return render(
        request,
        "justificativas/modelos/confirm_delete.html",
        {
            "page_title": "Excluir modelo de justificativa",
            "page_description": "Confirme a remocao deste modelo de justificativa.",
            "object": modelo,
            "back_url": _append_next(reverse("justificativas:modelos_index"), next_url),
        },
    )


def legacy_modelos_redirect(request):
    return redirect("justificativas:modelos_index")
