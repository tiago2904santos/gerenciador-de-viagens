from __future__ import annotations

import json

from django.urls import reverse
from django.utils import timezone

from core import entity_cards
from core.presenters.badges import build_badge
from core.presenters.text import join_non_empty
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
    protocolo = card.get("protocolo_display") or ""
    data_evento = card.get("data_evento_display") or ""
    destino = card.get("destino_display") or ""

    viatura_tipo = ""
    viatura_combustivel = ""
    viatura_unidade = ""
    if oficio.viatura_id:
        v = oficio.viatura
        viatura_tipo = v.get_tipo_display() if v.tipo else ""
        viatura_combustivel = str(v.combustivel) if v.combustivel_id else ""
        viatura_unidade = str(v.unidade) if v.unidade_id else ""

    return {
        "oficio_pk": card["oficio_pk"],
        "numero": card["numero_display"],
        "protocolo": protocolo,
        "data_evento_display": data_evento,
        "destino_display": destino,
        "meta_display": join_non_empty([protocolo, data_evento, destino]),
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
    meta = plano.periodo_display
    detail = plano.destino_display
    return {
        "kind": "Plano de trabalho",
        "title": plano.numero_formatado,
        "meta": meta,
        "detail": detail,
        "meta_display": join_non_empty([meta, detail]),
        "editar_url": reverse("planos_trabalho:wizard_identificacao", args=[plano.pk]),
        "visualizar_url": reverse("planos_trabalho:pdf_inline", args=[plano.pk]),
        "pdf_url": reverse("planos_trabalho:baixar_documento", args=[plano.pk, "pdf"]),
        "docx_url": reverse("planos_trabalho:baixar_documento", args=[plano.pk, "docx"]),
    }


def _ordem_item(ordem):
    meta = ordem.periodo_display
    detail = ordem.destinos_display
    return {
        "kind": "Ordem de serviço",
        "title": ordem.numero_formatado,
        "meta": meta,
        "detail": detail,
        "meta_display": join_non_empty([meta, detail]),
        "editar_url": reverse("ordens_servico:editar", args=[ordem.pk]),
        "visualizar_url": reverse("ordens_servico:pdf_inline", args=[ordem.pk]),
        "pdf_url": reverse("ordens_servico:baixar_pdf", args=[ordem.pk]),
        "docx_url": reverse("ordens_servico:baixar_docx", args=[ordem.pk]),
    }


def _convite_item(anexo):
    arquivo_url = (
        reverse("eventos:evento_anexo_conteudo", args=[anexo.evento_id, anexo.pk])
        if anexo.arquivo
        else ""
    )
    meta = anexo.criado_em.strftime("%d/%m/%Y") if anexo.criado_em else ""
    detail = anexo.observacoes or "Arquivo anexado ao evento."
    return {
        "kind": "Convite",
        "title": anexo.titulo or anexo.get_tipo_display(),
        "meta": meta,
        "detail": detail,
        "meta_display": join_non_empty([meta, detail]),
        "visualizar_url": arquivo_url,
        "pdf_url": arquivo_url,
        "docx_url": "",
        "editar_url": "",
    }


def _solicitacao_item(doc):
    arquivo_url = (
        reverse("eventos:solicitacao_anexo_conteudo", args=[doc.evento_id, doc.pk])
        if doc.arquivo
        else ""
    )
    nome = doc.nome_original or doc.arquivo.name.split("/")[-1]
    meta = doc.criado_em.strftime("%d/%m/%Y") if doc.criado_em else ""
    return {
        "kind": "Solicitação",
        "title": nome,
        "meta": meta,
        "detail": "",
        "meta_display": join_non_empty([meta]),
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
    if today < saida_date:
        dias = (saida_date - today).days
        if dias == 1:
            return "falta 1 dia", "warning"
        return f"faltam {dias} dias", "warning"
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
    if raw and raw not in {"Destino nao informado", "Destino não informado"}:
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


def apresentar_evento_list_card(evento, *, menus_sob_demanda=True):
    """Card da lista de eventos.

    `menus_sob_demanda` liga o `PF-04`. São quatro famílias de menu neste card —
    rodapé, um por ofício, um por documento e um por servidor com termo — e todas
    saem do HTML da lista quando isto é `True`. Quem serve é `eventos:card_menus`.
    """
    menus_src = reverse("eventos:card_menus", args=[evento.pk]) if menus_sob_demanda else ""

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

    titulo = _titulo_sem_data(evento)
    destino = _clean_evento_display(evento.destino_display)
    periodo = _clean_evento_display(evento.periodo_display)
    responsavel = evento.responsavel.nome if evento.responsavel_id and evento.responsavel else "Não informado"
    cancelado = evento.status == evento.STATUS_CANCELADO
    excluir_url = reverse("eventos:excluir", args=[evento.pk])
    cancelar_url = reverse("eventos:cancelar", args=[evento.pk])
    reativar_url = reverse("eventos:reativar", args=[evento.pk])

    search_parts = [titulo, destino, periodo, responsavel]
    for oficio_data in oficios:
        search_parts.append(oficio_data["numero"])
        search_parts.extend(s["name"] for s in oficio_data["servidores"])
    for doc in documentos:
        search_parts.extend([doc.get("kind", ""), doc.get("title", ""), doc.get("detail", "")])

    header_value = " · ".join(p for p in [titulo, destino, periodo] if p)

    if cancelado:
        acao_situacao = entity_cards.menu_confirm(
            reativar_url, titulo, "Reativar evento", "Retornar o evento ao fluxo de trabalho",
            icon="unarchive", icon_tone="success",
        )
    else:
        acao_situacao = entity_cards.menu_cancel(
            cancelar_url, titulo,
            title="Cancelar evento", description="Interromper o fluxo mantendo o histórico",
        )

    return {
        "pk": evento.pk,
        "search_text": " ".join(p for p in search_parts if p).strip(),
        "header": entity_cards.header(
            [entity_cards.header_item("Evento", header_value, wide=True, wrap=True)],
            [entity_cards.chip(status_state, status_label)],
        ),
        "footer": entity_cards.footer(
            edit_url=reverse("eventos:guiado_etapa", args=[evento.pk, 1]),
            edit_aria="Editar evento",
            edit_tooltip="Editar evento",
            danger_menus=[
                entity_cards.menu(
                    f"evento-action-menu-{evento.pk}",
                    "Gerenciar evento",
                    titulo,
                    [
                        acao_situacao,
                        entity_cards.menu_delete(
                            excluir_url, titulo,
                            title="Excluir evento",
                        ),
                    ],
                    icon="settings",
                    trigger_icon="more",
                    trigger_variant="edit",
                    trigger_aria="Mais ações do evento",
                    trigger_tooltip="Mais ações",
                    src=menus_src,
                )
            ],
        ),
        # Os gatilhos escritos à mão no `_evento_card_body.html` apontam para cá.
        "menus_url": menus_src,
        "titulo": titulo,
        "status_label": status_label,
        "status_state": status_state,
        "destino": destino,
        "periodo": periodo,
        "periodo_curto": _periodo_curto(evento),
        "evento_meta": _evento_meta(evento),
        "responsavel": responsavel,
        "oficios": oficios,
        "oficios_count": len(oficios),
        "servidores_flat": servidores_flat,
        "servidores_flat_count": len(servidores_flat),
        "documentos": documentos,
        "documentos_count": len(documentos),
        "detail_url": reverse("eventos:guiado_etapa", args=[evento.pk, 3]),
        "editar_url": reverse("eventos:guiado_etapa", args=[evento.pk, 1]),
        "excluir_url": excluir_url,
        "cancelar_url": cancelar_url,
        "reativar_url": reativar_url,
        "cancelado": cancelado,
    }


# ── Documentos vinculáveis: resumos para o picker do evento ────────────────
#
# A lista de documentos vinculados reaproveita o mesmo cartão de busca dos
# ofícios da Ordem de Serviço (título + meta em duas linhas) e recebe uma
# pré-filtragem por datas no cliente. O servidor entrega apenas os dados de
# cada documento (título, meta, período em ISO); o JS decide o que exibir
# comparando o período do documento com o período do evento.

# Documentos cujo período estiver a até N dias do período do evento aparecem
# na lista. Ajuste único aqui caso a tolerância precise mudar.
DOCUMENTO_FILTRO_DIAS_TOLERANCIA = 5

_PLACEHOLDERS_META = (
    "nao informado",
    "nao informada",
    "periodo nao informado",
    "destino nao informado",
)


def _sem_acento(texto: str) -> str:
    import unicodedata

    return "".join(
        c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn"
    )


def _meta_limpa(texto) -> str:
    texto = (texto or "").strip()
    if not texto:
        return ""
    base = _sem_acento(texto).lower()
    if any(base == p or base.endswith(p) for p in _PLACEHOLDERS_META):
        return ""
    return texto


def _como_data(valor):
    # Normaliza datetime -> date; date passa direto.
    if valor and hasattr(valor, "hour"):
        return valor.date()
    return valor


def _iso_data(valor) -> str:
    data = _como_data(valor)
    if not data:
        return ""
    try:
        return data.isoformat()
    except Exception:
        return ""


def _data_br(valor) -> str:
    data = _como_data(valor)
    if not data:
        return ""
    try:
        return data.strftime("%d/%m/%Y")
    except Exception:
        return ""


def _periodo_texto(inicio, fim) -> str:
    if not inicio:
        return ""
    if not fim or fim == inicio:
        return _data_br(inicio)
    return f"{_data_br(inicio)} a {_data_br(fim)}"


def _primeiros_nomes(nomes) -> str:
    partes = []
    for nome in nomes:
        nome = (nome or "").strip()
        if nome:
            partes.append(nome.split()[0])
    return ", ".join(partes)


def _selecionados(form, field_name) -> set[str]:
    valor = form[field_name].value() or []
    if isinstance(valor, (str, int)):
        valor = [valor]
    return {str(v) for v in valor}


def _datas_roteiro(roteiro):
    inicio = roteiro.saida_dt.date() if roteiro.saida_dt else None
    retorno = (
        getattr(roteiro, "retorno_chegada_dt", None)
        or getattr(roteiro, "retorno_saida_dt", None)
        or getattr(roteiro, "chegada_dt", None)
    )
    fim = retorno.date() if retorno else inicio
    return inicio, fim


def _resumo_oficio(oficio, selecionados: set[str]) -> dict:
    roteiro = oficio.roteiro
    destino_label = ""
    inicio = fim = None
    if roteiro:
        sede_obj = roteiro.origem_cidade or roteiro.origem_estado
        sede = str(sede_obj) if sede_obj else ""
        destinos = list(roteiro.destinos.select_related("cidade", "estado").order_by("ordem", "pk"))
        destinos_label = ", ".join(
            str(d.cidade or d.estado) for d in destinos if (d.cidade_id or d.estado_id)
        )
        destino_label = " → ".join(p for p in [sede, destinos_label] if p)
        inicio, fim = _datas_roteiro(roteiro)

    servidores = list(oficio.servidores.all())
    viatura = ""
    if oficio.viatura_id:
        placa = str(oficio.viatura)
        modelo = (getattr(oficio.viatura, "modelo", "") or "").strip()
        viatura = f"{placa} {modelo}".strip()

    title = " ".join(p for p in [f"Ofício {oficio.numero_formatado}", destino_label] if p)
    meta = " · ".join(
        p for p in [_periodo_texto(inicio, fim), _primeiros_nomes(s.nome for s in servidores), viatura] if p
    )
    search = " ".join(
        p
        for p in [
            oficio.numero_formatado,
            oficio.protocolo or "",
            destino_label,
            " ".join(s.nome for s in servidores),
            viatura,
        ]
        if p
    )
    return {
        "id": oficio.pk,
        "title": title,
        "meta": meta or "Sem informações disponíveis",
        "search_text": search,
        "data_inicio": _iso_data(inicio),
        "data_fim": _iso_data(fim),
        "selected": str(oficio.pk) in selecionados,
    }


def _resumo_roteiro(roteiro, selecionados: set[str]) -> dict:
    inicio, fim = _datas_roteiro(roteiro)
    title = str(roteiro)
    meta = _periodo_texto(inicio, fim)
    return {
        "id": roteiro.pk,
        "title": title,
        "meta": meta or "Sem período definido",
        "search_text": f"{title} {meta}",
        "data_inicio": _iso_data(inicio),
        "data_fim": _iso_data(fim),
        "selected": str(roteiro.pk) in selecionados,
    }


def _resumo_ordem(ordem, selecionados: set[str]) -> dict:
    inicio = ordem.data_evento_inicio
    fim = ordem.data_evento_fim or inicio
    title = ordem.numero_formatado
    meta = " · ".join(
        p for p in [_meta_limpa(ordem.periodo_display), _meta_limpa(ordem.destinos_display)] if p
    )
    return {
        "id": ordem.pk,
        "title": title,
        "meta": meta or "Sem período definido",
        "search_text": f"{title} {meta}",
        "data_inicio": _iso_data(inicio),
        "data_fim": _iso_data(fim),
        "selected": str(ordem.pk) in selecionados,
    }


def _resumo_plano(plano, selecionados: set[str]) -> dict:
    inicio = plano.data_evento_inicio
    fim = plano.data_evento_fim or inicio
    title = f"PT {plano.numero_formatado}"
    meta = " · ".join(
        p for p in [_meta_limpa(plano.programa_display), _meta_limpa(plano.periodo_display)] if p
    )
    return {
        "id": plano.pk,
        "title": title,
        "meta": meta or "Sem período definido",
        "search_text": f"{title} {meta}",
        "data_inicio": _iso_data(inicio),
        "data_fim": _iso_data(fim),
        "selected": str(plano.pk) in selecionados,
    }


def _resumo_termo(termo, selecionados: set[str]) -> dict:
    inicio, fim = termo.periodo_efetivo()
    title = f"Termo #{termo.pk}"
    meta = " · ".join(
        p for p in [_meta_limpa(termo.destino_display), _meta_limpa(termo.periodo_display)] if p
    )
    return {
        "id": termo.pk,
        "title": title,
        "meta": meta or "Sem período definido",
        "search_text": f"{title} {meta}",
        "data_inicio": _iso_data(inicio),
        "data_fim": _iso_data(fim),
        "selected": str(termo.pk) in selecionados,
    }


def _periodo_referencia_evento(form) -> dict:
    def norm(valor):
        if not valor:
            return ""
        if hasattr(valor, "isoformat"):
            return valor.isoformat()
        valor = str(valor).strip()
        if len(valor) == 10 and valor[4:5] == "-" and valor[7:8] == "-":
            return valor
        return ""

    if form.is_bound:
        return {"inicio": norm(form.data.get("data_inicio")), "fim": norm(form.data.get("data_fim"))}
    instance = getattr(form, "instance", None)
    return {
        "inicio": norm(getattr(instance, "data_inicio", None)),
        "fim": norm(getattr(instance, "data_fim", None)),
    }


def build_evento_documentos_context(form) -> dict:
    """Resumos dos documentos vinculáveis para o picker de "Documentos vinculados".

    Cada tipo de documento vira uma lista de cartões (título + meta + período em
    ISO) consumida pelo JS, que aplica a pré-filtragem por proximidade de datas
    contra o período do evento (``DOCUMENTO_FILTRO_DIAS_TOLERANCIA`` dias).
    """
    if form is None:
        return {}

    resumos = {
        "oficios": [
            _resumo_oficio(o, _selecionados(form, "oficios_vinculados"))
            for o in form.fields["oficios_vinculados"].queryset
        ],
        "roteiros": [
            _resumo_roteiro(r, _selecionados(form, "roteiros_vinculados"))
            for r in form.fields["roteiros_vinculados"].queryset
        ],
        "pt": [
            _resumo_plano(p, _selecionados(form, "planos_trabalho_vinculados"))
            for p in form.fields["planos_trabalho_vinculados"].queryset
        ],
        "os": [
            _resumo_ordem(o, _selecionados(form, "ordens_servico_vinculadas"))
            for o in form.fields["ordens_servico_vinculadas"].queryset
        ],
        "termos": [
            _resumo_termo(t, _selecionados(form, "termos_vinculados"))
            for t in form.fields["termos_vinculados"].queryset
        ],
    }
    return {
        "evento_doc_summaries": resumos,
        "evento_doc_periodo": _periodo_referencia_evento(form),
        "evento_doc_tolerancia_dias": DOCUMENTO_FILTRO_DIAS_TOLERANCIA,
    }


def apresentar_linha_lista_simples_tipo_evento(tipo, edit_url="#", delete_url="#", delete_modal=False):
    badges = [] if tipo.ativo else [build_badge("Inativo", "muted")]
    return {
        "title": tipo.nome,
        "badges": badges,
        "edit_url": edit_url,
        "edit_fields_json": json.dumps({"nome": tipo.nome, "ativo": tipo.ativo}, ensure_ascii=False),
        "delete_url": delete_url,
        "delete_modal": delete_modal,
    }
