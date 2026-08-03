import csv
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse

from core.retorno import com_next
from core.retorno import next_valido
from core.retorno import voltar_para
from core.utils.masks import only_digits
from .catalogs import cargo_delete  # noqa: F401  (re-export para urls.py)
from .catalogs import cargo_set_default  # noqa: F401
from .catalogs import cargo_update  # noqa: F401
from .catalogs import cargos_index  # noqa: F401
from .catalogs import combustivel_delete  # noqa: F401
from .catalogs import combustivel_set_default  # noqa: F401
from .catalogs import combustivel_update  # noqa: F401
from .catalogs import combustiveis_index  # noqa: F401
from .catalogs import estado_delete  # noqa: F401
from .catalogs import estado_update  # noqa: F401
from .catalogs import estados_index  # noqa: F401
from .catalogs import unidade_delete  # noqa: F401
from .catalogs import unidade_update  # noqa: F401
from .catalogs import unidades_index  # noqa: F401
from .models import Servidor
from .models import Viatura
from .forms import CidadeForm
from .forms import ConfiguracaoAssinaturasForm
from .forms import ConfiguracaoDestinatarioForm
from .forms import ConfiguracaoSistemaForm
from .forms import ServidorForm
from .forms import TabelaDiariaForm
from .forms import ViaturaForm
from .presenters import apresentar_linha_lista_simples_cidade
from .presenters import apresentar_linha_lista_simples_servidor
from .presenters import apresentar_linha_lista_simples_viatura
from .selectors import cargos_mais_frequentes_servidores
from .selectors import combustiveis_mais_frequentes_viaturas
from .selectors import get_cargo_by_id
from .selectors import get_combustivel_by_id
from .selectors import get_configuracao_sistema
from .selectors import get_servidor_by_id
from .selectors import get_unidade_by_id
from .selectors import get_viatura_by_id
from .selectors import listar_cidades
from .selectors import listar_servidores
from .selectors import listar_tabelas_diaria
from .selectors import listar_viaturas
from .services import atualizar_servidor
from .services import atualizar_viatura
from .services import CadastroVinculadoError
from .services import criar_cidade
from .services import criar_servidor
from .services import criar_viatura
from .services import excluir_servidor
from .services import excluir_viatura
from .services import salvar_configuracao_sistema
from .services import consultar_cep
from .services_via_cep import ViaCEPNotFoundError
from .services_via_cep import ViaCEPServiceError


CADASTROS_PER_PAGE = 15


def cidades_index(request):
    q = request.GET.get("q", "").strip()
    form = CidadeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_cidade(form)
        messages.success(request, "Cidade criada com sucesso.")
        return redirect("cadastros:cidades_index")
    cidades = listar_cidades(q=q)
    paginator = Paginator(cidades, CADASTROS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    rows = [
        apresentar_linha_lista_simples_cidade(cidade)
        for cidade in page_obj.object_list
    ]
    return _render_listagem(
        request,
        "cadastros/cidades/index.html",
        {
            "page_title": "Cidades",
            "page_description": "Base geográfica utilizada nos roteiros e documentos.",
            "rows": rows,
            "q": q,
            "quick_add_form": form,
            "page_obj": page_obj,
            "pagination_pages": _pagination_pages(page_obj),
            "page_querystring": urlencode({"q": q}) if q else "",
        },
    )


def cidades_export_csv(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="cidades.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["Cidade", "UF"])
    for cidade in listar_cidades():
        writer.writerow([cidade.nome, cidade.uf])
    return response
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




def _validated_next(request):
    """Fachada de `core.retorno.next_valido` (`NOVO-15`)."""
    return next_valido(request)


def _url_with_next(url, next_url):
    """Fachada de `core.retorno.com_next` (`NOVO-15`)."""
    return com_next(url, next_url)


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


def _servidor_cargo_id(request):
    raw = (request.GET.get("cargo") or "").strip()
    if not raw.isdigit():
        return None
    try:
        return get_cargo_by_id(int(raw)).pk
    except Http404:
        return None


def _build_servidor_cargo_abas(*, cargo_atual, top_cargos, q, next_url):
    """Abas Todos + top cargos; contagens respeitam a busca atual."""
    index_url = reverse("cadastros:servidores_index")
    preserved = []
    if q:
        preserved.append(("q", q))
    if next_url:
        preserved.append(("next", next_url))

    def _url(cargo_pk=None):
        params = list(preserved)
        if cargo_pk:
            params.append(("cargo", cargo_pk))
        query = urlencode(params)
        return f"{index_url}?{query}" if query else index_url

    base_qs = listar_servidores(q=q)
    abas = [
        {
            "key": "",
            "label": "Todos",
            "count": base_qs.count(),
            "url": _url(),
            "is_active": cargo_atual is None,
        }
    ]
    for cargo in top_cargos:
        abas.append(
            {
                "key": str(cargo.pk),
                "label": cargo.nome,
                "count": base_qs.filter(cargo_id=cargo.pk).count(),
                "url": _url(cargo.pk),
                "is_active": cargo_atual == cargo.pk,
            }
        )
    return abas


def servidores_index(request):
    q = request.GET.get("q", "").strip()
    next_url = _validated_next(request)
    cargo_id = _servidor_cargo_id(request)
    top_cargos = cargos_mais_frequentes_servidores(limit=3)
    servidores = listar_servidores(q=q, cargo_id=cargo_id)
    paginator = Paginator(servidores, SERVIDORES_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    rows = [
        apresentar_linha_lista_simples_servidor(
            servidor,
            edit_url=reverse("cadastros:servidor_update", args=[servidor.pk]),
            delete_url=_url_with_next(reverse("cadastros:servidor_delete", args=[servidor.pk]), next_url),
            delete_modal=True,
        )
        for servidor in page_obj.object_list
    ]
    page_params = {}
    if q:
        page_params["q"] = q
    if cargo_id:
        page_params["cargo"] = cargo_id
    if next_url:
        page_params["next"] = next_url
    abas = _build_servidor_cargo_abas(
        cargo_atual=cargo_id,
        top_cargos=top_cargos,
        q=q,
        next_url=next_url,
    ) if top_cargos else None
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
            "page_querystring": urlencode(page_params) if page_params else "",
            "back_url": next_url or None,
            "back_label": "Voltar à viatura",
            "next_url": next_url,
            "abas": abas,
            "tabs_aria_label": "Filtrar servidores por cargo",
            "cargo_filter": cargo_id or "",
        },
    )


def servidor_create(request):
    index_url = reverse("cadastros:servidores_index")
    next_url = voltar_para(request, index_url)
    form = ServidorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        servidor = criar_servidor(form)
        if servidor.status == Servidor.STATUS_RASCUNHO:
            messages.success(request, "Servidor salvo como rascunho. Complete cargo e CPF quando possível.")
        else:
            messages.success(request, "Servidor criado com sucesso.")
        return redirect(next_url)
    own_url = reverse("cadastros:servidor_create")
    return render(
        request,
        "cadastros/servidores/form.html",
        {
            "page_title": "Novo servidor",
            "page_description": "Apenas o nome é obrigatório — cargo, CPF, RG e unidade podem ser completados depois; o cadastro fica como rascunho até então.",
            "flow_eyebrow": "CADASTROS",
            "flow_back_label": "Voltar",
            "flow_back_url": next_url,
            "form": form,
            "submit_label": "Criar servidor",
            "submit_icon": "plus",
            "next_url": next_url,
            "back_url": next_url,
            "cargos_manage_url": _url_with_next(reverse("cadastros:cargos_index"), own_url),
            "unidades_manage_url": _url_with_next(reverse("cadastros:unidades_index"), own_url),
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
    own_url = reverse("cadastros:servidor_update", args=[pk])
    return render(
        request,
        "cadastros/servidores/form.html",
        {
            "page_title": "Editar servidor",
            "page_description": "Atualize os dados do servidor. Cargo, CPF, RG e unidade podem ser completados depois; o cadastro fica como rascunho até então.",
            "flow_eyebrow": "CADASTROS",
            "flow_back_label": "Voltar",
            "flow_back_url": reverse("cadastros:servidores_index"),
            "form": form,
            "submit_label": "Salvar servidor",
            "submit_icon": "check",
            "back_url": reverse("cadastros:servidores_index"),
            "cargos_manage_url": _url_with_next(reverse("cadastros:cargos_index"), own_url),
            "unidades_manage_url": _url_with_next(reverse("cadastros:unidades_index"), own_url),
        },
    )


def servidor_delete(request, pk):
    servidor = get_servidor_by_id(pk)
    redirect_url = _url_with_next(reverse("cadastros:servidores_index"), _validated_next(request))
    if request.method != "POST":
        return redirect(redirect_url)
    if request.method == "POST":
        try:
            excluir_servidor(servidor)
        except CadastroVinculadoError:
            _vinculo_error(request)
            return redirect(redirect_url)
        messages.success(request, "Servidor excluído com sucesso.")
        return redirect(redirect_url)


def viaturas_index(request):
    q = request.GET.get("q", "").strip()
    combustivel_id = _viatura_combustivel_id(request)
    unidade_id = None if combustivel_id else _viatura_unidade_id(request)
    unidade_cfg = _unidade_da_configuracao()
    top_combustiveis = combustiveis_mais_frequentes_viaturas(limit=3)
    viaturas = listar_viaturas(q=q, combustivel_id=combustivel_id, unidade_id=unidade_id)
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
    page_params = {}
    if q:
        page_params["q"] = q
    if combustivel_id:
        page_params["combustivel"] = combustivel_id
    elif unidade_id:
        page_params["unidade"] = unidade_id
    abas = _build_viatura_filtro_abas(
        combustivel_atual=combustivel_id,
        unidade_atual=unidade_id,
        unidade_cfg=unidade_cfg,
        top_combustiveis=top_combustiveis,
        q=q,
    )
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
            "page_querystring": urlencode(page_params) if page_params else "",
            "abas": abas,
            "tabs_aria_label": "Filtrar viaturas por unidade ou combustível",
            "combustivel_filter": combustivel_id or "",
            "unidade_filter": unidade_id or "",
        },
    )


def _unidade_da_configuracao():
    cfg = get_configuracao_sistema()
    if not cfg or not cfg.unidade_id:
        return None
    return cfg.unidade


def _viatura_combustivel_id(request):
    raw = (request.GET.get("combustivel") or "").strip()
    if not raw.isdigit():
        return None
    try:
        return get_combustivel_by_id(int(raw)).pk
    except Http404:
        return None


def _viatura_unidade_id(request):
    raw = (request.GET.get("unidade") or "").strip()
    if not raw.isdigit():
        return None
    try:
        return get_unidade_by_id(int(raw)).pk
    except Http404:
        return None


def _build_viatura_filtro_abas(*, combustivel_atual, unidade_atual, unidade_cfg, top_combustiveis, q):
    """Abas Todos + unidade da config + top combustíveis."""
    if not unidade_cfg and not top_combustiveis:
        return None

    index_url = reverse("cadastros:viaturas_index")
    preserved = [("q", q)] if q else []

    def _url(**extra):
        params = list(preserved)
        params.extend((k, v) for k, v in extra.items() if v)
        query = urlencode(params)
        return f"{index_url}?{query}" if query else index_url

    base_qs = listar_viaturas(q=q)
    abas = [
        {
            "key": "",
            "label": "Todos",
            "count": base_qs.count(),
            "url": _url(),
            "is_active": combustivel_atual is None and unidade_atual is None,
        }
    ]
    if unidade_cfg:
        label = (unidade_cfg.sigla or unidade_cfg.nome or "Unidade").strip()
        abas.append(
            {
                "key": f"unidade-{unidade_cfg.pk}",
                "label": label,
                "count": base_qs.filter(unidade_id=unidade_cfg.pk).count(),
                "url": _url(unidade=unidade_cfg.pk),
                "is_active": unidade_atual == unidade_cfg.pk,
            }
        )
    for combustivel in top_combustiveis:
        abas.append(
            {
                "key": f"combustivel-{combustivel.pk}",
                "label": combustivel.nome,
                "count": base_qs.filter(combustivel_id=combustivel.pk).count(),
                "url": _url(combustivel=combustivel.pk),
                "is_active": combustivel_atual == combustivel.pk,
            }
        )
    return abas


def viatura_create(request):
    index_url = reverse("cadastros:viaturas_index")
    next_url = voltar_para(request, index_url)
    form = ViaturaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        viatura = criar_viatura(form)
        if viatura.status == Viatura.STATUS_RASCUNHO:
            messages.success(request, "Viatura salva como rascunho. Complete modelo, combustível e tipo quando possível.")
        else:
            messages.success(request, "Viatura criada com sucesso.")
        return redirect(next_url)
    own_url = reverse("cadastros:viatura_create")
    return render(
        request,
        "cadastros/viaturas/form.html",
        {
            "page_title": "Nova viatura",
            "page_description": "Apenas a placa é obrigatória — modelo, combustível e tipo podem ser completados depois; o cadastro fica como rascunho até então.",
            "flow_eyebrow": "CADASTROS",
            "flow_back_label": "Voltar",
            "flow_back_url": next_url,
            "form": form,
            "submit_label": "Criar viatura",
            "submit_icon": "plus",
            "next_url": next_url,
            "back_url": next_url,
            "combustiveis_manage_url": _url_with_next(reverse("cadastros:combustiveis_index"), own_url),
            "unidades_manage_url": _url_with_next(reverse("cadastros:unidades_index"), own_url),
            "servidores_manage_url": _url_with_next(reverse("cadastros:servidores_index"), own_url),
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
    own_url = reverse("cadastros:viatura_update", args=[pk])
    return render(
        request,
        "cadastros/viaturas/form.html",
        {
            "page_title": "Editar viatura",
            "page_description": "Atualize os dados da viatura. Modelo, combustível e tipo podem ser completados depois; o cadastro fica como rascunho até então.",
            "flow_eyebrow": "CADASTROS",
            "flow_back_label": "Voltar",
            "flow_back_url": reverse("cadastros:viaturas_index"),
            "form": form,
            "submit_label": "Salvar viatura",
            "submit_icon": "check",
            "back_url": reverse("cadastros:viaturas_index"),
            "combustiveis_manage_url": _url_with_next(reverse("cadastros:combustiveis_index"), own_url),
            "unidades_manage_url": _url_with_next(reverse("cadastros:unidades_index"), own_url),
            "servidores_manage_url": _url_with_next(reverse("cadastros:servidores_index"), own_url),
        },
    )


def configuracao_sistema(request):
    from .models import ConfiguracaoSistema

    obj = ConfiguracaoSistema.get_for_area(getattr(request, "area", None))
    form_id = request.POST.get("form_id") if request.method == "POST" else None
    is_post_dados = request.method == "POST" and form_id not in {"destinatarios", "diarias"}
    is_post_destinatarios = form_id == "destinatarios"
    is_post_diarias = form_id == "diarias"

    post_data = request.POST if is_post_dados else None
    form = ConfiguracaoSistemaForm(post_data, instance=obj)
    assinaturas_form = ConfiguracaoAssinaturasForm(post_data, configuracao=obj)
    destinatario_form = ConfiguracaoDestinatarioForm(
        request.POST if is_post_destinatarios else None, instance=obj,
    )
    diaria_form = TabelaDiariaForm(request.POST if is_post_diarias else None)

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

    if is_post_diarias and diaria_form.is_valid():
        tabela = diaria_form.save()
        messages.success(
            request,
            f"Valores de {tabela.get_faixa_display()} valendo a partir de "
            f"{tabela.vigencia_inicio:%d/%m/%Y}. Roteiros anteriores mantêm o valor da época.",
        )
        return redirect("cadastros:configuracao")

    return render(
        request,
        "cadastros/configuracao/form.html",
        {
            "page_title": "Configurações do sistema",
            "page_description": "Unidade, cidade em documentos e assinantes padrão por tipo.",
            "flow_eyebrow": "CADASTROS",
            "flow_back_label": "Voltar",
            "flow_back_url": reverse("core:dashboard"),
            "form": form,
            "assinaturas_form": assinaturas_form,
            "destinatario_form": destinatario_form,
            "diaria_form": diaria_form,
            "diarias_vigentes": listar_tabelas_diaria(),
            "submit_label": "Salvar configuração",
            "submit_icon": "check",
            "back_url": reverse("core:dashboard"),
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
            "flow_eyebrow": "CADASTROS",
            "flow_back_label": "Voltar",
            "flow_back_url": reverse("cadastros:viaturas_index"),
            "object": viatura,
            "back_url": reverse("cadastros:viaturas_index"),
        },
    )
