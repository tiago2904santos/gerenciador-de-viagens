"""Builders do entity card global (components/ui/lists/entity_card*.html).

As views/presenters montam as partes comuns do card (cabeçalho, chips e rodapé
de ações) com estes helpers; o miolo específico de cada domínio continua num
partial próprio passado via body_template.
"""


def header_item(label, value, *, wide=False, wrap=False, value_class=""):
    return {"label": label, "value": value, "wide": wide, "wrap": wrap, "value_class": value_class}


def chip(tone, label):
    return {"tone": tone, "label": label}


def header(items, chips=None):
    return {"items": items, "chips": chips or []}


def menu_link(href, title, description, icon, tone, *, target_blank=False, download=False):
    return {
        "type": "link",
        "href": href,
        "title": title,
        "description": description,
        "icon": icon,
        "tone": tone,
        "target_blank": target_blank,
        "download": download,
    }


def menu_post(action_url, title, description, icon, icon_tone):
    """Item que submete um form POST (ex.: retificar/complementar)."""
    return {
        "type": "post",
        "action_url": action_url,
        "title": title,
        "description": description,
        "icon": icon,
        "icon_tone": icon_tone,
    }


def menu_delete(url, label, *, title="Excluir", description="Remover permanentemente quando permitido"):
    return {"type": "delete", "url": url, "label": label, "title": title, "description": description}


def menu_cancel(url, label, *, title="Cancelar", description="Interromper o fluxo mantendo o histórico"):
    return {"type": "cancel", "url": url, "label": label, "title": title, "description": description}


def menu_attach_signed(url, doc_label, *, assinado=False, current_name="", current_view_url="", current_remove_url=""):
    return {
        "type": "attach_signed",
        "url": url,
        "doc_label": doc_label,
        "assinado": assinado,
        "current_name": current_name,
        "current_view_url": current_view_url,
        "current_remove_url": current_remove_url,
    }


def menu(menu_id, title, subtitle, items, *, icon="folder", trigger_icon="folder",
         trigger_variant="settings", trigger_aria="", trigger_tooltip="Visualizar e baixar",
         trigger_state_class=""):
    """Botão-gatilho + menu rico (cv-action-menu--rich)."""
    return {
        "id": menu_id,
        "title": title,
        "subtitle": subtitle,
        "icon": icon,
        "items": items,
        "trigger_icon": trigger_icon,
        "trigger_variant": trigger_variant,
        "trigger_aria": trigger_aria or title,
        "trigger_tooltip": trigger_tooltip,
        "trigger_state_class": trigger_state_class,
    }


def documents_menu(menu_id, subtitle, *, title, view_url=None, pdf_url=None, docx_url=None,
                   view_title="Visualizar documento", view_description="Abrir o documento no navegador",
                   pdf_description="Documento pronto para impressão",
                   docx_description="Arquivo editável do documento",
                   trigger_aria="", extra_items=None):
    """Menu padrão Visualizar/PDF/DOCX usado no rodapé dos cards."""
    items = []
    if view_url:
        items.append(menu_link(view_url, view_title, view_description, "eye", "preview", target_blank=True))
    if pdf_url:
        items.append(menu_link(pdf_url, "Baixar PDF", pdf_description, "pdf", "pdf", download=True))
    if docx_url:
        items.append(menu_link(docx_url, "Baixar DOCX", docx_description, "docx", "docx", download=True))
    items.extend(extra_items or [])
    return menu(menu_id, title, subtitle, items, trigger_aria=trigger_aria)


def footer(*, edit_url=None, edit_aria="Editar", edit_tooltip="Editar", menus=None,
           delete_url=None, delete_aria="Excluir", delete_modal_url=None, delete_modal_label="",
           delete_modal_title="", danger_menus=None):
    """Rodapé de ações: grupo principal (editar + menus) e grupo de perigo.

    delete_url → link simples; delete_modal_url → botão que abre o modal global.
    danger_menus → menus ricos no grupo de perigo (ex.: "Mais ações" do ofício).
    """
    return {
        "edit_url": edit_url,
        "edit_aria": edit_aria,
        "edit_tooltip": edit_tooltip,
        "menus": menus or [],
        "delete_url": delete_url,
        "delete_aria": delete_aria,
        "delete_modal_url": delete_modal_url,
        "delete_modal_label": delete_modal_label,
        "delete_modal_title": delete_modal_title,
        "danger_menus": danger_menus or [],
    }
