"""Escrita da administração de áreas e contas.

Os três formulários já encapsulam a regra (o `UsuarioAreaCreationForm` cria a
conta e o vínculo padrão numa transação só). O service é a fronteira que a view
chama, mantendo `form.save()` fora dela.
"""


def criar_area(form):
    return form.save()


def criar_usuario(form):
    """Cria a conta e o vínculo inicial — a primeira área nasce como padrão."""
    return form.save()


def vincular_usuario(form):
    """Vincula uma conta existente a outra área, sem mexer na área padrão dela."""
    return form.save()
