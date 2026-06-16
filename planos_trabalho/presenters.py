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
    else:
        programa_label = plano.programa_display or "—"
        destino_label = plano.destino_display
        periodo_label = plano.periodo_display
        efetivo_total = plano.total_efetivo
    return {
        "id": plano.pk,
        "numero_label": plano.numero_formatado,
        "status_label": plano.get_status_display(),
        "status_state": str(plano.status or "").lower(),
        "destino": destino_label,
        "periodo": periodo_label,
        "programa": programa_label,
        "coordenador": coordenador_nome or "—",
        "efetivo_total": efetivo_total,
        "data_criacao_label": plano.data_criacao.strftime("%d/%m/%Y"),
        "editar_url": reverse("planos_trabalho:wizard_identificacao", args=[plano.pk]),
        "documentos_url": reverse("planos_trabalho:wizard_documentos", args=[plano.pk]),
        "excluir_url": reverse("planos_trabalho:excluir", args=[plano.pk]),
        "baixar_docx_url": reverse("planos_trabalho:baixar_documento", args=[plano.pk, "docx"]),
        "baixar_pdf_url": reverse("planos_trabalho:baixar_documento", args=[plano.pk, "pdf"]),
        "pdf_inline_url": reverse("planos_trabalho:pdf_inline", args=[plano.pk]),
    }
