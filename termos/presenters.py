from core.presenters.meta import build_meta


def apresentar_linha_lista_simples_termo_servidor(
    termo,
    servidor,
    *,
    edit_url="#",
    pdf_url="",
):
    from oficios.presenters import _iniciais_nome_servidor

    cargo_nome = servidor.cargo.nome if servidor.cargo_id and servidor.cargo else ""
    unidade_nome = str(servidor.unidade) if servidor.unidade_id else ""
    oficio_label = termo.oficio.numero_formatado if termo.oficio_id else "—"

    return {
        "avatar": _iniciais_nome_servidor(servidor.nome),
        "title": servidor.nome,
        "badges": [],
        "meta": [
            build_meta("Destino", termo.destino_display),
            build_meta("Período", termo.periodo_display),
            build_meta("Cargo", cargo_nome or "—"),
            build_meta("Unidade", unidade_nome or "—"),
            build_meta("Ofício", oficio_label),
        ],
        "edit_url": edit_url,
        "delete_url": "",
        "delete_modal": False,
        "pdf_url": pdf_url,
        "docx_url": "",
    }


def apresentar_linha_lista_simples_termo(
    termo,
    *,
    edit_url="#",
    delete_url="#",
    delete_modal=False,
    pdf_url="",
    docx_url="",
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

    return {
        "avatar": "TM",
        "title": termo.destino_display,
        "badges": [],
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
    }
