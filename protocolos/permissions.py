"""Permissões da Central de Protocolos.

MVP: qualquer usuário autenticado pode operar (o login já é exigido pelo
middleware quando ``LOGIN_ENFORCED``). As funções abaixo centralizam a regra
para que seja fácil restringir por grupo/permissão no futuro, sem espalhar
``if`` pelas views.
"""

from __future__ import annotations


def _autorizado(user) -> bool:
    return bool(user and user.is_authenticated)


def pode_visualizar(user) -> bool:
    return _autorizado(user)


def pode_criar_protocolo(user) -> bool:
    return _autorizado(user)


def pode_tramitar(user) -> bool:
    return _autorizado(user)


def pode_solicitar_assinatura(user) -> bool:
    return _autorizado(user)


def pode_enviar_documento(user) -> bool:
    return _autorizado(user)
