"""Nome de ícone -> símbolo da folha (`PF-01`).

Antes da folha de símbolos, `icon.html` era uma cadeia de 36 condições e um
`else`: nome desconhecido caía no último ramo e desenhava uma interrogação. Com
`<use href="#cv-icon-...">`, um `id` inexistente **não desenha nada** — falha
silenciosa, que é justamente o modo de falha que este refactor passa o tempo
caçando.

Este filtro devolve o comportamento visível: nome conhecido vira ele mesmo,
apelido vira o canônico, e qualquer outra coisa vira `unknown`, que é a mesma
interrogação de antes.

É o primeiro `templatetags` do projeto. A alternativa era duplicar os apelidos
como símbolos na folha e viver sem fallback — mais barato, e pior: um nome errado
vindo do Python (os presenters montam ação com `icon="..."`, e 17 inclusões passam
variável em vez de literal) viraria buraco invisível na tela.

A tupla abaixo é a fonte única do conjunto de ícones;
`core/tests/test_folha_de_icones.py` exige que ela e a folha digam a mesma coisa.
"""

from __future__ import annotations

from django import template
from django.utils.html import format_html

register = template.Library()

#: Um `<symbol id="cv-icon-{{nome}}">` na folha para cada um destes.
ICONES = (
    "check",
    "plus",
    "user-plus",
    "car-plus",
    "home",
    "chevron-down",
    "arrow-right",
    "arrow-left",
    "list",
    "x",
    "ban",
    "more",
    "grip",
    "eye",
    "edit",
    "trash",
    "sign",
    "document",
    "pdf",
    "docx",
    "route",
    "calculator",
    "copy-modern",
    "copy",
    "settings",
    "search",
    "download",
    "link",
    "clipboard-copy",
    "folder",
    "cloud",
    "calendar",
    "sync",
    "archive",
    "unarchive",
    "star",
    "code",
    "whatsapp-modern",
    "whatsapp-business",
    "whatsapp",
)

#: Nomes que o código já usava e que compartilham desenho com outro. Vinham de
#: ramos como `elif icon == "trash" or icon == "delete"`.
APELIDOS = {
    "delete": "trash",
    "drag": "grip",
    "pen": "sign",
    "pencil": "edit",
    "preview": "eye",
    "signature": "sign",
}

DESCONHECIDO = "unknown"


@register.filter
def nome_de_icone(valor) -> str:
    """Devolve um `id` de símbolo que existe na folha, sempre."""
    nome = (valor or "").strip()
    if nome in ICONES:
        return nome
    return APELIDOS.get(nome, DESCONHECIDO)


@register.simple_tag
def icone_svg(valor):
    """Renderiza o invólucro pequeno sem abrir um componente Cotton por ícone."""
    return format_html(
        '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" '
        'focusable="false"><use href="#cv-icon-{}"></use></svg>',
        nome_de_icone(valor),
    )
