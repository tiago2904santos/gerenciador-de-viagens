from __future__ import annotations

from django.urls import reverse
from django.utils import timezone

from core.presenters.badges import build_badge
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
    justificativa_card = card.get("justificativa")
    tem_justificativa = bool(
        justificativa_card and justificativa_card.get("status_label") == "Preenchida"
    )
    justificativa_pdf_url = card.get("justificativa_pdf_url", "") if tem_justificativa else ""
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
        "justificativa_pdf_url": justificativa_pdf_url,
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


def _solicitacao_item(doc):
    arquivo_url = doc.arquivo.url if doc.arquivo else ""
    nome = doc.nome_original or doc.arquivo.name.split("/")[-1]
    return {
        "kind": "Solicitação",
        "title": nome,
        "meta": doc.criado_em.strftime("%d/%m/%Y") if doc.criado_em else "",
        "detail": "",
        "visualizar_url": arquivo_url,
        "pdf_url": arquivo_url,
        "docx_url": "",
        "editar_url": "",
    }


def _evento_pronto(evento) -> bool:
    """Evento "pronto" = documentos vinculados finalizados, sem nenhum pendente.

    Regra:
      - Ofícios: nenhum ofício pode estar em rascunho (cancelados são ignorados).
        Não é obrigatório ter ofício — um evento pode se apoiar só em convite/OS.
      - Etapa 4: precisa existir pelo menos um documento (Ordem de Serviço, Plano
        de Trabalho, convite ou ofício/documento de solicitação) e nenhum deles
        pode estar pendente (um Plano de Trabalho em rascunho bloqueia).
    """
    from oficios.models import Oficio
    from planos_trabalho.models import PlanoTrabalho

    oficios = [o for o in evento.oficios.all() if not o.cancelado]
    if any(o.status == Oficio.STATUS_RASCUNHO for o in oficios):
        return False

    planos = [p for p in evento.planos_trabalho.all() if not p.cancelado]
    if any(p.status == PlanoTrabalho.STATUS_RASCUNHO for p in planos):
        return False

    tem_os = any(not o.cancelado for o in evento.ordens_servico.all())
    tem_plano = bool(planos)  # todos os restantes já não são rascunho
    tem_convite = any(a.tipo == EventoAnexo.TIPO_CONVITE for a in evento.anexos.all())
    tem_solicitacao = bool(list(evento.documentos_solicitacao.all()))
    return tem_os or tem_plano or tem_convite or tem_solicitacao


def _evento_roteiro_saida(evento):
    """Roteiro do evento com a saída mais próxima → (saida_date, end_date, origem_nome).

    Considera roteiros ligados direto ao evento e os ligados via ofícios. Ignora
    cancelados e sem data de saída. Devolve (None, None, "") se não houver.
    """
    candidatos = list(evento.roteiros.all())
    for o in evento.oficios.all():
        if o.roteiro_id and o.roteiro:
            candidatos.append(o.roteiro)

    validos = {}
    for r in candidatos:
        if getattr(r, "cancelado", False) or not r.saida_dt:
            continue
        validos[r.pk] = r
    if not validos:
        return None, None, ""

    r = min(validos.values(), key=lambda x: x.saida_dt)
    tz = timezone.get_current_timezone()
    saida_date = r.saida_dt.astimezone(tz).date() if timezone.is_aware(r.saida_dt) else r.saida_dt.date()
    chegada_dt = r.retorno_chegada_dt or r.chegada_dt
    end_date = saida_date
    if chegada_dt:
        end_date = chegada_dt.astimezone(tz).date() if timezone.is_aware(chegada_dt) else chegada_dt.date()
    origem = r.origem_cidade.nome if r.origem_cidade_id and r.origem_cidade else ""
    return saida_date, end_date, origem


def _evento_temporal_chip(evento):
    """Rótulo/tonalidade do chip de um evento pronto: contagem regressiva até a saída."""
    saida_date, end_date, origem = _evento_roteiro_saida(evento)
    if not saida_date:
        return "Pronto", "success"

    today = timezone.localdate()
    sufixo = f" p/ sair de {origem}" if origem else ""
    if today < saida_date:
        dias = (saida_date - today).days
        if dias == 1:
            return f"falta 1 dia{sufixo}", "warning"
        return f"faltam {dias} dias{sufixo}", "warning"
    if saida_date <= today <= end_date:
        return "em andamento", "info"
    dias = (today - end_date).days
    if dias == 0:
        return "concluído hoje", "success"
    if dias == 1:
        return "concluído ontem", "success"
    return f"concluído há {dias} dias", "success"


def _titulo_sem_data(evento) -> str:
    titulo = evento.titulo or f"Evento #{evento.pk}"
    if evento.data_inicio:
        sufixo = f" - {evento.data_inicio.strftime('%d/%m/%Y')}"
        if titulo.endswith(sufixo):
            titulo = titulo[: -len(sufixo)]
    return titulo


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
    documentos.extend(_solicitacao_item(doc) for doc in evento.documentos_solicitacao.all())

    if evento.status == evento.STATUS_CANCELADO:
        status_label, status_state = "Cancelado", "danger"
    elif _evento_pronto(evento):
        status_label, status_state = _evento_temporal_chip(evento)
    else:
        status_label, status_state = "Rascunho", "warning"

    return {
        "pk": evento.pk,
        "titulo": _titulo_sem_data(evento),
        "status_label": status_label,
        "status_state": status_state,
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
        "cancelar_url": reverse("eventos:cancelar", args=[evento.pk]),
        "cancelado": evento.status == evento.STATUS_CANCELADO,
    }


def apresentar_linha_lista_simples_tipo_evento(tipo, edit_url="#", delete_url="#", delete_modal=False):
    badges = [] if tipo.ativo else [build_badge("Inativo", "muted")]
    return {
        "title": tipo.nome,
        "badges": badges,
        "edit_url": edit_url,
        "delete_url": delete_url,
        "delete_modal": delete_modal,
    }
