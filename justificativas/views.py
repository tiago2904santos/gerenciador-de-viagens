from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.normalizers import remove_accents

from .catalogs import modelo_definir_padrao  # noqa: F401  (re-export para urls.py)
from .catalogs import modelo_editar  # noqa: F401
from .catalogs import modelo_excluir  # noqa: F401
from .catalogs import modelos_index  # noqa: F401
from .forms import JustificativaQuickAddForm
from .presenters import apresentar_linha_lista_simples_justificativa
from .presenters import apresentar_oficio_picker_summary
from .selectors import get_justificativa_by_id
from .selectors import listar_justificativas
from .services import criar_justificativas_quick_add
from .services import excluir_justificativa


JUSTIFICATIVAS_PER_PAGE = 15


def _oficios_summary_for_quick_add(form):
    """Resumo dos ofícios que alimentam o *picker*, a partir do queryset do campo.

    `NOVO-06`: a versão anterior montava isto de `Oficio.objects` cru — sem recorte
    de área — e o resultado vai para o corpo da página por `json_script`. Medido com
    20.000 ofícios em três áreas: **20.000 entradas** contra 6.666 da área ativa.

    Ler do próprio campo, e não de um queryset paralelo, é o que impede o resumo de
    voltar a divergir do que o formulário aceita: quem apertar o recorte num lugar
    aperta nos dois. É como `termos` e `ordens_servico` já fazem.
    """
    oficios = (
        form.fields["oficios"]
        .queryset.select_related(
            "roteiro__origem_cidade",
            "roteiro__origem_estado",
            "viatura",
        )
        .prefetch_related(
            "roteiro__destinos__cidade",
            "roteiro__destinos__estado",
            "servidores",
            "servidores_termo_autorizacao",
        )
    )
    summaries = {}
    for index, oficio in enumerate(oficios):
        summary = apresentar_oficio_picker_summary(oficio)
        summary["order"] = index
        summaries[str(summary["id"])] = summary
    return summaries


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
            "oficios_summary": _oficios_summary_for_quick_add(form),
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


def legacy_modelos_redirect(request):
    return redirect("justificativas:modelos_index")
