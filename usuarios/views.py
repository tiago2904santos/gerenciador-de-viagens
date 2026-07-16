from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.shortcuts import render

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

    users = get_user_model().objects.prefetch_related("vinculos_area__area").order_by("username")
    areas = AreaTrabalho.objects.prefetch_related("vinculos_usuario").order_by("sigla")
    vinculos = (
        VinculoUsuarioArea.objects.select_related("usuario", "area")
        .order_by("area__sigla", "usuario__username")
    )

    return render(
        request,
        "usuarios/index.html",
        {
            "page_title": "Áreas e usuários",
            "page_description": "Crie áreas de trabalho, usuários e vínculos de acesso sem usar terminal.",
            "area_form": area_form,
            "usuario_form": usuario_form,
            "vinculo_form": vinculo_form,
            "areas": areas,
            "users": users,
            "vinculos": vinculos,
        },
    )
