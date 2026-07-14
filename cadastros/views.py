import csv
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from core.utils.masks import only_digits
from .models import Servidor
from .models import Viatura
from .forms import CargoForm
from .forms import CidadeForm
from .forms import CombustivelForm
from .forms import ConfiguracaoAssinaturasForm
from .forms import ConfiguracaoDestinatarioForm
from .forms import ConfiguracaoSistemaForm
from .forms import EstadoForm
from .forms import ServidorForm
from .forms import UnidadeForm
from .forms import ViaturaForm
from .presenters import apresentar_linha_lista_simples_cargo
from .presenters import apresentar_linha_lista_simples_cidade
from .presenters import apresentar_linha_lista_simples_estado
from .presenters import apresentar_linha_lista_simples_combustivel
from .presenters import apresentar_linha_lista_simples_servidor
from .presenters import apresentar_linha_lista_simples_unidade
from .presenters import apresentar_linha_lista_simples_viatura
from .selectors import get_cargo_by_id
from .selectors import get_cidade_by_id
from .selectors import get_estado_by_id
from .selectors import get_combustivel_by_id
from .selectors import get_servidor_by_id
from .selectors import get_unidade_by_id
from .selectors import get_viatura_by_id
from .selectors import listar_cargos
from .selectors import listar_cidades
from .selectors import listar_estados
from .selectors import listar_combustiveis
from .selectors import listar_servidores
from .selectors import listar_unidades
from .selectors import listar_viaturas
from .services import atualizar_cargo
from .services import atualizar_cidade
from .services import atualizar_estado
from .services import atualizar_combustivel
from .services import atualizar_servidor
from .services import atualizar_unidade
from .services import atualizar_viatura
from .services import CadastroVinculadoError
from .services import criar_cargo
from .services import criar_cidade
from .services import criar_estado
from .services import criar_combustivel
from .services import criar_servidor
from .services import criar_unidade
from .services import criar_viatura
from .services import excluir_cargo
from .services import excluir_cidade
from .services import excluir_estado
from .services import excluir_combustivel
from .services import excluir_servidor
from .services import excluir_unidade
from .services import definir_cargo_padrao
from .services import definir_combustivel_padrao
from .services import excluir_viatura
from .services import salvar_configuracao_sistema
from .services import consultar_cep
from .services_via_cep import ViaCEPNotFoundError
from .services_via_cep import ViaCEPServiceError


CADASTROS_PER_PAGE = 15
SERVIDORES_PER_PAGE = 25


def _render_listagem(request, template_name, context):
    return render(request, template_name, context)


def _pagination_pages(page_obj, *, on_each_side=1, on_ends=1):
    return [
        page_number if isinstance(page_number, int) else "..."
        for page_number in page_obj.paginator.get_elided_page_range(
            page_obj.number,
            on_each_side=on_each_side,
            on_ends=on_ends,
        )
    ]


def _vinculo_error(request):
    messages.error(
        request,
        "Não foi possível excluir este cadastro porque ele está vinculado a outros registros.",
    )


def _safe_next_url(request, fallback_url):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback_url


def index(request):
    return render(
        request,
        "cadastros/index.html",
        {
            "page_title": "Cadastros",
            "page_description": "Dados-base e cadastros auxiliares dos fluxos.",
            "modules": [
                {
                    "title": "Servidores",
                    "description": "Pessoas vinculadas aos fluxos.",
                    "href": reverse("cadastros:servidores_index"),
                    "eyebrow": "Cadastro",
                },
                {
                    "title": "Cargos",
                    "description": "Cargos utilizados em servidores.",
                    "href": reverse("cadastros:cargos_index"),
                    "eyebrow": "Cadastro",
                },
                {
                    "title": "Viaturas",
                    "description": "Veículos operacionais.",
                    "href": reverse("cadastros:viaturas_index"),
                    "eyebrow": "Cadastro",
                },
                {
                    "title": "Combustíveis",
                    "description": "Tipos de combustível.",
                    "href": reverse("cadastros:combustiveis_index"),
                    "eyebrow": "Cadastro",
                },
                {
                    "title": "Unidades",
                    "description": "Unidades administrativas.",
                    "href": reverse("cadastros:unidades_index"),
                    "eyebrow": "Cadastro",
                },
                {
                    "title": "Cidades",
                    "description": "Base geográfica de referência dos fluxos.",
                    "href": reverse("cadastros:cidades_index"),
                    "eyebrow": "Cadastro",
                },
                {
                    "title": "Configurações do sistema",
                    "description": "Dados institucionais e assinaturas por tipo de documento.",
                    "href": reverse("cadastros:configuracao"),
                    "eyebrow": "Sistema",
                },
            ],
            "internal_modules": [
                {
                    "title": "Estados",
                    "description": "Base administrativa interna para suporte à malha de cidades.",
                    "href": reverse("cadastros:estados_index"),
                    "eyebrow": "Base interna",
                },
            ],
        },
    )


def estados_index(request):
    q = request.GET.get("q", "").strip()
    estados = listar_estados(q=q)
    paginator = Paginator(estados, CADASTROS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    rows = [
        apresentar_linha_lista_simples_estado(
            estado,
            edit_url=reverse("cadastros:estado_update", args=[estado.pk]),
            delete_url=reverse("cadastros:estado_delete", args=[estado.pk]),
            delete_modal=True,
        )
        for estado in page_obj.object_list
    ]
    return _render_listagem(
        request,
        "cadastros/estados/index.html",
        {
            "page_title": "Estados",
            "page_description": "Base administrativa interna de unidades federativas (UF).",
            "rows": rows,
            "q": q,
            "page_eyebrow": "Cadastros internos",
            "page_obj": page_obj,
            "pagination_pages": _pagination_pages(page_obj),
            "page_querystring": urlencode({"q": q}) if q else "",
        },
    )


def estado_create(request):
    form = EstadoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_estado(form)
        messages.success(request, "Estado criado com sucesso.")
        return redirect("cadastros:estados_index")
    return render(
        request,
        "cadastros/estados/form.html",
        {
            "page_title": "Novo estado",
            "page_description": "Cadastre UF e nome oficial.",
            "form": form,
            "submit_label": "Criar estado",
            "submit_icon": "plus",
            "back_url": reverse("cadastros:estados_index"),
        },
    )


def estado_update(request, pk):
    estado = get_estado_by_id(pk)
    form = EstadoForm(request.POST or None, instance=estado)
    if request.method == "POST" and form.is_valid():
        atualizar_estado(estado, form)
        messages.success(request, "Estado atualizado com sucesso.")
        return redirect("cadastros:estados_index")
    return render(
        request,
        "cadastros/estados/form.html",
        {
            "page_title": "Editar estado",
            "page_description": "Atualize os dados da UF.",
            "form": form,
            "submit_label": "Salvar estado",
            "submit_icon": "check",
            "back_url": reverse("cadastros:estados_index"),
        },
    )


def estado_delete(request, pk):
    estado = get_estado_by_id(pk)
    if request.method == "POST":
        try:
            excluir_estado(estado)
        except CadastroVinculadoError:
            _vinculo_error(request)
            return redirect("cadastros:estados_index")
        messages.success(request, "Estado excluído com sucesso.")
        return redirect("cadastros:estados_index")
    return render(
        request,
        "cadastros/estados/confirm_delete.html",
        {
            "page_title": "Excluir estado",
            "page_description": "Não é possível excluir se existirem cidades vinculadas.",
            "object": estado,
            "back_url": reverse("cadastros:estados_index"),
        },
    )


def unidades_index(request):
    q = request.GET.get("q", "").strip()
    form = UnidadeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_unidade(form)
        messages.success(request, "Unidade criada com sucesso.")
        return redirect("cadastros:unidades_index")
    unidades = listar_unidades(q=q)
    paginator = Paginator(unidades, CADASTROS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    rows = [
        apresentar_linha_lista_simples_unidade(
            unidade,
            edit_url=reverse("cadastros:unidade_update", args=[unidade.pk]),
            delete_url=reverse("cadastros:unidade_delete", args=[unidade.pk]),
            delete_modal=True,
        )
        for unidade in page_obj.object_list
    ]
    return _render_listagem(
        request,
        "cadastros/unidades/index.html",
        {
            "page_title": "Unidades",
            "page_description": "Unidades administrativas reutilizadas nos fluxos.",
            "rows": rows,
            "q": q,
            "quick_add_form": form,
            "page_obj": page_obj,
            "pagination_pages": _pagination_pages(page_obj),
            "page_querystring": urlencode({"q": q}) if q else "",
        },
    )


def unidade_create(request):
    form = UnidadeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_unidade(form)
        messages.success(request, "Unidade criada com sucesso.")
        return redirect("cadastros:unidades_index")
    return render(
        request,
        "cadastros/unidades/form.html",
        {
            "page_title": "Nova unidade",
            "page_description": "Cadastre uma unidade administrativa reutilizável.",
            "form": form,
            "submit_label": "Criar unidade",
            "submit_icon": "plus",
            "back_url": reverse("cadastros:unidades_index"),
        },
    )


def unidade_update(request, pk):
    unidade = get_unidade_by_id(pk)
    form = UnidadeForm(request.POST or None, instance=unidade)
    if request.method == "POST" and form.is_valid():
        atualizar_unidade(unidade, form)
        messages.success(request, "Unidade atualizada com sucesso.")
        return redirect("cadastros:unidades_index")
    return render(
        request,
        "cadastros/unidades/form.html",
        {
            "page_title": "Editar unidade",
            "page_description": "Atualize os dados da unidade.",
            "form": form,
            "submit_label": "Salvar unidade",
            "submit_icon": "check",
            "back_url": reverse("cadastros:unidades_index"),
        },
    )


def unidade_delete(request, pk):
    unidade = get_unidade_by_id(pk)
    if request.method == "POST":
        try:
            excluir_unidade(unidade)
        except CadastroVinculadoError:
            _vinculo_error(request)
            return redirect("cadastros:unidades_index")
        messages.success(request, "Unidade excluída com sucesso.")
        return redirect("cadastros:unidades_index")
    return redirect("cadastros:unidades_index")


def cidades_index(request):
    q = request.GET.get("q", "").strip()
    cidades = listar_cidades(q=q)
    paginator = Paginator(cidades, CADASTROS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    rows = [
        apresentar_linha_lista_simples_cidade(
            cidade,
            edit_url=reverse("cadastros:cidade_update", args=[cidade.pk]),
            delete_url=reverse("cadastros:cidade_delete", args=[cidade.pk]),
            delete_modal=True,
        )
        for cidade in page_obj.object_list
    ]
    export_base = reverse("cadastros:cidades_export_csv")
    export_csv_url = f"{export_base}?{urlencode({'q': q})}" if q else export_base
    return _render_listagem(
        request,
        "cadastros/cidades/index.html",
        {
            "page_title": "Cidades",
            "page_description": "Cidades de referência para os fluxos.",
            "rows": rows,
            "q": q,
            "export_csv_url": export_csv_url,
            "page_eyebrow": "Cadastros",
            "page_obj": page_obj,
            "pagination_pages": _pagination_pages(page_obj),
            "page_querystring": urlencode({"q": q}) if q else "",
        },
    )


def cidades_export_csv(request):
    q = request.GET.get("q", "").strip()
    cidades = listar_cidades(q=q)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="cidades.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(
        ["id", "nome", "uf", "estado_id", "capital", "codigo_ibge", "criado_em", "atualizado_em"],
    )
    for cidade in cidades:
        writer.writerow(
            [
                cidade.pk,
                cidade.nome,
                cidade.uf,
                cidade.estado_id,
                cidade.capital,
                cidade.codigo_ibge or "",
                cidade.created_at.isoformat(),
                cidade.updated_at.isoformat(),
            ]
        )
    return response


def cidade_create(request):
    form = CidadeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_cidade(form)
        messages.success(request, "Cidade criada com sucesso.")
        return redirect("cadastros:cidades_index")
    return render(
        request,
        "cadastros/cidades/form.html",
        {
            "page_title": "Nova cidade",
            "page_description": "Cadastre uma cidade de referência.",
            "form": form,
            "submit_label": "Criar cidade",
            "submit_icon": "plus",
            "back_url": reverse("cadastros:cidades_index"),
        },
    )


def cidade_update(request, pk):
    cidade = get_cidade_by_id(pk)
    form = CidadeForm(request.POST or None, instance=cidade)
    if request.method == "POST" and form.is_valid():
        atualizar_cidade(cidade, form)
        messages.success(request, "Cidade atualizada com sucesso.")
        return redirect("cadastros:cidades_index")
    return render(
        request,
        "cadastros/cidades/form.html",
        {
            "page_title": "Editar cidade",
            "page_description": "Atualize os dados da cidade.",
            "form": form,
            "submit_label": "Salvar cidade",
            "submit_icon": "check",
            "back_url": reverse("cadastros:cidades_index"),
        },
    )


def cidade_delete(request, pk):
    cidade = get_cidade_by_id(pk)
    if request.method == "POST":
        try:
            excluir_cidade(cidade)
        except CadastroVinculadoError:
            _vinculo_error(request)
            return redirect("cadastros:cidades_index")
        messages.success(request, "Cidade excluída com sucesso.")
        return redirect("cadastros:cidades_index")
    return render(
        request,
        "cadastros/cidades/confirm_delete.html",
        {
            "page_title": "Excluir cidade",
            "page_description": "Esta ação excluirá o cadastro. Se houver vínculos com outros registros, a exclusão será bloqueada.",
            "object": cidade,
            "back_url": reverse("cadastros:cidades_index"),
        },
    )


def cargos_index(request):
    q = request.GET.get("q", "").strip()
    form = CargoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_cargo(form)
        messages.success(request, "Cargo criado com sucesso.")
        return redirect("cadastros:cargos_index")
    cargos = listar_cargos(q=q)
    paginator = Paginator(cargos, CADASTROS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    rows = [
        apresentar_linha_lista_simples_cargo(
            cargo,
            edit_url=reverse("cadastros:cargo_update", args=[cargo.pk]),
            delete_url=reverse("cadastros:cargo_delete", args=[cargo.pk]),
            delete_modal=True,
            set_default_url=(
                reverse("cadastros:cargo_set_default", args=[cargo.pk]) if not cargo.is_padrao else None
            ),
        )
        for cargo in page_obj.object_list
    ]
    return _render_listagem(
        request,
        "cadastros/cargos/index.html",
        {
            "page_title": "Cargos",
            "page_description": "Cadastre os cargos utilizados em servidores.",
            "rows": rows,
            "q": q,
            "quick_add_form": form,
            "page_obj": page_obj,
            "pagination_pages": _pagination_pages(page_obj),
            "page_querystring": urlencode({"q": q}) if q else "",
        },
    )


def cargo_create(request):
    form = CargoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_cargo(form)
        messages.success(request, "Cargo criado com sucesso.")
        return redirect("cadastros:cargos_index")
    return render(
        request,
        "cadastros/cargos/form.html",
        {
            "page_title": "Novo cargo",
            "page_description": "Cadastre um cargo para seleção em servidores.",
            "form": form,
            "submit_label": "Criar cargo",
            "submit_icon": "plus",
            "back_url": reverse("cadastros:cargos_index"),
        },
    )


def cargo_update(request, pk):
    cargo = get_cargo_by_id(pk)
    form = CargoForm(request.POST or None, instance=cargo)
    if request.method == "POST" and form.is_valid():
        atualizar_cargo(cargo, form)
        messages.success(request, "Cargo atualizado com sucesso.")
        return redirect("cadastros:cargos_index")
    return render(
        request,
        "cadastros/cargos/form.html",
        {
            "page_title": "Editar cargo",
            "page_description": "Atualize os dados do cargo.",
            "form": form,
            "submit_label": "Salvar cargo",
            "submit_icon": "check",
            "back_url": reverse("cadastros:cargos_index"),
        },
    )


def cargo_set_default(request, pk):
    if request.method != "POST":
        return redirect("cadastros:cargos_index")
    cargo = get_cargo_by_id(pk)
    definir_cargo_padrao(cargo)
    messages.success(request, "Cargo definido como padrão com sucesso.")
    return redirect("cadastros:cargos_index")


def cargo_delete(request, pk):
    cargo = get_cargo_by_id(pk)
    if request.method != "POST":
        return redirect("cadastros:cargos_index")
    try:
        excluir_cargo(cargo)
    except CadastroVinculadoError:
        _vinculo_error(request)
        return redirect("cadastros:cargos_index")
    messages.success(request, "Cargo excluído com sucesso.")
    return redirect("cadastros:cargos_index")


def combustiveis_index(request):
    q = request.GET.get("q", "").strip()
    form = CombustivelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_combustivel(form)
        messages.success(request, "Combustível criado com sucesso.")
        return redirect("cadastros:combustiveis_index")
    combustiveis = listar_combustiveis(q=q)
    paginator = Paginator(combustiveis, CADASTROS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    rows = [
        apresentar_linha_lista_simples_combustivel(
            combustivel,
            edit_url=reverse("cadastros:combustivel_update", args=[combustivel.pk]),
            delete_url=reverse("cadastros:combustivel_delete", args=[combustivel.pk]),
            set_default_url=(
                reverse("cadastros:combustivel_set_default", args=[combustivel.pk])
                if not combustivel.is_padrao
                else None
            ),
            delete_modal=True,
        )
        for combustivel in page_obj.object_list
    ]
    return _render_listagem(
        request,
        "cadastros/combustiveis/index.html",
        {
            "page_title": "Combustíveis",
            "page_description": "Cadastre os combustíveis disponíveis para viaturas.",
            "rows": rows,
            "q": q,
            "quick_add_form": form,
            "page_obj": page_obj,
            "pagination_pages": _pagination_pages(page_obj),
            "page_querystring": urlencode({"q": q}) if q else "",
        },
    )


def combustivel_create(request):
    form = CombustivelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_combustivel(form)
        messages.success(request, "Combustível criado com sucesso.")
        return redirect("cadastros:combustiveis_index")
    return render(
        request,
        "cadastros/combustiveis/form.html",
        {
            "page_title": "Novo combustível",
            "page_description": "Cadastre um combustível para seleção em viaturas.",
            "form": form,
            "submit_label": "Criar combustível",
            "submit_icon": "plus",
            "back_url": reverse("cadastros:combustiveis_index"),
        },
    )


def combustivel_update(request, pk):
    combustivel = get_combustivel_by_id(pk)
    form = CombustivelForm(request.POST or None, instance=combustivel)
    if request.method == "POST" and form.is_valid():
        atualizar_combustivel(combustivel, form)
        messages.success(request, "Combustível atualizado com sucesso.")
        return redirect("cadastros:combustiveis_index")
    return render(
        request,
        "cadastros/combustiveis/form.html",
        {
            "page_title": "Editar combustível",
            "page_description": "Atualize os dados do combustível.",
            "form": form,
            "submit_label": "Salvar combustível",
            "submit_icon": "check",
            "back_url": reverse("cadastros:combustiveis_index"),
        },
    )


def combustivel_set_default(request, pk):
    if request.method != "POST":
        return redirect("cadastros:combustiveis_index")
    combustivel = get_combustivel_by_id(pk)
    definir_combustivel_padrao(combustivel)
    messages.success(request, "Combustível definido como padrão com sucesso.")
    return redirect("cadastros:combustiveis_index")


def combustivel_delete(request, pk):
    combustivel = get_combustivel_by_id(pk)
    if request.method == "POST":
        try:
            excluir_combustivel(combustivel)
        except CadastroVinculadoError:
            _vinculo_error(request)
            return redirect("cadastros:combustiveis_index")
        messages.success(request, "Combustível excluído com sucesso.")
        return redirect("cadastros:combustiveis_index")
    return redirect("cadastros:combustiveis_index")


def servidores_index(request):
    q = request.GET.get("q", "").strip()
    servidores = listar_servidores(q=q)
    paginator = Paginator(servidores, SERVIDORES_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    rows = [
        apresentar_linha_lista_simples_servidor(
            servidor,
            edit_url=reverse("cadastros:servidor_update", args=[servidor.pk]),
            delete_url=reverse("cadastros:servidor_delete", args=[servidor.pk]),
            delete_modal=True,
        )
        for servidor in page_obj.object_list
    ]
    return _render_listagem(
        request,
        "cadastros/servidores/index.html",
        {
            "page_title": "Servidores",
            "page_description": "Servidores vinculados aos fluxos documentais.",
            "rows": rows,
            "q": q,
            "page_obj": page_obj,
            "pagination_pages": _pagination_pages(page_obj),
            "page_querystring": urlencode({"q": q}) if q else "",
        },
    )


def servidor_create(request):
    index_url = reverse("cadastros:servidores_index")
    next_url = _safe_next_url(request, index_url)
    form = ServidorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        servidor = criar_servidor(form)
        if servidor.status == Servidor.STATUS_RASCUNHO:
            messages.success(request, "Servidor salvo como rascunho. Complete cargo e CPF quando possível.")
        else:
            messages.success(request, "Servidor criado com sucesso.")
        return redirect(next_url)
    return render(
        request,
        "cadastros/servidores/form.html",
        {
            "page_title": "Novo servidor",
            "page_description": "Apenas o nome é obrigatório — cargo, CPF, RG e unidade podem ser completados depois; o cadastro fica como rascunho até então.",
            "form": form,
            "submit_label": "Criar servidor",
            "submit_icon": "plus",
            "next_url": next_url,
            "back_url": next_url,
            "cargos_manage_url": reverse("cadastros:cargos_index"),
            "unidades_manage_url": reverse("cadastros:unidades_index"),
        },
    )


def servidor_update(request, pk):
    servidor = get_servidor_by_id(pk)
    form = ServidorForm(request.POST or None, instance=servidor)
    if request.method == "POST" and form.is_valid():
        servidor = atualizar_servidor(servidor, form)
        if servidor.status == Servidor.STATUS_RASCUNHO:
            messages.success(request, "Servidor salvo como rascunho. Complete cargo e CPF quando possível.")
        else:
            messages.success(request, "Servidor atualizado com sucesso.")
        return redirect("cadastros:servidores_index")
    return render(
        request,
        "cadastros/servidores/form.html",
        {
            "page_title": "Editar servidor",
            "page_description": "Atualize os dados do servidor. Cargo, CPF, RG e unidade podem ser completados depois; o cadastro fica como rascunho até então.",
            "form": form,
            "submit_label": "Salvar servidor",
            "submit_icon": "check",
            "back_url": reverse("cadastros:servidores_index"),
            "cargos_manage_url": reverse("cadastros:cargos_index"),
            "unidades_manage_url": reverse("cadastros:unidades_index"),
        },
    )


def servidor_delete(request, pk):
    servidor = get_servidor_by_id(pk)
    if request.method != "POST":
        return redirect("cadastros:servidores_index")
    if request.method == "POST":
        try:
            excluir_servidor(servidor)
        except CadastroVinculadoError:
            _vinculo_error(request)
            return redirect("cadastros:servidores_index")
        messages.success(request, "Servidor excluído com sucesso.")
        return redirect("cadastros:servidores_index")


def viaturas_index(request):
    q = request.GET.get("q", "").strip()
    viaturas = listar_viaturas(q=q)
    paginator = Paginator(viaturas, CADASTROS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    rows = [
        apresentar_linha_lista_simples_viatura(
            viatura,
            edit_url=reverse("cadastros:viatura_update", args=[viatura.pk]),
            delete_url=reverse("cadastros:viatura_delete", args=[viatura.pk]),
            delete_modal=True,
        )
        for viatura in page_obj.object_list
    ]
    return _render_listagem(
        request,
        "cadastros/viaturas/index.html",
        {
            "page_title": "Viaturas",
            "page_description": "Viaturas cadastradas para uso operacional.",
            "rows": rows,
            "q": q,
            "page_obj": page_obj,
            "pagination_pages": _pagination_pages(page_obj),
            "page_querystring": urlencode({"q": q}) if q else "",
        },
    )


def viatura_create(request):
    index_url = reverse("cadastros:viaturas_index")
    next_url = _safe_next_url(request, index_url)
    form = ViaturaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        viatura = criar_viatura(form)
        if viatura.status == Viatura.STATUS_RASCUNHO:
            messages.success(request, "Viatura salva como rascunho. Complete modelo, combustível e tipo quando possível.")
        else:
            messages.success(request, "Viatura criada com sucesso.")
        return redirect(next_url)
    return render(
        request,
        "cadastros/viaturas/form.html",
        {
            "page_title": "Nova viatura",
            "page_description": "Apenas a placa é obrigatória — modelo, combustível e tipo podem ser completados depois; o cadastro fica como rascunho até então.",
            "form": form,
            "submit_label": "Criar viatura",
            "submit_icon": "plus",
            "next_url": next_url,
            "back_url": next_url,
            "combustiveis_manage_url": reverse("cadastros:combustiveis_index"),
        },
    )


def viatura_update(request, pk):
    viatura = get_viatura_by_id(pk)
    form = ViaturaForm(request.POST or None, instance=viatura)
    if request.method == "POST" and form.is_valid():
        viatura = atualizar_viatura(viatura, form)
        if viatura.status == Viatura.STATUS_RASCUNHO:
            messages.success(request, "Viatura salva como rascunho. Complete modelo, combustível e tipo quando possível.")
        else:
            messages.success(request, "Viatura atualizada com sucesso.")
        return redirect("cadastros:viaturas_index")
    return render(
        request,
        "cadastros/viaturas/form.html",
        {
            "page_title": "Editar viatura",
            "page_description": "Atualize os dados da viatura. Modelo, combustível e tipo podem ser completados depois; o cadastro fica como rascunho até então.",
            "form": form,
            "submit_label": "Salvar viatura",
            "submit_icon": "check",
            "back_url": reverse("cadastros:viaturas_index"),
            "combustiveis_manage_url": reverse("cadastros:combustiveis_index"),
        },
    )


def configuracao_sistema(request):
    from django.conf import settings

    from eventos.models import Evento
    from integracoes.google_drive.models import (
        DriveArquivo,
        DriveCredenciais,
        DriveReorganizacaoJob,
    )
    from integracoes.google_drive import status as drive_status
    from integracoes.google_drive.services import escopo_faltante, esta_autorizado, get_pasta_raiz_id

    from .models import ConfiguracaoSistema

    obj = ConfiguracaoSistema.get_singleton()
    is_post_dados = request.method == "POST" and request.POST.get("form_id") != "destinatarios"
    is_post_destinatarios = request.method == "POST" and request.POST.get("form_id") == "destinatarios"

    post_data = request.POST if is_post_dados else None
    form = ConfiguracaoSistemaForm(post_data, instance=obj)
    assinaturas_form = ConfiguracaoAssinaturasForm(post_data, configuracao=obj)
    destinatario_form = ConfiguracaoDestinatarioForm(
        request.POST if is_post_destinatarios else None, instance=obj,
    )

    if is_post_dados and form.is_valid() and assinaturas_form.is_valid():
        _, cidade_resolvida = salvar_configuracao_sistema(form)
        assinaturas_form.save(obj)
        if (
            "uf" in form.cleaned_data
            and (form.cleaned_data.get("uf") or form.cleaned_data.get("cidade_endereco"))
            and not cidade_resolvida
        ):
            messages.warning(
                request,
                "Base geográfica não importada ou cidade não encontrada; cidade sede padrão não foi definida.",
            )
        messages.success(request, "Configurações salvas com sucesso.")
        return redirect("cadastros:configuracao")

    if is_post_destinatarios and destinatario_form.is_valid():
        destinatario_form.save()
        messages.success(request, "Destinatário salvo com sucesso.")
        return redirect("cadastros:configuracao")

    cfg_drive = getattr(settings, "GOOGLE_DRIVE", {})
    drive_creds = DriveCredenciais.objects.first()
    drive_modo = cfg_drive.get("MODO", "mock").lower()
    drive_autorizado = esta_autorizado()
    drive_pasta_raiz_id = get_pasta_raiz_id()
    return render(
        request,
        "cadastros/configuracao/form.html",
        {
            "page_title": "Configurações do sistema",
            "page_description": "Unidade, cidade em documentos e assinantes padrão por tipo.",
            "form": form,
            "assinaturas_form": assinaturas_form,
            "destinatario_form": destinatario_form,
            "submit_label": "Salvar configuração",
            "submit_icon": "check",
            "back_url": reverse("core:dashboard"),
            # Google Drive
            "drive_autorizado": drive_autorizado,
            "drive_creds": drive_creds,
            "drive_escopo_faltante": escopo_faltante(),
            "drive_pasta_raiz_id": drive_pasta_raiz_id,
            "drive_pasta_raiz_nome": drive_creds.pasta_raiz_nome if drive_creds else "",
            "drive_total_arquivos": DriveArquivo.objects.count(),
            "drive_modo_ativo": drive_modo != "mock",
            # Reorganização em massa
            "drive_pode_reorganizar": bool(drive_pasta_raiz_id)
            and (drive_autorizado or drive_modo == "mock"),
            "drive_total_eventos": Evento.objects.count(),
            "drive_job_reorg": DriveReorganizacaoJob.objects.order_by("-iniciado_em").first(),
            # Pendências (falhas de envio ao Drive)
            "drive_total_pendencias": drive_status.contagem_pendencias(),
            "drive_pendencias": drive_status.listar_pendencias_detalhadas(limite=20),
        },
    )


def api_consulta_cep(request, cep):
    cep_limpo = only_digits(cep)
    if len(cep_limpo) != 8:
        return JsonResponse({"erro": "CEP deve ter 8 dígitos."}, status=400)

    try:
        payload = consultar_cep(cep_limpo)
    except ViaCEPServiceError:
        return JsonResponse({"erro": "Erro ao consultar serviço externo de CEP."}, status=502)
    except ViaCEPNotFoundError:
        return JsonResponse({"erro": "CEP não encontrado."}, status=404)

    return JsonResponse(payload)


def viatura_delete(request, pk):
    viatura = get_viatura_by_id(pk)
    if request.method == "POST":
        try:
            excluir_viatura(viatura)
        except CadastroVinculadoError:
            _vinculo_error(request)
            return redirect("cadastros:viaturas_index")
        messages.success(request, "Viatura excluída com sucesso.")
        return redirect("cadastros:viaturas_index")
    return render(
        request,
        "cadastros/viaturas/confirm_delete.html",
        {
            "page_title": "Excluir viatura",
            "page_description": "Esta ação excluirá o cadastro. Se houver vínculos com outros registros, a exclusão será bloqueada.",
            "object": viatura,
            "back_url": reverse("cadastros:viaturas_index"),
        },
    )
