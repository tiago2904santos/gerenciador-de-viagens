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
from .forms import AreaTrabalhoForm
from .forms import UsuarioAreaCreationForm
from .forms import VinculoUsuarioAreaForm
from .presenters import apresentar_linha_lista_simples_area
from .presenters import apresentar_linha_lista_simples_usuario


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
    """Lista de contas — uma linha por pessoa, com as áreas na própria linha."""
    q = request.GET.get("q", "").strip()

    usuarios = selectors.listar_usuarios(q=q)
    paginator = Paginator(usuarios, ADMIN_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    rows = [apresentar_linha_lista_simples_usuario(usuario) for usuario in page_obj.object_list]

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
            "novo_usuario_url": reverse("usuarios:usuario_create"),
            "vincular_url": reverse("usuarios:vinculo_create"),
            # A página já passa por `somente_administrador`, permissão mais forte
            # que editor — sem isto o staff sem vínculo não veria o botão de criar.
            "can_edit_area": True,
            **contadores,
        },
    )


@somente_administrador
def areas_index(request):
    """Lista de áreas — sigla, nome e quantas contas têm acesso."""
    q = request.GET.get("q", "").strip()

    areas = selectors.listar_areas(q=q)
    paginator = Paginator(areas, ADMIN_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    rows = [apresentar_linha_lista_simples_area(area) for area in page_obj.object_list]

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
            "nova_area_url": reverse("usuarios:area_create"),
            # Mesma razão do `index`: o gate da página já é administrador.
            "can_edit_area": True,
            **contadores,
        },
    )


@somente_administrador
def usuario_create(request):
    form = UsuarioAreaCreationForm(request.POST or None, prefix="usuario")
    if request.method == "POST" and form.is_valid():
        user = services.criar_usuario(form)
        messages.success(request, f"Usuário {user.get_username()} criado e vinculado à área.")
        return redirect("usuarios:index")

    return render(
        request,
        "usuarios/form.html",
        {
            "page_title": "Novo usuário",
            "flow_eyebrow": "Administração",
            "flow_back_label": "Voltar",
            "flow_back_url": reverse("usuarios:index"),
            "page_description": "Conta, senha e a área em que a pessoa entra por padrão.",
            "usuario_form": form,
            "form": form,
            "card_title": "Dados do usuário",
            "body_template": "usuarios/partials/_criar_usuario_fields.html",
            "submit_label": "Criar usuário",
        },
    )


@somente_administrador
def area_create(request):
    form = AreaTrabalhoForm(request.POST or None, prefix="area")
    if request.method == "POST" and form.is_valid():
        area = services.criar_area(form)
        messages.success(request, f"Área {area.sigla} criada com sucesso.")
        return redirect("usuarios:areas_index")

    return render(
        request,
        "usuarios/form.html",
        {
            "page_title": "Nova área",
            "flow_eyebrow": "Administração",
            "flow_back_label": "Voltar",
            "flow_back_url": reverse("usuarios:areas_index"),
            "page_description": "Nome e sigla da unidade de trabalho.",
            "area_form": form,
            "form": form,
            "card_title": "Dados da área",
            "body_template": "usuarios/partials/_criar_area_fields.html",
            "submit_label": "Criar área",
        },
    )


@somente_administrador
def vinculo_create(request):
    form = VinculoUsuarioAreaForm(request.POST or None, prefix="vinculo")
    if request.method == "POST" and form.is_valid():
        vinculo = services.vincular_usuario(form)
        messages.success(request, f"Vínculo de {vinculo.usuario} com {vinculo.area} salvo.")
        return redirect("usuarios:index")

    return render(
        request,
        "usuarios/form.html",
        {
            "page_title": "Vincular usuário",
            "flow_eyebrow": "Administração",
            "flow_back_label": "Voltar",
            "flow_back_url": reverse("usuarios:index"),
            "page_description": "Dá a uma conta existente acesso a outra área.",
            "vinculo_form": form,
            "form": form,
            "card_title": "Dados do vínculo",
            "body_template": "usuarios/partials/_vincular_usuario_fields.html",
            "submit_label": "Salvar vínculo",
        },
    )
