from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse

from . import selectors
from . import services
from .forms import AreaTrabalhoEditForm
from .forms import AreaTrabalhoForm
from .forms import UsuarioAreaCreationForm
from .forms import UsuarioEditForm
from .forms import VinculoNaAreaForm
from .forms import VinculoUsuarioAreaForm
from .presenters import apresentar_linha_lista_simples_area
from .presenters import apresentar_linha_lista_simples_usuario
from .presenters import apresentar_linha_lista_simples_vinculo


ADMIN_PER_PAGE = 25


def somente_administrador(view):
    """Administração de contas e áreas é exclusiva de staff/superuser."""

    @wraps(view)
    @login_required(login_url="core:login")
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_staff and not request.user.is_superuser:
            raise PermissionDenied("Apenas administradores podem gerenciar áreas e usuários.")
        return view(request, *args, **kwargs)

    return _wrapped


def _pagination_pages(page_obj, *, on_each_side=1, on_ends=1):
    return [
        page_number if isinstance(page_number, int) else "..."
        for page_number in page_obj.paginator.get_elided_page_range(
            page_obj.number, on_each_side=on_each_side, on_ends=on_ends
        )
    ]


def _abas_administracao(*, ativa, contadores):
    """Alternador Usuários / Áreas — o mesmo `cv-segment-toggle` dos Termos.

    É o que amarra as duas listagens: cada uma é uma página inteira, e o
    toggle no cabeçalho é a passagem entre elas.
    """
    return [
        {
            "key": "usuarios",
            "label": "Usuários",
            "count": contadores["total_usuarios"],
            "url": reverse("usuarios:index"),
            "is_active": ativa == "usuarios",
        },
        {
            "key": "areas",
            "label": "Áreas",
            "count": contadores["total_areas"],
            "url": reverse("usuarios:areas_index"),
            "is_active": ativa == "areas",
        },
    ]


@somente_administrador
def index(request):
    """Lista de contas — criação inline (quick-add) no padrão das justificativas."""
    q = request.GET.get("q", "").strip()
    quick_add_form = UsuarioAreaCreationForm(prefix="usuario")

    if request.method == "POST":
        quick_add_form = UsuarioAreaCreationForm(request.POST, prefix="usuario")
        if quick_add_form.is_valid():
            user = services.criar_usuario(quick_add_form)
            messages.success(request, f"Usuário {user.get_username()} criado e vinculado à área.")
            return redirect("usuarios:index")

    usuarios = selectors.listar_usuarios(q=q)
    paginator = Paginator(usuarios, ADMIN_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    vincular_url = reverse("usuarios:vinculo_create")
    rows = [
        apresentar_linha_lista_simples_usuario(
            usuario,
            vincular_url=vincular_url,
            edit_url=reverse("usuarios:usuario_update", args=[usuario.pk]),
            delete_url=(
                None
                if usuario.pk == request.user.pk
                else reverse("usuarios:usuario_delete", args=[usuario.pk])
            ),
        )
        for usuario in page_obj.object_list
    ]

    contadores = selectors.contadores_administracao()

    return render(
        request,
        "usuarios/index.html",
        {
            "page_title": "Usuários",
            "page_description": "Contas do sistema e as áreas a que cada uma tem acesso.",
            "rows": rows,
            "q": q,
            "page_obj": page_obj,
            "pagination_pages": _pagination_pages(page_obj),
            "page_querystring": urlencode({"q": q}) if q else "",
            "abas": _abas_administracao(ativa="usuarios", contadores=contadores),
            "tabs_aria_label": "Alternar entre usuários e áreas",
            "quick_add_form": quick_add_form,
            "vincular_form": VinculoUsuarioAreaForm(prefix="vinculo"),
            # A página já passa por `somente_administrador`, permissão mais forte
            # que editor — sem isto o staff sem vínculo não veria o botão de criar.
            "can_edit_area": True,
            **contadores,
        },
    )


@somente_administrador
def areas_index(request):
    """Lista de áreas — criação inline (quick-add) no padrão das justificativas."""
    q = request.GET.get("q", "").strip()
    quick_add_form = AreaTrabalhoForm(prefix="area")

    if request.method == "POST":
        quick_add_form = AreaTrabalhoForm(request.POST, prefix="area")
        if quick_add_form.is_valid():
            area = services.criar_area(quick_add_form)
            messages.success(request, f"Área {area.sigla} criada com sucesso.")
            return redirect("usuarios:areas_index")

    areas = selectors.listar_areas(q=q)
    paginator = Paginator(areas, ADMIN_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    rows = [
        apresentar_linha_lista_simples_area(
            area,
            edit_url=reverse("usuarios:area_update", args=[area.pk]),
        )
        for area in page_obj.object_list
    ]

    contadores = selectors.contadores_administracao()

    return render(
        request,
        "usuarios/areas/index.html",
        {
            "page_title": "Áreas",
            "page_description": "Unidades de trabalho que isolam os dados do sistema.",
            "rows": rows,
            "q": q,
            "page_obj": page_obj,
            "pagination_pages": _pagination_pages(page_obj),
            "page_querystring": urlencode({"q": q}) if q else "",
            "abas": _abas_administracao(ativa="areas", contadores=contadores),
            "tabs_aria_label": "Alternar entre usuários e áreas",
            "quick_add_form": quick_add_form,
            # Mesma razão do `index`: o gate da página já é administrador.
            "can_edit_area": True,
            **contadores,
        },
    )


@somente_administrador
def area_update(request, pk):
    """Gerenciador da área: dados + contas vinculadas."""
    area = selectors.get_area_by_id(pk)
    form = AreaTrabalhoEditForm(request.POST or None, instance=area, prefix="area")
    vinculo_form = VinculoNaAreaForm(prefix="vinculo", area=area)

    if request.method == "POST" and form.is_valid():
        area = services.atualizar_area(form)
        messages.success(request, f"Área {area.sigla} atualizada com sucesso.")
        return redirect("usuarios:area_update", pk=area.pk)

    vinculos = selectors.listar_vinculos_da_area(area)
    rows = [
        apresentar_linha_lista_simples_vinculo(
            vinculo,
            delete_url=reverse("usuarios:vinculo_delete", args=[vinculo.pk]),
        )
        for vinculo in vinculos
    ]

    return render(
        request,
        "usuarios/areas/form.html",
        {
            "page_title": f"Área {area.sigla}",
            "page_description": "Edite os dados da área e as contas com acesso a ela.",
            "flow_eyebrow": "Administração",
            "flow_back_label": "Voltar",
            "flow_back_url": reverse("usuarios:areas_index"),
            "form": form,
            "area": area,
            "rows": rows,
            "vinculo_form": vinculo_form,
            "vinculo_action_url": reverse("usuarios:vinculo_create_na_area", args=[area.pk]),
            "submit_label": "Salvar área",
            "can_edit_area": True,
        },
    )


@somente_administrador
def usuario_create(request):
    """Compat: redireciona para a lista, onde a criação passou a ser inline."""
    return redirect("usuarios:index")


@somente_administrador
def usuario_update(request, pk):
    """POST do quick-edit na lista. GET só redireciona — sem página dedicada."""
    if request.method != "POST":
        return redirect("usuarios:index")

    usuario = selectors.get_usuario_by_id(pk)
    form = UsuarioEditForm(request.POST, instance=usuario, prefix="usuario")
    if form.is_valid():
        usuario = services.atualizar_usuario(form)
        messages.success(request, f"Usuário {usuario.get_username()} atualizado.")
    else:
        messages.error(request, "Não foi possível salvar o usuário. Confira os dados informados.")
    return redirect("usuarios:index")


@somente_administrador
def usuario_delete(request, pk):
    """Exclui a conta via modal de confirmação da lista."""
    if request.method != "POST":
        return redirect("usuarios:index")

    usuario = selectors.get_usuario_by_id(pk)
    username = usuario.get_username()
    try:
        services.excluir_usuario(usuario, solicitante=request.user)
    except services.UsuarioNaoPodeSerExcluido as exc:
        messages.error(request, exc.messages[0] if exc.messages else str(exc))
        return redirect("usuarios:index")

    messages.success(request, f"Usuário {username} excluído.")
    return redirect("usuarios:index")


@somente_administrador
def area_create(request):
    """Compat: redireciona para a lista, onde a criação passou a ser inline."""
    return redirect("usuarios:areas_index")


@somente_administrador
def vinculo_create(request):
    """POST do modal na lista. GET só redireciona — a página dedicada foi removida."""
    if request.method != "POST":
        return redirect("usuarios:index")

    form = VinculoUsuarioAreaForm(request.POST, prefix="vinculo")
    if form.is_valid():
        vinculo = services.vincular_usuario(form)
        messages.success(request, f"Vínculo de {vinculo.usuario} com {vinculo.area} salvo.")
    else:
        messages.error(
            request,
            "Não foi possível salvar o vínculo. Confira a área e o perfil informados.",
        )
    return redirect("usuarios:index")


@somente_administrador
def vinculo_create_na_area(request, pk):
    """POST do formulário de vínculo dentro do gerenciador da área."""
    area = selectors.get_area_by_id(pk)
    if request.method != "POST":
        return redirect("usuarios:area_update", pk=pk)

    form = VinculoNaAreaForm(request.POST, prefix="vinculo", area=area)
    if form.is_valid():
        vinculo = services.vincular_usuario(form)
        messages.success(request, f"{vinculo.usuario} vinculado à área {area.sigla}.")
    else:
        messages.error(
            request,
            "Não foi possível vincular o usuário. Confira a conta e o perfil.",
        )
    return redirect("usuarios:area_update", pk=pk)


@somente_administrador
def vinculo_delete(request, pk):
    """Remove o vínculo e volta ao gerenciador da área."""
    vinculo = selectors.get_vinculo_by_id(pk)
    area_pk = vinculo.area_id
    if request.method != "POST":
        return redirect("usuarios:area_update", pk=area_pk)

    services.remover_vinculo(vinculo)
    messages.success(request, "Vínculo removido da área.")
    return redirect("usuarios:area_update", pk=area_pk)
