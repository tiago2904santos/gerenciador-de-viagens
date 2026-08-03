from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.db.models import Q
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse

from .forms import AreaTrabalhoForm
from .forms import UsuarioAreaCreationForm
from .forms import VinculoUsuarioAreaForm
from .models import AreaTrabalho
from .models import VinculoUsuarioArea


@login_required(login_url="core:login")
def index(request):
    if not request.user.is_staff and not request.user.is_superuser:
        raise PermissionDenied("Apenas administradores podem gerenciar áreas e usuários.")

    area_form = AreaTrabalhoForm(prefix="area")
    usuario_form = UsuarioAreaCreationForm(prefix="usuario")
    vinculo_form = VinculoUsuarioAreaForm(prefix="vinculo")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "criar_area":
            area_form = AreaTrabalhoForm(request.POST, prefix="area")
            if area_form.is_valid():
                area = area_form.save()
                messages.success(request, f"Área {area.sigla} criada com sucesso.")
                return redirect("usuarios:index")
        elif action == "criar_usuario":
            usuario_form = UsuarioAreaCreationForm(request.POST, prefix="usuario")
            if usuario_form.is_valid():
                user = usuario_form.save()
                messages.success(request, f"Usuário {user.get_username()} criado e vinculado à área.")
                return redirect("usuarios:index")
        elif action == "vincular_usuario":
            vinculo_form = VinculoUsuarioAreaForm(request.POST, prefix="vinculo")
            if vinculo_form.is_valid():
                vinculo = vinculo_form.save()
                messages.success(request, f"Vínculo de {vinculo.usuario} com {vinculo.area} salvo.")
                return redirect("usuarios:index")
        else:
            messages.error(request, "Ação administrativa inválida.")

    users_base = get_user_model().objects.prefetch_related("vinculos_area__area")
    areas_base = AreaTrabalho.objects.annotate(total_vinculos=Count("vinculos_usuario"))
    vinculos_base = VinculoUsuarioArea.objects.select_related("usuario", "area")

    total_usuarios = users_base.count()
    total_areas = areas_base.count()
    total_vinculos = vinculos_base.count()

    busca = request.GET.get("q", "").strip()
    areas = areas_base
    vinculos = vinculos_base
    if busca:
        areas = areas.filter(Q(sigla__icontains=busca) | Q(nome__icontains=busca))
        vinculos = vinculos.filter(
            Q(usuario__username__icontains=busca)
            | Q(usuario__first_name__icontains=busca)
            | Q(usuario__last_name__icontains=busca)
            | Q(usuario__email__icontains=busca)
            | Q(area__sigla__icontains=busca)
            | Q(area__nome__icontains=busca)
            | Q(papel__icontains=busca)
        )

    users = users_base.order_by("username")
    areas = areas.order_by("sigla")
    vinculos = (
        vinculos
        .order_by("area__sigla", "usuario__username")
    )

    return render(
        request,
        "usuarios/index.html",
        {
            "page_title": "Áreas e usuários",
            "page_description": "Crie áreas de trabalho, usuários e vínculos de acesso sem usar terminal.",
            "flow_eyebrow": "ADMINISTRAÇÃO",
            "flow_back_label": "Voltar",
            "flow_back_url": reverse("core:dashboard"),
            "area_form": area_form,
            "usuario_form": usuario_form,
            "vinculo_form": vinculo_form,
            "areas": areas,
            "users": users,
            "vinculos": vinculos,
            "busca": busca,
            "total_areas": total_areas,
            "total_usuarios": total_usuarios,
            "total_vinculos": total_vinculos,
        },
    )
