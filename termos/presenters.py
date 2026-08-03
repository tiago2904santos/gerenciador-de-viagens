from core import entity_cards
from core.presenters.meta import build_meta
from core.utils.masks import format_placa


def apresentar_termo_card(
    termo,
    *,
    edit_url="#",
    delete_url="#",
    delete_modal=False,
    pdf_url="",
    docx_url="",
    generico_pdf_url="",
    generico_docx_url="",
    servidor_url_builder=None,
    servidor_view_url_builder=None,
    viatura_view_url="",
    viatura_pdf_url="",
    viatura_docx_url="",
    assinado=False,
    anexar_assinado_url="",
    remover_assinado_url="",
    assinado_nome_original="",
    assinado_view_url="",
):
    """Card do termo, montado por camadas conforme o que estiver preenchido.

    O estado mínimo é destino + período. Servidores e viatura viram faixas
    próprias só quando existem, e cada servidor ganha o menu de download do
    seu termo. `servidor_url_builder(servidor_pk, formato)` devolve a URL.
    """
    from oficios.presenters import _iniciais_nome_servidor

    viatura = termo.viatura_efetiva()
    oficio_label = termo.oficio.numero_formatado if termo.oficio_id else ""
    destino = termo.destino_display
    periodo = termo.periodo_display

    # A viatura do termo decide a variante do template do termo do servidor
    # (COMPLETO_COM_VIATURA x COMPLETO_SEM_VIATURA) — ver
    # termos.services._resolver_variante_termo_cadastro.
    com_viatura = viatura is not None

    servidores_display = []
    for servidor in termo.servidores_efetivos():
        cargo_nome = servidor.cargo.nome if servidor.cargo_id and servidor.cargo else ""
        unidade_nome = str(servidor.unidade) if servidor.unidade_id else ""
        servidores_display.append({
            "servidor_pk": servidor.pk,
            "initials": _iniciais_nome_servidor(servidor.nome),
            "name": servidor.nome,
            "cargo": cargo_nome,
            "unidade": unidade_nome,
            "pdf_url": servidor_url_builder(servidor.pk, "pdf") if servidor_url_builder else "",
            "docx_url": servidor_url_builder(servidor.pk, "docx") if servidor_url_builder else "",
            "view_url": servidor_view_url_builder(servidor.pk) if servidor_view_url_builder else "",
        })

    # A viatura ocupa uma linha na mesma lista dos servidores e se comporta
    # como um deles; o download dela e o termo sem servidor, so com o veiculo.
    viatura_row = None
    if viatura is not None:
        placa_fmt = format_placa(viatura.placa) if viatura.placa else ""
        titulo = " · ".join(p for p in [placa_fmt, viatura.modelo or ""] if p)
        meta = " · ".join(p for p in [
            viatura.get_tipo_display() if viatura.tipo else "",
            str(viatura.unidade) if viatura.unidade_id else "",
        ] if p)
        viatura_row = {
            "initials": "VT",
            "name": titulo or "Viatura",
            "meta": meta,
            "view_url": viatura_view_url,
            "pdf_url": viatura_pdf_url,
            "docx_url": viatura_docx_url,
        }

    menus = []
    doc_items = []
    if pdf_url:
        doc_items.append(entity_cards.menu_link(
            pdf_url, "Baixar PDF", "Todos os servidores do termo", "pdf", "pdf", download=True,
        ))
    if docx_url:
        doc_items.append(entity_cards.menu_link(
            docx_url, "Baixar DOCX", "Arquivo editável", "docx", "docx", download=True,
        ))
    if generico_pdf_url:
        doc_items.append(entity_cards.menu_link(
            generico_pdf_url, "Termo em branco (PDF)",
            "Sem preenchimento, para assinar à mão", "pdf", "pdf", download=True,
        ))
    if generico_docx_url:
        doc_items.append(entity_cards.menu_link(
            generico_docx_url, "Termo em branco (DOCX)",
            "Sem preenchimento, para editar", "docx", "docx", download=True,
        ))
    if anexar_assinado_url:
        doc_items.append(entity_cards.menu_attach_signed(
            anexar_assinado_url,
            destino,
            assinado=assinado,
            current_name=assinado_nome_original,
            current_view_url=assinado_view_url,
            current_remove_url=remover_assinado_url,
        ))
    if doc_items:
        menus.append(entity_cards.menu(
            f"termo-docs-{termo.pk}",
            "Documentos",
            destino,
            doc_items,
            trigger_state_class="is-assinado" if assinado else "",
        ))

    footer_kwargs = {
        "edit_url": edit_url,
        "edit_aria": "Editar termo",
        "menus": menus,
    }
    if delete_modal:
        footer_kwargs["delete_modal_url"] = delete_url
        footer_kwargs["delete_modal_label"] = destino
        footer_kwargs["delete_modal_title"] = "Excluir termo?"
    elif delete_url:
        footer_kwargs["delete_url"] = delete_url
        footer_kwargs["delete_aria"] = "Excluir termo"

    header_items = [entity_cards.header_item("Destino", destino, wide=True)]
    # periodo_display devolve a sentinela "Periodo nao informado" (truthy) quando
    # nao ha data; sem data o cabecalho fica so com o destino.
    if termo.periodo_efetivo()[0] is not None:
        # "dd/mm/aaaa a dd/mm/aaaa" nao cabe no info-value, que trunca por padrao.
        header_items.append(entity_cards.header_item("Período", periodo, wrap=True))
    header_chips = [entity_cards.chip("muted", oficio_label)] if oficio_label else []

    # Sem servidores e sem viatura o miolo nao renderiza faixa alguma; nesse caso
    # cabecalho e acoes dividem a mesma linha (ver static/css/termos.css).
    compacto = not servidores_display and viatura_row is None

    return {
        "termo_pk": termo.pk,
        "extra_class": "cv-record-card--termo-compacto" if compacto else "",
        "search_text": " ".join(filter(None, [
            destino, periodo, oficio_label,
            str(viatura) if viatura else "",
            *[s["name"] for s in servidores_display],
        ])),
        "header": entity_cards.header(header_items, header_chips),
        "footer": entity_cards.footer(**footer_kwargs),
        "periodo": periodo,
        "oficio_label": oficio_label or "—",
        "servidores": servidores_display,
        "servidores_count": len(servidores_display),
        "com_viatura": com_viatura,
        "viatura_row": viatura_row,
        "linhas_count": len(servidores_display) + (1 if viatura_row else 0),
        "viatura_label": str(viatura) if viatura else "—",
        "servidores_label": str(len(servidores_display)) if servidores_display else "sem servidor",
    }


def apresentar_linha_lista_simples_termo_servidor(
    termo,
    servidor,
    *,
    edit_url="#",
    pdf_url="",
    oficio=None,
    assinado=False,
    anexar_assinado_url="",
    remover_assinado_url="",
    assinado_nome_original="",
    assinado_view_url="",
):
    from oficios.presenters import _iniciais_nome_servidor

    cargo_nome = servidor.cargo.nome if servidor.cargo_id and servidor.cargo else ""
    unidade_nome = str(servidor.unidade) if servidor.unidade_id else ""
    oficio_efetivo = oficio or (termo.oficio if termo.oficio_id else None)
    oficio_label = oficio_efetivo.numero_formatado if oficio_efetivo else "—"
    viatura = termo.viatura if termo.viatura_id else (oficio_efetivo.viatura if oficio_efetivo and oficio_efetivo.viatura_id else None)

    # "Assinado" não vira badge de texto (ocuparia espaço demais na lista) — o
    # próprio ícone "anexar assinado" muda de cor via classe `is-assinado`.
    badges = []

    return {
        "avatar": _iniciais_nome_servidor(servidor.nome),
        "title": servidor.nome,
        "badges": badges,
        "meta": [
            build_meta("Destino", termo.destino_display),
            build_meta("Período", termo.periodo_display),
            build_meta("Cargo", cargo_nome or "—"),
            build_meta("Unidade", unidade_nome or "—"),
            build_meta("Ofício", oficio_label),
            build_meta("Viatura", str(viatura) if viatura else "—"),
        ],
        "edit_url": edit_url,
        "delete_url": "",
        "delete_modal": False,
        "pdf_url": pdf_url,
        "docx_url": "",
        "assinado": assinado,
        "anexar_assinado_url": anexar_assinado_url,
        "remover_assinado_url": remover_assinado_url,
        "assinado_nome_original": assinado_nome_original,
        "assinado_view_url": assinado_view_url,
    }


def apresentar_linha_lista_simples_termo(
    termo,
    *,
    edit_url="#",
    delete_url="#",
    delete_modal=False,
    pdf_url="",
    docx_url="",
    assinado=False,
    anexar_assinado_url="",
    remover_assinado_url="",
    assinado_nome_original="",
    assinado_view_url="",
):
    servidores = termo.servidores_efetivos()
    servidores_count = servidores.count()
    if servidores_count:
        servidores_label = str(servidores_count)
    elif termo.oficio_id:
        servidores_label = "fallback do ofício"
    else:
        servidores_label = "sem servidor"

    viatura = termo.viatura_efetiva()
    oficio_label = termo.oficio.numero_formatado if termo.oficio_id else "—"

    # "Assinado" não vira badge de texto (ocuparia espaço demais na lista) — o
    # próprio ícone "anexar assinado" muda de cor via classe `is-assinado`.
    badges = []

    return {
        "avatar": "TM",
        "title": termo.destino_display,
        "badges": badges,
        "meta": [
            build_meta("Período", termo.periodo_display),
            build_meta("Ofício", oficio_label),
            build_meta("Servidores", servidores_label),
            build_meta("Viatura", str(viatura) if viatura else "—"),
        ],
        "edit_url": edit_url,
        "delete_url": delete_url,
        "delete_modal": delete_modal,
        "pdf_url": pdf_url,
        "docx_url": docx_url,
        "assinado": assinado,
        "anexar_assinado_url": anexar_assinado_url,
        "remover_assinado_url": remover_assinado_url,
        "assinado_nome_original": assinado_nome_original,
        "assinado_view_url": assinado_view_url,
    }
