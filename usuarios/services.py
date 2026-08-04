"""Escrita da administração de áreas e contas.

Os formulários encapsulam a regra (o `UsuarioAreaCreationForm` cria a
conta e o vínculo padrão numa transação só). O service é a fronteira que a
view chama, mantendo `form.save()` fora dela.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError


class UsuarioNaoPodeSerExcluido(ValidationError):
    """Exclusão bloqueada por regra de negócio ou vínculo protegido."""


class AreaNaoPodeSerExcluida(ValidationError):
    """Exclusão bloqueada por vínculos de conta ou registros protegidos."""


def criar_area(form):
    return form.save()


def atualizar_area(form):
    return form.save()


def excluir_area(area):
    """Remove a área. Bloqueia se houver contas vinculadas ou dados protegidos."""
    if area.vinculos_usuario.exists():
        raise AreaNaoPodeSerExcluida(
            "Não é possível excluir uma área com usuários vinculados. "
            "Remova os vínculos antes."
        )

    try:
        area.delete()
    except ProtectedError as exc:
        raise AreaNaoPodeSerExcluida(
            "Não foi possível excluir a área porque há registros vinculados a ela."
        ) from exc


def criar_usuario(form):
    """Cria a conta e o vínculo inicial — a primeira área nasce como padrão."""
    return form.save()


def atualizar_usuario(form):
    return form.save()


def vincular_usuario(form):
    """Vincula uma conta existente a outra área, sem mexer na área padrão dela."""
    return form.save()


def remover_vinculo(vinculo):
    """Remove o acesso da conta à área (unique exige hard delete para religar)."""
    vinculo.delete()


def excluir_usuario(usuario, *, solicitante):
    """Remove a conta. Não permite autoexclusão nem apagar o último administrador."""
    if solicitante is not None and usuario.pk == solicitante.pk:
        raise UsuarioNaoPodeSerExcluido("Você não pode excluir a própria conta.")

    if usuario.is_staff or usuario.is_superuser:
        User = get_user_model()
        restantes = (
            User.objects.filter(is_active=True, is_staff=True)
            .exclude(pk=usuario.pk)
            .count()
        )
        if restantes == 0:
            raise UsuarioNaoPodeSerExcluido(
                "Não é possível excluir o último administrador do sistema."
            )

    try:
        usuario.delete()
    except ProtectedError as exc:
        raise UsuarioNaoPodeSerExcluido(
            "Não foi possível excluir a conta porque há registros vinculados a ela."
        ) from exc

