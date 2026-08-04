"""Consultas de áreas de trabalho e contas.

As duas listagens da administração (`Usuários` e `Áreas`) leem tudo por aqui: a
view não monta queryset. A busca por `q` fica centralizada em `_filtro_busca_*`
e não é reescrita em cada chamada.
"""

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.db.models import Prefetch
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import AreaTrabalho
from .models import VinculoUsuarioArea


def queryset_areas_base():
    """Áreas com a contagem de vínculos já resolvida (evita N+1 na listagem)."""
    return AreaTrabalho.objects.annotate(total_vinculos=Count("vinculos_usuario"))


def _filtro_busca_areas(q):
    return Q(sigla__icontains=q) | Q(nome__icontains=q)


def listar_areas(q=""):
    queryset = queryset_areas_base()
    if q:
        queryset = queryset.filter(_filtro_busca_areas(q))
    return queryset.order_by("sigla")


def queryset_usuarios_base():
    """Contas com os vínculos pré-carregados, área padrão primeiro.

    A ordenação do `Prefetch` é o que faz a linha da lista sair com a área
    padrão à frente das demais — o presenter não reordena.
    """
    vinculos = (
        VinculoUsuarioArea.objects
        .select_related("area")
        .order_by("-area_padrao", "area__sigla")
    )
    return get_user_model().objects.prefetch_related(
        Prefetch("vinculos_area", queryset=vinculos)
    )


def _filtro_busca_usuarios(q):
    return (
        Q(username__icontains=q)
        | Q(first_name__icontains=q)
        | Q(last_name__icontains=q)
        | Q(email__icontains=q)
        | Q(vinculos_area__area__sigla__icontains=q)
        | Q(vinculos_area__area__nome__icontains=q)
        | Q(vinculos_area__papel__icontains=q)
    )


def listar_usuarios(q=""):
    queryset = queryset_usuarios_base()
    if q:
        # `distinct` é obrigatório: o filtro atravessa vinculos_area e uma conta
        # com duas áreas casaria duas vezes na mesma busca.
        queryset = queryset.filter(_filtro_busca_usuarios(q)).distinct()
    return queryset.order_by("first_name", "username")


def contadores_administracao():
    """Os dois números que alimentam o alternador Usuários / Áreas."""
    return {
        "total_areas": AreaTrabalho.objects.count(),
        "total_usuarios": get_user_model().objects.count(),
        "total_vinculos": VinculoUsuarioArea.objects.count(),
    }


def get_area_by_id(pk):
    return get_object_or_404(queryset_areas_base(), pk=pk)


def listar_vinculos_da_area(area, q=""):
    """Contas vinculadas a uma área, com o usuário já carregado."""
    queryset = (
        VinculoUsuarioArea.objects.filter(area=area)
        .select_related("usuario")
        .order_by("usuario__first_name", "usuario__username")
    )
    if q:
        queryset = queryset.filter(
            Q(usuario__username__icontains=q)
            | Q(usuario__first_name__icontains=q)
            | Q(usuario__last_name__icontains=q)
            | Q(usuario__email__icontains=q)
            | Q(papel__icontains=q)
        )
    return queryset


def get_usuario_by_id(pk):
    return get_object_or_404(queryset_usuarios_base(), pk=pk)


def get_vinculo_da_area(area, usuario_id):
    """Vínculo desta conta com esta área, ou `None`.

    `usuario_id` vem cru do POST: um valor não numérico faria o ORM levantar
    `ValueError` em vez de simplesmente não achar nada.
    """
    if not str(usuario_id or "").isdigit():
        return None
    return VinculoUsuarioArea.objects.filter(area=area, usuario_id=usuario_id).first()


def get_vinculo_by_id(pk):
    return get_object_or_404(
        VinculoUsuarioArea.objects.select_related("usuario", "area"),
        pk=pk,
    )
