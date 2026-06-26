"""Apresentadores (presenters) do módulo de Eventos.

`apresentar_evento_card` monta um card de lista rico, no mesmo espírito do
card de ofícios, agregando TODOS os documentos vinculados ao evento
(ofícios, planos de trabalho, ordens de serviço e termos) além dos dados
principais do próprio evento.
"""

from django.urls import reverse
from django.utils import timezone

from .models import Evento


# ── Status do evento ────────────────────────────────────────────────
_EVENTO_STATUS_TONE = {
    Evento.STATUS_RASCUNHO: "muted",
    Evento.STATUS_EM_PREPARACAO: "warning",
    Evento.STATUS_DOCUMENTOS_GERADOS: "info",
    Evento.STATUS_EM_EXECUCAO: "info",
    Evento.STATUS_FINALIZADO: "success",
    Evento.STATUS_CANCELADO: "danger",
}

_EVENTO_STATUS_VARIANT = {
    Evento.STATUS_RASCUNHO: "rascunho",
    Evento.STATUS_EM_PREPARACAO: "preparacao",
    Evento.STATUS_DOCUMENTOS_GERADOS: "gerado",
    Evento.STATUS_EM_EXECUCAO: "execucao",
    Evento.STATUS_FINALIZADO: "finalizado",
    Evento.STATUS_CANCELADO: "cancelado",
}


def _tipo_display_evento(evento) -> str:
    if not evento.tipo:
        return ""
    if evento.tipo == Evento.TIPO_OUTROS and (evento.tipo_outro or "").strip():
        return evento.tipo_outro.strip()
    return evento.get_tipo_display()


def _temporal_badge_evento(evento):
    """Chip relativo (faltam X dias / em andamento / há X dias)."""
    inicio = evento.data_inicio
    if not inicio:
        return None, "muted"
    hoje = timezone.localdate()
    fim = evento.data_fim or inicio
    if hoje < inicio:
        dias = (inicio - hoje).days
        if dias == 1:
            return "falta 1 dia", "warning"
        return f"faltam {dias} dias", "warning"
    if inicio <= hoje <= fim:
        if hoje == inicio:
            return "começa hoje", "info"
        return "em andamento", "info"
    dias = (hoje - fim).days
    if dias == 0:
        return "foi hoje", "success"
    if dias == 1:
        return "foi ontem", "success"
    return f"há {dias} dias", "success"


def _responsavel_display(evento) -> str:
    if evento.responsavel_id and evento.responsavel:
        return evento.responsavel.nome
    return ""


def _unidade_display(evento) -> str:
    if evento.unidade_responsavel_id and evento.unidade_responsavel:
        return str(evento.unidade_responsavel)
    return ""


# ── Sub-itens de documentos ─────────────────────────────────────────
def _oficio_tone(oficio) -> str:
    from oficios.models import Oficio

    if oficio.status in {Oficio.STATUS_GERADO, Oficio.STATUS_FINALIZADO}:
        return "success"
    if oficio.status == Oficio.STATUS_ARQUIVADO:
        return "muted"
    return "warning"


def _itens_oficios(evento):
    itens = []
    for oficio in evento.oficios.all():
        try:
            url = reverse("oficios:dados_viajantes", args=[oficio.pk])
        except Exception:
            url = ""
        try:
            pdf_url = reverse("oficios:oficio_pdf_inline", args=[oficio.pk])
        except Exception:
            pdf_url = ""
        itens.append(
            {
                "titulo": oficio.numero_formatado,
                "status_label": oficio.get_status_display(),
                "status_tone": _oficio_tone(oficio),
                "url": url,
                "pdf_url": pdf_url,
            }
        )
    return itens


def _plano_tone(plano) -> str:
    from planos_trabalho.models import PlanoTrabalho

    if plano.status == PlanoTrabalho.STATUS_GERADO:
        return "success"
    return "warning"


def _itens_planos(evento):
    itens = []
    for plano in evento.planos_trabalho.all():
        try:
            url = reverse("planos_trabalho:wizard_identificacao", args=[plano.pk])
        except Exception:
            url = ""
        try:
            pdf_url = reverse("planos_trabalho:pdf_inline", args=[plano.pk])
        except Exception:
            pdf_url = ""
        itens.append(
            {
                "titulo": f"PT {plano.numero_formatado}",
                "status_label": plano.get_status_display(),
                "status_tone": _plano_tone(plano),
                "destino": plano.destino_display,
                "url": url,
                "pdf_url": pdf_url,
            }
        )
    return itens


def _itens_ordens(evento):
    itens = []
    for ordem in evento.ordens_servico.all():
        try:
            url = reverse("ordens_servico:editar", args=[ordem.pk])
        except Exception:
            url = ""
        itens.append(
            {
                "titulo": ordem.numero_formatado,
                "periodo": ordem.periodo_display,
                "destino": ordem.destinos_display,
                "servidores_count": ordem.servidores.count(),
                "url": url,
            }
        )
    return itens


def _itens_termos(evento):
    itens = []
    for termo in evento.termos_autorizacao.all():
        try:
            url = reverse("termos:editar", args=[termo.pk])
        except Exception:
            url = ""
        itens.append(
            {
                "titulo": getattr(termo, "destino_display", "") or f"Termo #{termo.pk}",
                "periodo": getattr(termo, "periodo_display", ""),
                "url": url,
            }
        )
    return itens


def apresentar_evento_card(evento):
    """Monta o card completo de um evento para a listagem."""
    oficios = _itens_oficios(evento)
    planos = _itens_planos(evento)
    ordens = _itens_ordens(evento)
    termos = _itens_termos(evento)

    temporal_label, temporal_tone = _temporal_badge_evento(evento)

    motivo = (evento.motivo or evento.descricao or "").strip()
    motivo_resumido = (motivo[:200] + "…") if len(motivo) > 200 else motivo

    status = evento.status or Evento.STATUS_RASCUNHO

    try:
        detalhe_url = reverse("eventos:detalhe", args=[evento.pk])
    except Exception:
        detalhe_url = ""
    try:
        editar_url = reverse("eventos:guiado_etapa", kwargs={"pk": evento.pk, "etapa": 1})
    except Exception:
        editar_url = ""

    def _etapa_url(etapa):
        try:
            return reverse("eventos:guiado_etapa", kwargs={"pk": evento.pk, "etapa": etapa})
        except Exception:
            return ""

    return {
        "evento_pk": evento.pk,
        "titulo": evento.titulo or f"Evento #{evento.pk}",
        "tipo_display": _tipo_display_evento(evento),
        "status_label": evento.get_status_display(),
        "status_tone": _EVENTO_STATUS_TONE.get(status, "muted"),
        "status_variant": _EVENTO_STATUS_VARIANT.get(status, "rascunho"),
        "periodo_display": evento.periodo_display,
        "destino_display": evento.destino_display,
        "responsavel_display": _responsavel_display(evento),
        "unidade_display": _unidade_display(evento),
        "motivo_resumido": motivo_resumido,
        "temporal_label": temporal_label,
        "temporal_tone": temporal_tone,
        # Grupos de documentos
        "oficios": oficios,
        "oficios_count": len(oficios),
        "oficios_url": _etapa_url(3),
        "planos": planos,
        "planos_count": len(planos),
        "planos_url": _etapa_url(4),
        "ordens": ordens,
        "ordens_count": len(ordens),
        "ordens_url": _etapa_url(4),
        "termos": termos,
        "termos_count": len(termos),
        "termos_url": _etapa_url(5),
        "documentos_total": len(oficios) + len(planos) + len(ordens) + len(termos),
        # URLs / ações
        "detalhe_url": detalhe_url,
        "editar_url": editar_url,
    }
