from django.urls import reverse

from core import entity_cards
from core.presenters.meta import build_meta
from core.presenters.meta import linha_de_meta
from core.presenters.text import join_non_empty
from core.utils.masks import format_placa
from termos.abas import situacao_do_termo


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
            "meta": join_non_empty([cargo_nome, unidade_nome]),
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

    # O modal de download pergunta a este endpoint o que existe para baixar.
    downloads_url = reverse("termos:termo_cadastro_downloads", args=[termo.pk]) if termo.pk else ""

    # SEM menus (2026-08-18). O cartão tinha um menu "Documentos" que era um
    # segundo caminho para o mesmo download que o seletor ao lado já faz, com a
    # diferença de esconder a escolha atrás de dois cliques. Com ele foi embora
    # o endpoint sob demanda (`termos:card_menus`) — não havia mais gatilho
    # nenhum para servir.
    menus = []

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

    # Titulo unico "destino · periodo", como o card de roteiro faz com a rota.
    # periodo_display devolve a sentinela "Periodo nao informado" (truthy)
    # quando nao ha data; nesse caso o titulo fica so com o destino.
    tem_periodo = termo.periodo_efetivo()[0] is not None
    # A meta responde "de quem é este termo" sem abrir: ofício, equipe e
    # viatura na mesma linha. Os nomes vêm inteiros — o primeiro nome sozinho
    # não distingue dois ADEMAR da mesma unidade.
    meta_partes = []
    if oficio_label:
        meta_partes.append(f"Ofício: {oficio_label}")
    if servidores_display:
        meta_partes.append(", ".join(s["name"] for s in servidores_display))
    if viatura is not None:
        placa_meta = format_placa(viatura.placa) if viatura.placa else ""
        meta_partes.append(" ".join(p for p in [placa_meta, viatura.modelo or ""] if p))
    titulo = " · ".join(p for p in [destino, periodo if tem_periodo else ""] if p)
    header_items = [
        entity_cards.header_item("Termo", titulo or destino, wide=True, wrap=True)
    ]
    header_chips = [entity_cards.chip("muted", oficio_label)] if oficio_label else []

    # Sem servidores e sem viatura o miolo nao renderiza faixa alguma; nesse caso
    # cabecalho e acoes dividem a mesma linha (ver static/css/pages/termos.css).
    return {
        "termo_pk": termo.pk,
        "situacao": situacao_do_termo(termo),
        "meta_line": " · ".join(meta_partes),
        # O anexar-assinado deixou de ser item de menu e virou botão da linha:
        # é a única ação do termo que não é "baixar", e estava escondida dois
        # cliques abaixo de um menu chamado "Documentos".
        "assinatura": {
            "url": anexar_assinado_url,
            "assinado": assinado,
            "doc_label": f"o termo de {destino}",
            "nome_original": assinado_nome_original,
            "view_url": assinado_view_url,
            "remover_url": remover_assinado_url,
        },
        "search_text": " ".join(filter(None, [
            destino, periodo, oficio_label,
            str(viatura) if viatura else "",
            *[s["name"] for s in servidores_display],
        ])),
        "header": entity_cards.header(header_items, header_chips),
        "footer": entity_cards.footer(**footer_kwargs),
        "periodo": periodo,
        "oficio_label": oficio_label or "—",
        "downloads_url": downloads_url,
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
    delete_url="",
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

    meta = [
        build_meta("Destino", termo.destino_display),
        build_meta("Período", termo.periodo_display),
        build_meta("Cargo", cargo_nome or "—"),
        build_meta("Unidade", unidade_nome or "—"),
        build_meta("Ofício", oficio_label),
        build_meta("Viatura", str(viatura) if viatura else "—"),
    ]
    return {
        "avatar": _iniciais_nome_servidor(servidor.nome),
        "title": servidor.nome,
        "badges": badges,
        "meta": meta,
        "meta_line": linha_de_meta(meta),
        "edit_url": edit_url,
        "delete_url": delete_url,
        "delete_modal": bool(delete_url),
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

    meta = [
        build_meta("Período", termo.periodo_display),
        build_meta("Ofício", oficio_label),
        build_meta("Servidores", servidores_label),
        build_meta("Viatura", str(viatura) if viatura else "—"),
    ]
    return {
        "avatar": "TM",
        "title": termo.destino_display,
        "badges": badges,
        "meta": meta,
        "meta_line": linha_de_meta(meta),
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
