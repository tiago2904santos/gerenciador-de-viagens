from __future__ import annotations

from django.urls import reverse
from django.utils import timezone

from oficios.presenters import _iniciais_nome_servidor


def _temporal_badge_os(ordem):
    inicio = ordem.data_evento_inicio
    if not inicio:
        return None, "muted"
    fim = ordem.data_evento_fim or inicio
    today = timezone.localdate()
    if today < inicio:
        dias = (inicio - today).days
        if dias == 1:
            return "falta 1 dia", "warning"
        return f"faltam {dias} dias", "warning"
    if inicio <= today <= fim:
        if today == inicio:
            return "começa hoje", "info"
        return "em andamento", "info"
    dias = (today - fim).days
    if dias == 0:
        return "foi hoje", "success"
    if dias == 1:
        return "foi ontem", "success"
    return f"há {dias} dias", "success"


def _servidores_display_os(ordem):
    motorista_pks = set()
    for oficio in ordem.oficios.all():
        if oficio.motorista_id:
            motorista_pks.add(oficio.motorista_id)

    cards = []
    for servidor in ordem.servidores.all():
        cargo_nome = servidor.cargo.nome if servidor.cargo_id and servidor.cargo else ""
        unidade_nome = str(servidor.unidade) if servidor.unidade_id else ""
        cards.append(
            {
                "initials": _iniciais_nome_servidor(servidor.nome),
                "name": servidor.nome,
                "cargo": cargo_nome,
                "unidade": unidade_nome,
                "is_motorista": servidor.pk in motorista_pks,
            },
        )
    return cards


def _destinos_display_os(ordem):
    destinos = list(ordem.destinos.select_related("estado").order_by("nome"))
    if not destinos:
        return ""
    parts = [f"{d.nome} ({d.estado.sigla})" for d in destinos[:3]]
    result = ", ".join(parts)
    if len(destinos) > 3:
        result += f" +{len(destinos) - 3}"
    return result


def _oficios_vinculados_os(ordem):
    items = []
    for oficio in ordem.oficios.all():
        try:
            url = reverse("oficios:dados_viajantes", args=[oficio.pk])
        except Exception:
            url = ""
        protocolo = ""
        try:
            from core.utils.masks import format_protocolo
            protocolo = format_protocolo(oficio.protocolo) or ""
        except Exception:
            pass
        items.append(
            {
                "numero": oficio.numero_formatado,
                "protocolo": protocolo,
                "url": url,
            },
        )
    return items


def _periodo_display_curto(ordem) -> str:
    inicio = ordem.data_evento_inicio
    fim = ordem.data_evento_fim
    if not inicio:
        return ""
    if not fim or fim == inicio:
        return inicio.strftime("%d/%m")
    if inicio.year == fim.year:
        return f"{inicio.strftime('%d/%m')} a {fim.strftime('%d/%m')}"
    return f"{inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}"


def apresentar_ordem_servico_card(ordem):
    data_criacao_display = ""
    if ordem.created_at:
        try:
            tz = timezone.get_current_timezone()
            dt = ordem.created_at
            if timezone.is_aware(dt):
                dt = dt.astimezone(tz)
            data_criacao_display = dt.strftime("%d/%m/%Y")
        except Exception:
            pass

    temporal_label, temporal_tone = _temporal_badge_os(ordem)

    motivo = (ordem.motivo or "").strip()
    motivo_resumido = motivo
    if len(motivo) > 240:
        motivo_resumido = motivo[:240] + "…"

    return {
        "pk": ordem.pk,
        "numero_display": ordem.numero_formatado,
        "data_criacao_display": data_criacao_display,
        "periodo_display": _periodo_display_curto(ordem),
        "destinos_display": _destinos_display_os(ordem),
        "temporal_label": temporal_label,
        "temporal_tone": temporal_tone,
        "servidores": _servidores_display_os(ordem),
        "servidores_count": ordem.servidores.count(),
        "oficios_vinculados": _oficios_vinculados_os(ordem),
        "motivo": motivo,
        "motivo_resumido": motivo_resumido,
        "editar_url": reverse("ordens_servico:editar", args=[ordem.pk]),
        "docx_url": reverse("ordens_servico:baixar_docx", args=[ordem.pk]),
        "pdf_url": reverse("ordens_servico:baixar_pdf", args=[ordem.pk]),
        "visualizar_url": reverse("ordens_servico:pdf_inline", args=[ordem.pk]),
        "excluir_url": reverse("ordens_servico:excluir", args=[ordem.pk]),
    }
