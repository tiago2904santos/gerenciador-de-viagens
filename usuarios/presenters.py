"""Linhas de listagem da administração, no contrato `cv-record-row`.

Sem HTML e sem consulta: os vínculos chegam pré-carregados pelo
`selectors.queryset_usuarios_base`.
"""

from core.presenters.badges import build_badge
from core.presenters.meta import build_meta


def _iniciais(texto, fallback="??"):
    partes = [parte for parte in str(texto or "").strip().split() if parte]
    if not partes:
        return fallback
    if len(partes) == 1:
        return partes[0][:2].upper()
    return f"{partes[0][0]}{partes[-1][0]}".upper()


def _nome_exibido(usuario):
    return usuario.get_full_name().strip() or usuario.get_username()


def apresentar_linha_lista_simples_area(area):
    """Sigla como título, nome como subtítulo, contagem de contas como fato.

    Sem `avatar`: a inicial de uma sigla é a própria sigla, e repetir "AS" ao
    lado de "ASCOM" só gaguejava a linha.
    """
    total = getattr(area, "total_vinculos", 0)
    badges = []
    if not area.ativa:
        badges.append(build_badge("Inativa", "draft"))
    if total == 0:
        badges.append(build_badge("Sem usuários", "muted"))
    return {
        "title": area.sigla,
        "badges": badges,
        "subtitle": area.nome,
        "search_extra": area.nome,
        "facts": [
            build_meta("Usuários", str(total)),
        ],
    }


def apresentar_linha_lista_simples_usuario(usuario):
    """Uma linha por pessoa: as áreas viram fatos na própria linha.

    A área padrão vem primeiro (ordenação do `Prefetch`) e é a única marcada,
    para que a linha responda "onde essa conta entra por padrão" sem uma coluna
    de chips repetidos.
    """
    vinculos = list(usuario.vinculos_area.all())

    badges = []
    if usuario.is_superuser or usuario.is_staff:
        badges.append(build_badge("Administrador do sistema", "info"))
    if not vinculos:
        badges.append(build_badge("Sem área", "draft"))
    if not usuario.is_active:
        badges.append(build_badge("Inativo", "draft"))

    facts = [
        build_meta(
            vinculo.area.sigla,
            f"{vinculo.get_papel_display()} (padrão)" if vinculo.area_padrao else vinculo.get_papel_display(),
        )
        for vinculo in vinculos
    ]

    username = usuario.get_username()
    email = (usuario.email or "").strip()
    subtitle = f"@{username} · {email}" if email else f"@{username}"

    return {
        "avatar": _iniciais(_nome_exibido(usuario), "US"),
        "title": _nome_exibido(usuario),
        "badges": badges,
        "subtitle": subtitle,
        "search_extra": f"{username} {email}",
        "facts": facts,
    }
