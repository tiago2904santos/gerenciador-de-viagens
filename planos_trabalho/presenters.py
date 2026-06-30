"""Apresentação do wizard e da listagem de Planos de Trabalho (clone do padrão de ofícios)."""

from __future__ import annotations

from django.urls import reverse

from .models import PlanoTrabalho


def apresentar_evento_card(evento):
    """Card de um evento commitado (etapa 1, estilo do card de ofício)."""
    from roteiros.services.diarias import formatar_valor_diarias
    from .services import montar_efetivo_evento_texto

    nome_op, cargo_op = evento.coordenador_nome_cargo()
    atividades = list(evento.atividades_selecionadas.order_by("ordem", "nome")) if evento.pk else []

    valor_total_display = ""
    valor_unitario_display = ""
    if evento.diarias_valor_total is not None:
        valor_total_display = f"R$ {formatar_valor_diarias(evento.diarias_valor_total)}"
    if evento.diarias_valor_unitario is not None:
        valor_unitario_display = f"R$ {formatar_valor_diarias(evento.diarias_valor_unitario)}"

    return {
        "id": evento.pk,
        "ordem": evento.ordem,
        "titulo": f"Evento {evento.ordem}",
        "programa": evento.programa_display or "—",
        "destino": evento.destino_display,
        "periodo": evento.periodo_display,
        "horario": (evento.horario_atendimento or "").strip() or "—",
        "coordenador_op": nome_op or "—",
        "coordenador_op_cargo": cargo_op or "",
        "efetivo_total": evento.total_efetivo,
        "efetivo_texto": montar_efetivo_evento_texto(evento),
        "valor_total_display": valor_total_display,
        "valor_unitario_display": valor_unitario_display,
        "diarias_composicao": (evento.diarias_composicao or "").strip(),
        "atividades": [a.nome for a in atividades],
        "atividades_count": len(atividades),
        "editar_url": reverse("planos_trabalho:evento_editar", args=[evento.plano_id, evento.pk]),
        "excluir_url": reverse("planos_trabalho:evento_remover", args=[evento.plano_id, evento.pk]),
    }


def _efetivo_itens(efetivos):
    """Linhas de efetivo (cargo · unidade · quantidade) para a lista do resumo."""
    itens = []
    for item in efetivos.select_related("cargo", "unidade").order_by("cargo__nome"):
        if not item.quantidade or not item.cargo_id:
            continue
        cargo_nome = (item.cargo.nome or "").strip()
        if not cargo_nome:
            continue
        unidade = ""
        if item.unidade_id and item.unidade:
            sigla = (getattr(item.unidade, "sigla", "") or "").strip()
            unidade = sigla or (item.unidade.nome or "").strip()
        itens.append(
            {"quantidade": int(item.quantidade), "cargo": cargo_nome, "unidade": unidade}
        )
    return itens


def _resumo_evento_de_plano(plano):
    """Bloco de resumo (etapa 4) derivado dos campos do plano — evento único."""
    from roteiros.services.diarias import formatar_valor_diarias
    from roteiros.services.valor_extenso import valor_por_extenso_ptbr
    from .services import format_periodo_evento_extenso, montar_efetivo_texto

    nome_op, cargo_op = plano.coordenador_nome_cargo("op")
    atividades = (
        list(plano.atividades_selecionadas.order_by("ordem", "nome")) if plano.pk else []
    )
    valor_total_display = ""
    valor_unitario_display = ""
    valor_extenso = ""
    if plano.diarias_valor_total is not None:
        valor_total_display = f"R$ {formatar_valor_diarias(plano.diarias_valor_total)}"
        valor_extenso = valor_por_extenso_ptbr(plano.diarias_valor_total)
    if plano.diarias_valor_unitario is not None:
        valor_unitario_display = f"R$ {formatar_valor_diarias(plano.diarias_valor_unitario)}"

    return {
        "ordem": 1,
        "titulo": "Evento",
        "programa": plano.programa_display or "—",
        "destino": plano.destino_display,
        "periodo": plano.periodo_display,
        "data_evento_extenso": format_periodo_evento_extenso(
            plano.data_evento_inicio, plano.data_evento_fim
        ) or "—",
        "horario": (plano.horario_atendimento or "").strip() or "—",
        "coordenador_op": nome_op or "—",
        "coordenador_op_cargo": cargo_op or "",
        "coordenador_op_presente": bool(nome_op),
        "efetivo_total": plano.total_efetivo,
        "efetivo_texto": montar_efetivo_texto(plano),
        "efetivo_itens": _efetivo_itens(plano.efetivos) if plano.pk else [],
        "valor_total_display": valor_total_display or "—",
        "valor_unitario_display": valor_unitario_display or "—",
        "valor_extenso": valor_extenso or "—",
        "diarias_composicao": (plano.diarias_composicao or "").strip() or "—",
        "atividades": [a.nome for a in atividades],
        "atividades_count": len(atividades),
    }


def _resumo_evento_de_evento(evento):
    """Bloco de resumo (etapa 4) de um evento commitado — multi-evento."""
    from roteiros.services.valor_extenso import valor_por_extenso_ptbr
    from .services import format_periodo_evento_extenso

    card = apresentar_evento_card(evento)
    card["valor_total_display"] = card.get("valor_total_display") or "—"
    card["valor_unitario_display"] = card.get("valor_unitario_display") or "—"
    card["diarias_composicao"] = card.get("diarias_composicao") or "—"
    card["coordenador_op_presente"] = bool(
        card.get("coordenador_op") and card["coordenador_op"] != "—"
    )
    card["data_evento_extenso"] = format_periodo_evento_extenso(
        evento.data_evento_inicio, evento.data_evento_fim
    ) or "—"
    card["valor_extenso"] = (
        valor_por_extenso_ptbr(evento.diarias_valor_total)
        if evento.diarias_valor_total is not None
        else "—"
    )
    card["efetivo_itens"] = _efetivo_itens(evento.efetivos)
    return card


def apresentar_resumo_evento_card(evento):
    """Card de resumo de um evento (mesmo visual da etapa 4). Uso público."""
    return _resumo_evento_de_evento(evento)


def apresentar_resumo_header(plano):
    """Dados de nível do plano usados no cabeçalho dos cards de resumo de evento."""
    nome_adm, cargo_adm = plano.coordenador_nome_cargo("adm")
    return {
        "numero": plano.numero_formatado,
        "coordenador_adm_nome": nome_adm or "—",
        "coordenador_adm_cargo": cargo_adm or "",
        "is_multi": plano.is_multi_evento,
    }


def apresentar_resumo_documentos(plano):
    """Resumo de conferência (etapa 4) — clone do card 'Resumo do ofício'.

    Identidade do plano (número, data de criação, coordenador administrativo) fica
    no cabeçalho; cada evento ganha um bloco de fatos próprio. Em evento único há um
    único bloco derivado do plano; em multi-evento, um bloco por evento commitado.
    """
    nome_adm, cargo_adm = plano.coordenador_nome_cargo("adm")

    if plano.is_multi_evento:
        eventos = [_resumo_evento_de_evento(e) for e in plano.eventos_ordenados]
    else:
        eventos = [_resumo_evento_de_plano(plano)]

    return {
        "numero": plano.numero_formatado,
        "data_criacao": plano.data_criacao.strftime("%d/%m/%Y"),
        "coordenador_adm_nome": nome_adm or "—",
        "coordenador_adm_cargo": cargo_adm or "",
        "is_multi": plano.is_multi_evento,
        "total_eventos": len(eventos),
        "eventos": eventos,
    }


ETAPAS = [
    {"key": "identificacao", "number": 1, "title": "Identificação e atuação", "url_name": "planos_trabalho:wizard_identificacao"},
    {"key": "efetivo_diarias", "number": 2, "title": "Efetivo e diárias", "url_name": "planos_trabalho:wizard_efetivo_diarias"},
    {"key": "atividades", "number": 3, "title": "Atividades, metas e recursos", "url_name": "planos_trabalho:wizard_atividades"},
    {"key": "documentos", "number": 4, "title": "Resumo e documentos", "url_name": "planos_trabalho:wizard_documentos"},
]


def apresentar_status_etapa(status):
    labels = {
        "not_started": "Não iniciada",
        "current": "Atual",
        "incomplete": "Incompleta",
        "complete": "Concluída",
        "locked": "Bloqueada",
    }
    return {"status": status, "label": labels.get(status, "Não iniciada")}


def apresentar_plano_wizard_header(etapa_atual, plano=None):
    titles = {step["key"]: step["title"] for step in ETAPAS}
    numbers = {step["key"]: step["number"] for step in ETAPAS}
    subtitle = titles.get(etapa_atual, ETAPAS[0]["title"])
    step_number = numbers.get(etapa_atual, 1)
    ctx = {
        "title": "Plano de Trabalho",
        "subtitle": subtitle,
        "description": f"Etapa {step_number} de {len(ETAPAS)} — {subtitle}",
    }
    if plano is not None:
        ctx["status_label"] = plano.get_status_display()
        ctx["status_variant"] = "draft" if plano.status == PlanoTrabalho.STATUS_RASCUNHO else "active"
    return ctx


def apresentar_plano_wizard_steps(
    plano=None,
    etapa_atual="identificacao",
    identificacao_status=None,
    efetivo_diarias_status=None,
    atividades_status=None,
    documentos_status=None,
):
    status_map = {
        "identificacao": identificacao_status or "not_started",
        "efetivo_diarias": efetivo_diarias_status or "not_started",
        # Etapa 3 é placeholder: nunca bloqueia o fluxo.
        "atividades": atividades_status or "not_started",
        "documentos": documentos_status or "not_started",
    }
    steps = []
    for definicao in ETAPAS:
        key = definicao["key"]
        completion = status_map[key]
        step = {
            "key": key,
            "number": definicao["number"],
            "title": definicao["title"],
            "url": reverse(definicao["url_name"], args=[plano.pk]) if plano else "",
            "state": "current" if etapa_atual == key else completion,
            "completion_state": completion,
        }
        step["state_label"] = apresentar_status_etapa(completion)["label"]
        steps.append(step)
    return steps


def _step_state_class(step: dict) -> str:
    state = step.get("state") or step.get("completion_state") or "not_started"
    if state == "current":
        return "is-current"
    if state == "complete":
        return "is-complete"
    if state == "locked":
        return "is-disabled"
    if state == "incomplete":
        return "is-missing"
    return "is-pending"


def _step_marker(step: dict) -> tuple[str, bool]:
    state = step.get("state") or step.get("completion_state") or "not_started"
    if state == "complete":
        return "✓", True
    return str(step.get("number") or ""), False


def apresentar_plano_wizard_page_steps(steps):
    page_steps = []
    for step in steps or []:
        state_class = _step_state_class(step)
        marker, marker_hidden = _step_marker(step)
        page_steps.append(
            {
                "url": step.get("url") or "",
                "state_class": state_class,
                "step_label": f"Etapa {step.get('number', '')}",
                "title": step.get("title") or "",
                "status": step.get("state_label") or "",
                "marker": marker,
                "marker_aria_hidden": marker_hidden,
                "aria_current": "step" if state_class == "is-current" else "",
            }
        )
    return page_steps


def apresentar_plano_wizard_summary(plano):
    if plano is None:
        raise ValueError("O wizard de plano de trabalho exige um rascunho persistido.")
    return {
        "numero_label": plano.numero_formatado,
        "data_criacao_label": plano.data_criacao.strftime("%d/%m/%Y"),
        "status_label": plano.get_status_display(),
        "status_state": str(plano.status or "").lower(),
    }


def apresentar_plano_card(plano):
    from roteiros.services.diarias import formatar_valor_diarias

    coordenador_nome, _cargo = plano.coordenador_nome_cargo("adm")
    if plano.is_multi_evento:
        eventos = list(plano.eventos.all()) if plano.pk else []
        n = len(eventos)
        programa_label = f"{n} eventos" if n != 1 else "1 evento"
        # Em multi, os campos do plano refletem o rascunho — agrega dos eventos.
        destinos = []
        for e in eventos:
            d = e.destino_display
            if d and d != "Destino não informado" and d not in destinos:
                destinos.append(d)
        destino_label = ", ".join(destinos) or "—"
        inicios = [e.data_evento_inicio for e in eventos if e.data_evento_inicio]
        fins = [e.data_evento_fim or e.data_evento_inicio for e in eventos if e.data_evento_inicio]
        if inicios:
            ini, fim = min(inicios), max(fins)
            periodo_label = ini.strftime("%d/%m/%Y") if ini == fim else f"{ini.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}"
        else:
            periodo_label = "—"
        efetivo_total = plano.total_efetivo_combinado
        totais = [e.diarias_valor_total for e in eventos if e.diarias_valor_total is not None]
        valor_total = sum(totais) if totais else None
        valor_unitario = plano.diarias_combinada_valor_unitario
        diarias_composicao = (plano.diarias_combinada_composicao or "").strip()
    else:
        programa_label = plano.programa_display or "—"
        destino_label = plano.destino_display
        periodo_label = plano.periodo_display
        efetivo_total = plano.total_efetivo
        valor_total = plano.diarias_valor_total
        valor_unitario = plano.diarias_valor_unitario
        diarias_composicao = (plano.diarias_composicao or "").strip()

    valor_total_display = f"R$ {formatar_valor_diarias(valor_total)}" if valor_total is not None else ""
    valor_unitario_display = f"R$ {formatar_valor_diarias(valor_unitario)}" if valor_unitario is not None else ""

    # ── Participantes (solicitante + coordenadores) — mesmo visual dos servidores do ofício.
    # Quem não foi informado simplesmente não aparece.
    nome_op, cargo_op = plano.coordenador_nome_cargo("op")
    candidatos = [
        (plano.programa_display, "", "Solicitante"),
        (coordenador_nome, _cargo, "Coord. adm."),
        (nome_op, cargo_op, "Coord. op."),
    ]
    participantes = [
        {"name": nome, "meta": meta or "", "badge": badge}
        for nome, meta, badge in candidatos
        if (nome or "").strip()
    ]

    # ── Atividades selecionadas no plano
    atividades = (
        [a.nome for a in plano.atividades_selecionadas.order_by("ordem", "nome")]
        if plano.pk
        else []
    )

    return {
        "id": plano.pk,
        "numero_label": plano.numero_formatado,
        "status_label": plano.get_status_display(),
        "status_state": str(plano.status or "").lower(),
        "destino": destino_label,
        "periodo": periodo_label,
        "programa": programa_label,
        "coordenador": coordenador_nome or "—",
        "participantes": participantes,
        "atividades": atividades,
        "atividades_count": len(atividades),
        "efetivo_total": efetivo_total,
        "valor_total_display": valor_total_display,
        "valor_unitario_display": valor_unitario_display,
        "diarias_composicao": diarias_composicao,
        "data_criacao_label": plano.data_criacao.strftime("%d/%m/%Y"),
        "editar_url": reverse("planos_trabalho:wizard_identificacao", args=[plano.pk]),
        "documentos_url": reverse("planos_trabalho:wizard_documentos", args=[plano.pk]),
        "excluir_url": reverse("planos_trabalho:excluir", args=[plano.pk]),
        "baixar_docx_url": reverse("planos_trabalho:baixar_documento", args=[plano.pk, "docx"]),
        "baixar_pdf_url": reverse("planos_trabalho:baixar_documento", args=[plano.pk, "pdf"]),
        "pdf_inline_url": reverse("planos_trabalho:pdf_inline", args=[plano.pk]),
    }
