import json
import re
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
        "edit_fields_json": json.dumps(
            {"nome": modelo.nome, "texto": modelo.texto or ""}, ensure_ascii=False
        ),
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


def _roteiro_destino_label(item):
    if not item:
        return ""
    if item.cidade_id:
        return str(item.cidade)
    if item.estado_id:
        return str(item.estado)
    return str(item)


def _digits(value):
    return re.sub(r"\D", "", str(value or ""))


def apresentar_oficio_picker_summary(oficio):
    """Resumo para a lista de Ofício vinculado (mesmo contrato visual dos termos)."""
    roteiro = oficio.roteiro
    destino = ""
    roteiro_label = ""
    periodo = ""
    sede = ""
    if roteiro:
        sede_obj = roteiro.origem_cidade or roteiro.origem_estado
        sede = str(sede_obj) if sede_obj else ""
        destinos = list(roteiro.destinos.all())
        destinos.sort(key=lambda d: (d.ordem or 0, d.pk))
        destino_obj = destinos[0] if destinos else None
        destino = _roteiro_destino_label(destino_obj)
        destinos_label = ", ".join(_roteiro_destino_label(item) for item in destinos if item)
        roteiro_label = " -> ".join(part for part in [sede, destinos_label or destino] if part)
        if roteiro.saida_dt:
            inicio = roteiro.saida_dt.strftime("%d/%m/%Y")
            retorno = roteiro.retorno_chegada_dt or roteiro.retorno_saida_dt
            fim = retorno.strftime("%d/%m/%Y") if retorno else inicio
            periodo = inicio if fim == inicio else f"{inicio} a {fim}"

    servidores_termo = list(oficio.servidores_termo_autorizacao.all())
    servidores_oficio = list(oficio.servidores.all())
    servidores_nomes = []
    seen = set()
    for servidor in servidores_termo + servidores_oficio:
        if servidor.pk in seen:
            continue
        seen.add(servidor.pk)
        servidores_nomes.append(servidor.nome)

    viatura = str(oficio.viatura) if oficio.viatura_id else ""
    viatura_modelo = getattr(oficio.viatura, "modelo", "") if oficio.viatura_id else ""

    return {
        "id": oficio.pk,
        "label": f"Oficio {oficio.numero_formatado}",
        "numero": oficio.numero_formatado,
        "protocolo": oficio.protocolo or "",
        "sede": sede,
        "destino": destino,
        "roteiro": roteiro_label,
        "periodo": periodo,
        "servidores_nomes": servidores_nomes,
        "servidores_label": ", ".join(servidores_nomes),
        "viatura": viatura,
        "viatura_modelo": viatura_modelo,
        "search_text": " ".join(
            part
            for part in [
                oficio.numero_formatado,
                str(oficio.numero or ""),
                str(oficio.ano or ""),
                _digits(oficio.numero_formatado),
                oficio.protocolo or "",
                _digits(oficio.protocolo),
                sede,
                destino,
                roteiro_label,
                periodo,
                viatura,
                viatura_modelo,
                " ".join(servidores_nomes),
                oficio.assunto or "",
            ]
            if part
        ),
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
