from core.presenters.meta import build_meta


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
