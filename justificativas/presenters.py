from urllib.parse import urlencode

from core.presenters.badges import build_badge
from core.presenters.meta import build_meta
from django.urls import reverse
from django.utils import timezone

from .models import Justificativa
from .models import ModeloJustificativa
from .services import avaliar_etapa_justificativa_oficio
from .services import avaliar_justificativa_oficio


def apresentar_linha_lista_simples_modelo_justificativa(
    modelo: ModeloJustificativa,
    edit_url: str = "#",
    delete_url: str = "#",
    delete_modal: bool = False,
    next_url: str = "",
):
    """Mesmo contrato de `apresentar_linha_lista_simples_modelo_motivo` (lista simples)."""
    badges = []
    if modelo.is_padrao:
        badges.append(build_badge("Padrão", "default"))
    texto = (modelo.texto or "").strip()
    if len(texto) > 90:
        texto = f"{texto[:90]}..."
    set_default_url = (
        reverse("justificativas:modelo_definir_padrao", args=[modelo.pk])
        if not modelo.is_padrao
        else ""
    )
    if set_default_url and next_url:
        set_default_url = f"{set_default_url}?{urlencode({'next': next_url})}"
    return {
        "title": modelo.nome,
        "badges": badges,
        "meta": [
            build_meta("Prévia", texto or "—"),
        ],
        "edit_url": edit_url,
        "delete_url": delete_url,
        "delete_modal": delete_modal,
        "set_default_url": set_default_url,
    }


def apresentar_linha_lista_simples_justificativa(
    justificativa: Justificativa,
    *,
    edit_url: str | None = None,
    delete_url: str | None = None,
    delete_modal: bool = False,
    pdf_url: str | None = None,
    docx_url: str | None = None,
):
    oficio = justificativa.oficio
    texto = (justificativa.texto or "").strip()
    if len(texto) > 110:
        texto = f"{texto[:110]}..."

    badges = []

    return {
        "avatar": "JT",
        "title": f"Oficio {oficio.numero_formatado}",
        "badges": badges,
        "meta": [
            build_meta("Modelo", justificativa.modelo.nome if justificativa.modelo_id else "-"),
            build_meta("Texto", texto or "-"),
            build_meta("Atualizada", timezone.localtime(justificativa.updated_at).strftime("%d/%m/%Y %H:%M")),
        ],
        "search_extra": " ".join(
            part
            for part in [
                oficio.protocolo,
                oficio.assunto,
                justificativa.modelo.nome if justificativa.modelo_id else "",
                texto,
            ]
            if part
        ),
        "edit_url": edit_url or reverse("oficios:wizard_justificativa", args=[oficio.pk]),
        "delete_url": delete_url,
        "delete_modal": delete_modal,
        "pdf_url": pdf_url or reverse("oficios:baixar_justificativa_documento", args=[oficio.pk, "pdf"]),
        "docx_url": docx_url or reverse("oficios:baixar_justificativa_documento", args=[oficio.pk, "docx"]),
    }


def apresentar_justificativa_wizard_context(oficio):
    """
    Contexto de apresentação da etapa de justificativa (badge, alertas, labels).
    """
    etapa = avaliar_etapa_justificativa_oficio(oficio)
    ev = avaliar_justificativa_oficio(oficio)

    obrigatoria = bool(etapa.get("obrigatoria"))
    if obrigatoria:
        badge_label = "Obrigatória"
        badge_class = "status-chip--danger"
    else:
        badge_label = "Não exigida"
        badge_class = "status-chip--muted"

    primeira = etapa.get("primeira_saida")
    primeira_label = "—"
    if primeira is not None:
        local = primeira.astimezone(timezone.get_current_timezone())
        primeira_label = local.strftime("%d/%m/%Y %H:%M")

    if obrigatoria:
        resultado_label = "Justificativa obrigatória"
    elif ev.get("status") == "unknown":
        resultado_label = "Aguardando dados do roteiro"
    else:
        resultado_label = "Justificativa dispensada"

    help_texto = (
        "Explique o motivo do cadastramento ou emissão com antecedência igual ou inferior a "
        f"{etapa['prazo_dias']} dias."
        if obrigatoria
        else "Opcional: registre uma justificativa complementar se necessário."
    )

    return {
        "etapa": etapa,
        "regra": ev,
        "badge_label": badge_label,
        "badge_class": badge_class,
        "alerta_regra": ev.get("motivo_regra") or "",
        "data_criacao_label": ev["data_criacao"].strftime("%d/%m/%Y"),
        "primeira_saida_label": primeira_label,
        "dias_antecedencia_label": (
            str(etapa["dias_antecedencia"])
            if etapa["dias_antecedencia"] is not None
            else "—"
        ),
        "prazo_dias_label": str(etapa["prazo_dias"]),
        "status_etapa_label": etapa["status"],
        "pendencias": etapa.get("pendencias") or [],
        "resultado_label": resultado_label,
        "help_texto": help_texto,
    }
