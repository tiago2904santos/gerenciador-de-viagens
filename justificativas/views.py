from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.pagination import contexto_paginacao
from django.views.decorators.http import require_http_methods

from core.normalizers import remove_accents
from oficios.picker import LIMITE_BUSCA
from oficios.picker import dados_do_option
from oficios.picker import oficios_ja_escolhidos
from oficios.selectors import listar_oficios

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


def _com_o_que_o_resumo_le(oficios):
    """As relações que `apresentar_oficio_picker_summary` toca, para não haver N+1."""
    return oficios.select_related(
        "roteiro__origem_cidade",
        "roteiro__origem_estado",
        "viatura",
    ).prefetch_related(
        "roteiro__destinos__cidade",
        "roteiro__destinos__estado",
        "servidores",
        "servidores_termo_autorizacao",
    )


def _resumos_de(oficios):
    """`{str(pk): resumo}` na forma que `CV.documentSource` consome.

    Recebe um iterável já preparado — o `select_related` tem de vir **antes** de
    qualquer fatiamento, e o Django recusa reescrever um queryset já fatiado.
    """
    resumos = {}
    for indice, oficio in enumerate(oficios):
        resumo = apresentar_oficio_picker_summary(oficio)
        resumo["order"] = indice
        # O `<option>` que a busca cria é montado com o que o servidor manda, não
        # adivinhado no JS: o texto é `str(oficio)` ("Ofício 01/2026") e o `label`
        # do resumo é outra coisa ("Oficio 01/2026", sem acento). Deixar o cliente
        # escolher faria a opção criada pela busca sair diferente da renderizada
        # pelo Django (`NOVO-07`).
        resumo["option"] = dados_do_option(oficio, resumo=resumo, rotulo=str)
        resumos[str(resumo["id"])] = resumo
    return resumos


def _oficios_summary_for_quick_add(form):
    """Resumo **apenas dos ofícios já selecionados** (`NOVO-07`).

    Antes isto trazia todo ofício da área e ia inteiro para o corpo da página por
    `json_script`. Medido: 45,1 KB para 66 ofícios, ~680 bytes cada — 4,5 MB com
    6.666. A tela crescia com a tabela, não com o que ela mostra.

    Agora o blob carrega só o que o formulário já tem selecionado (zero, na
    abertura), para o preenchimento inicial continuar imediato e síncrono. O
    resto chega por `api_buscar_oficios`, e o picker registra em memória.
    """
    return _resumos_de(_com_o_que_o_resumo_le(oficios_ja_escolhidos(form, "oficios")))


@require_http_methods(["GET"])
def api_buscar_oficios(request):
    """Busca de ofícios para o seletor, sob demanda (`NOVO-07`).

    Recorte por área vem de `listar_oficios`, que já aplica
    `filter_queryset_by_area` — é o mesmo caminho da lista de ofícios, e o mesmo
    dado que o `NOVO-06` fechou.
    """
    q = (request.GET.get("q") or "").strip()
    # `listar_oficios` já traz os prefetches que o resumo lê, já aplica o recorte
    # por área e já faz `.distinct()` quando há busca (`oficios/selectors.py:115`)
    # — a busca junta `servidores` e `roteiro__destinos`, e sem isso um ofício com
    # dois servidores que casam gastaria duas das 30 vagas.
    # `order_by` explícito, e não o default de `listar_oficios` (`-numero, -ano`):
    # o seletor sempre ofereceu o **mais recentemente criado** primeiro, que é o
    # que o queryset do campo fazia (`-created_at, -pk`). Trocar a ordem aqui
    # seria mudar a tela sem que nada avisasse.
    oficios = listar_oficios(q=q or None).order_by("-created_at", "-pk")[:LIMITE_BUSCA]
    return JsonResponse({"resultados": list(_resumos_de(oficios).values())})


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

    paginacao = contexto_paginacao(
        justificativas,
        request,
        JUSTIFICATIVAS_PER_PAGE,
        query_params={"q": q},
    )
    page_obj = paginacao["page_obj"]
    rows = [
        apresentar_linha_lista_simples_justificativa(
            j,
            delete_url=reverse("justificativas:justificativa_delete", args=[j.pk]),
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
            **paginacao,
        },
    )


@require_POST
def justificativa_excluir(request, pk):
    justificativa = get_justificativa_by_id(pk)
    excluir_justificativa(justificativa)
    messages.success(request, "Justificativa excluída com sucesso.")
    return redirect("justificativas:index")


def legacy_modelos_redirect(request, pk=None):
    return redirect("justificativas:modelos_index")
