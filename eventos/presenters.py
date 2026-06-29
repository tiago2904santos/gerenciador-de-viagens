from __future__ import annotations

from django.urls import reverse

from oficios.presenters import apresentar_oficio_card

from .models import EventoAnexo


def _clean_evento_display(value: str) -> str:
    replacements = {
        "Destino nao informado": "Destino não informado",
        "Periodo nao informado": "Período não informado",
    }
    return replacements.get(value, value)


def _oficio_item(oficio):
    card = apresentar_oficio_card(oficio)
    viatura_placa = card.get("veiculo_placa") or ""
    viatura_modelo = card.get("veiculo_modelo") or ""
    viatura_display = " · ".join(filter(None, [viatura_placa, viatura_modelo])) or "Não informado"

    viatura_tipo = ""
    viatura_combustivel = ""
    viatura_unidade = ""
    if oficio.viatura_id:
        v = oficio.viatura
        viatura_tipo = v.get_tipo_display() if v.tipo else ""
        viatura_combustivel = str(v.combustivel) if v.combustivel_id else ""
        viatura_unidade = str(v.unidade) if v.unidade_id else ""

    return {
        "numero": card["numero_display"],
        "protocolo": card.get("protocolo_display") or "",
        "status_label": card["status_chip_label"].replace(" (legado)", ""),
        "status_state": card["status_chip_tone"],
        "data": card["data_criacao_display"],
        "servidores": card["servidores"],
        "servidores_count": card["servidores_count"],
        "viatura_display": viatura_display,
        "viatura_placa": viatura_placa,
        "viatura_modelo": viatura_modelo,
        "viatura_tipo": viatura_tipo,
        "viatura_combustivel": viatura_combustivel,
        "viatura_unidade": viatura_unidade,
        "valor_display": card.get("valor_diarias_display") or "Não informado",
        "valor_extenso": card.get("valor_diarias_extenso") or "",
        "editar_url": card["editar_url"],
        "visualizar_url": card["visualizar_url"],
        "pdf_url": card["pdf_url"],
        "docx_url": card["docx_url"],
    }


def _plano_item(plano):
    return {
        "kind": "Plano de trabalho",
        "title": plano.numero_formatado,
        "meta": plano.periodo_display,
        "detail": plano.destino_display,
        "editar_url": reverse("planos_trabalho:wizard_identificacao", args=[plano.pk]),
        "visualizar_url": reverse("planos_trabalho:pdf_inline", args=[plano.pk]),
        "pdf_url": reverse("planos_trabalho:baixar_documento", args=[plano.pk, "pdf"]),
        "docx_url": reverse("planos_trabalho:baixar_documento", args=[plano.pk, "docx"]),
    }


def _ordem_item(ordem):
    return {
        "kind": "Ordem de serviço",
        "title": ordem.numero_formatado,
        "meta": ordem.periodo_display,
        "detail": ordem.destinos_display,
        "editar_url": reverse("ordens_servico:editar", args=[ordem.pk]),
        "visualizar_url": reverse("ordens_servico:pdf_inline", args=[ordem.pk]),
        "pdf_url": reverse("ordens_servico:baixar_pdf", args=[ordem.pk]),
        "docx_url": reverse("ordens_servico:baixar_docx", args=[ordem.pk]),
    }


def _convite_item(anexo):
    arquivo_url = anexo.arquivo.url if anexo.arquivo else ""
    return {
        "kind": "Convite",
        "title": anexo.titulo or anexo.get_tipo_display(),
        "meta": anexo.criado_em.strftime("%d/%m/%Y") if anexo.criado_em else "",
        "detail": anexo.observacoes or "Arquivo anexado ao evento.",
        "visualizar_url": arquivo_url,
        "pdf_url": arquivo_url,
        "docx_url": "",
        "editar_url": "",
    }


def _evento_meta(evento) -> str:
    parts = []
    raw = evento.destino_display
    if raw and raw != "Destino nao informado":
        parts.append(raw)
    pc = _periodo_curto(evento)
    if pc:
        parts.append(pc)
    return " · ".join(parts)


def _periodo_curto(evento) -> str:
    if not evento.data_inicio:
        return ""
    inicio = evento.data_inicio.strftime("%d/%m")
    if not evento.data_fim or evento.data_fim == evento.data_inicio:
        return inicio
    return f"{inicio} a {evento.data_fim.strftime('%d/%m')}"


def apresentar_evento_list_card(evento):
    oficios = [_oficio_item(oficio) for oficio in evento.oficios.all()]

    servidores_flat = []
    for oficio_data in oficios:
        for s in oficio_data["servidores"]:
            servidores_flat.append({**s, "oficio_numero": oficio_data["numero"]})

    documentos = []
    documentos.extend(_plano_item(plano) for plano in evento.planos_trabalho.all())
    documentos.extend(_convite_item(anexo) for anexo in evento.anexos.all() if anexo.tipo == EventoAnexo.TIPO_CONVITE)
    documentos.extend(_ordem_item(ordem) for ordem in evento.ordens_servico.all())

    return {
        "pk": evento.pk,
        "titulo": evento.titulo or f"Evento #{evento.pk}",
        "status_label": evento.get_status_display(),
        "status_state": "success" if evento.status == evento.STATUS_FINALIZADO else "warning",
        "destino": _clean_evento_display(evento.destino_display),
        "periodo": _clean_evento_display(evento.periodo_display),
        "periodo_curto": _periodo_curto(evento),
        "evento_meta": _evento_meta(evento),
        "responsavel": evento.responsavel.nome if evento.responsavel_id and evento.responsavel else "Não informado",
        "oficios": oficios,
        "oficios_count": len(oficios),
        "servidores_flat": servidores_flat,
        "servidores_flat_count": len(servidores_flat),
        "documentos": documentos,
        "documentos_count": len(documentos),
        "detail_url": reverse("eventos:guiado_etapa", args=[evento.pk, 3]),
        "editar_url": reverse("eventos:guiado_etapa", args=[evento.pk, 1]),
        "excluir_url": reverse("eventos:excluir", args=[evento.pk]),
    }
