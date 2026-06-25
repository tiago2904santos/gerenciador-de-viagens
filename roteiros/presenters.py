from decimal import Decimal, InvalidOperation

from django.urls import reverse
from django.utils import timezone

from core.presenters.actions import build_delete_action
from core.presenters.actions import build_edit_action
from core.presenters.actions import build_open_action
from core.presenters.meta import build_meta
from .models import Roteiro
from .services import montar_contexto_editor_roteiro
from .services.diarias import infer_tipo_destino_from_paradas
from .services.valor_extenso import valor_por_extenso_ptbr


def _label_cidade_uf(cidade, estado):
    if cidade:
        uf = cidade.estado.sigla if getattr(cidade, "estado", None) else getattr(cidade, "uf", "")
        return f"{cidade.nome}/{uf}"
    if estado:
        return estado.sigla
    return "—"


def _format_brl(valor):
    if valor is None:
        return None
    try:
        dec = valor if isinstance(valor, Decimal) else Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return None
    dec = dec.quantize(Decimal("0.01"))
    texto = f"{dec:.2f}"
    inteiro, frac = texto.split(".")
    inteiro_fmt = f"{int(inteiro):,}".replace(",", ".")
    return f"R$ {inteiro_fmt},{frac}"


def _format_trecho_dt(dt):
    if not dt:
        return "—"
    return f"{dt:%d/%m/%Y %H:%M}"


def _composicao_diarias_linhas(texto):
    raw = (texto or "").strip()
    if not raw:
        return []
    linhas = []
    for chunk in raw.replace("\n", "+").split("+"):
        item = chunk.strip()
        if item:
            linhas.append(item)
    return linhas


def _roteiro_card_layout(trechos_count):
    if trechos_count >= 4:
        return "diarias-dashboard"
    if trechos_count == 3:
        return "expanded-3"
    return "compact"


def _trechos_visiveis(trechos_payload):
    if len(trechos_payload) <= 4:
        return trechos_payload, None

    restantes = trechos_payload[3:]
    destinos_restantes = [t["destino"] for t in restantes if t.get("destino")]
    return trechos_payload[:3], {
        "count": len(restantes),
        "destinos": destinos_restantes,
        "texto": ", ".join(destinos_restantes),
    }


def _inferir_tipo_destino(destinos):
    paradas = []
    for destino in destinos:
        cidade = getattr(destino, "cidade", None)
        estado = getattr(destino, "estado", None)
        cidade_nome = getattr(cidade, "nome", None)
        uf = getattr(estado, "sigla", None) or getattr(cidade, "uf", None)
        if cidade_nome or uf:
            paradas.append((cidade_nome, uf))
    return infer_tipo_destino_from_paradas(paradas) if paradas else ""


def _roteiro_inicio_fim(roteiro):
    """Resolve as datas de início e fim do roteiro, normalizando a ordem."""
    inicio = (
        getattr(roteiro, "saida_dt", None)
        or getattr(roteiro, "chegada_dt", None)
        or getattr(roteiro, "retorno_saida_dt", None)
        or getattr(roteiro, "retorno_chegada_dt", None)
    )
    fim = (
        getattr(roteiro, "retorno_chegada_dt", None)
        or getattr(roteiro, "chegada_dt", None)
        or getattr(roteiro, "saida_dt", None)
        or getattr(roteiro, "retorno_saida_dt", None)
    )
    if inicio and fim and fim < inicio:
        inicio, fim = fim, inicio
    return inicio, fim


def _format_roteiro_dt(dt):
    if not dt:
        return ""
    tz = timezone.get_current_timezone()
    if timezone.is_aware(dt):
        dt = dt.astimezone(tz)
    return dt.strftime("%d/%m/%Y %H:%M")


def _temporal_badge_roteiro(roteiro):
    """Chip de quanto falta / em andamento / quanto tempo passou."""
    inicio, fim = _roteiro_inicio_fim(roteiro)
    if not inicio:
        return None, "muted"
    tz = timezone.get_current_timezone()
    today = timezone.localdate()
    inicio_date = inicio.astimezone(tz).date() if timezone.is_aware(inicio) else inicio.date()
    fim_date = inicio_date
    if fim:
        fim_date = fim.astimezone(tz).date() if timezone.is_aware(fim) else fim.date()
    if today < inicio_date:
        dias = (inicio_date - today).days
        if dias == 1:
            return "falta 1 dia", "warning"
        return f"faltam {dias} dias", "warning"
    if inicio_date <= today <= fim_date:
        if today == inicio_date:
            return "começa hoje", "info"
        return "em andamento", "info"
    dias = (today - fim_date).days
    if dias == 0:
        return "foi hoje", "success"
    if dias == 1:
        return "foi ontem", "success"
    return f"há {dias} dias", "success"


def _roteiro_faixa_lateral_class(roteiro):
    now = timezone.now()
    inicio, fim = _roteiro_inicio_fim(roteiro)

    status_code = getattr(roteiro, "status", "") or ""
    if status_code == Roteiro.STATUS_RASCUNHO:
        if inicio and now >= inicio:
            return "roteiro-list-card--faixa-rascunho-atrasado"
        return "roteiro-list-card--faixa-rascunho-futuro"

    if status_code == Roteiro.STATUS_FINALIZADO:
        if fim and now >= fim:
            return "roteiro-list-card--faixa-finalizado-concluido"
        return "roteiro-list-card--faixa-finalizado-antecipado"

    return "roteiro-list-card--faixa-neutro"


def apresentar_roteiro_card(roteiro):
    origem_txt = _label_cidade_uf(roteiro.origem_cidade, roteiro.origem_estado)
    destinos_todos = list(roteiro.destinos.all()) if roteiro.pk else []
    destino_principal_txt = "—"
    if destinos_todos:
        primeiro = destinos_todos[0]
        destino_principal_txt = _label_cidade_uf(primeiro.cidade, primeiro.estado)

    if destino_principal_txt != "—":
        titulo_rota = f"{origem_txt} → {destino_principal_txt}"
    else:
        titulo_rota = origem_txt if origem_txt != "—" else f"Roteiro #{roteiro.pk}"

    edit_url = reverse("roteiros:editar", args=[roteiro.pk])
    delete_url = reverse("roteiros:excluir", args=[roteiro.pk])

    status = roteiro.get_status_display() if hasattr(roteiro, "get_status_display") else roteiro.status
    status_code = getattr(roteiro, "status", "") or ""
    if status_code == Roteiro.STATUS_FINALIZADO:
        status_chip_class = "status-chip--completed"
        status_variant = "finalizado"
    elif status_code == Roteiro.STATUS_RASCUNHO:
        status_chip_class = "status-chip--draft"
        status_variant = "rascunho"
    else:
        status_chip_class = "status-chip--muted"
        status_variant = "outro"

    trechos_payload = []
    for trecho in roteiro.trechos.all():
        orig_t = _label_cidade_uf(trecho.origem_cidade, trecho.origem_estado)
        dest_t = _label_cidade_uf(trecho.destino_cidade, trecho.destino_estado)
        trechos_payload.append(
            {
                "rota": f"{orig_t} → {dest_t}",
                "destino": dest_t,
                "saida": _format_trecho_dt(trecho.saida_dt),
                "chegada": _format_trecho_dt(trecho.chegada_dt),
            }
        )

    diaria_moeda = _format_brl(getattr(roteiro, "valor_diarias", None))
    diaria_resumo = (roteiro.quantidade_diarias or "").strip()
    diaria_composicao_linhas = _composicao_diarias_linhas(diaria_resumo)
    diaria_vazio = not diaria_moeda and not diaria_composicao_linhas
    trechos_count = len(trechos_payload)
    trechos_visiveis, trechos_resumo = _trechos_visiveis(trechos_payload)
    roteiro_card_layout = _roteiro_card_layout(trechos_count)
    diaria_extenso = (roteiro.valor_diarias_extenso or "").strip()
    if (not diaria_extenso or diaria_extenso == "(preencher manualmente)") and diaria_moeda:
        diaria_extenso = valor_por_extenso_ptbr(getattr(roteiro, "valor_diarias", None))

    inicio_dt, fim_dt = _roteiro_inicio_fim(roteiro)
    temporal_label, temporal_tone = _temporal_badge_roteiro(roteiro)

    return {
        "title": titulo_rota,
        "rota_display": titulo_rota,
        "inicio_display": _format_roteiro_dt(inicio_dt),
        "fim_display": _format_roteiro_dt(fim_dt),
        "temporal_label": temporal_label,
        "temporal_tone": temporal_tone,
        "valor_diarias_display": diaria_moeda or "",
        "valor_diarias_extenso": diaria_extenso,
        "editar_url": edit_url,
        "excluir_url": delete_url,
        "subtitle": "Roteiro reutilizável para documentos",
        "status": status,
        "status_chip_label": status,
        "status_chip_class": status_chip_class,
        "status_variant": status_variant,
        "faixa_lateral_class": _roteiro_faixa_lateral_class(roteiro),
        "diaria_moeda": diaria_moeda,
        "diaria_resumo": diaria_resumo,
        "diaria_extenso": diaria_extenso,
        "diaria_composicao_linhas": diaria_composicao_linhas,
        "diaria_tipo_destino": _inferir_tipo_destino(destinos_todos),
        "diaria_vazio": diaria_vazio,
        "trechos": trechos_visiveis,
        "trechos_count": trechos_count,
        "trechos_resumo": trechos_resumo,
        "roteiro_card_layout": roteiro_card_layout,
        "actions": [build_open_action(edit_url), build_edit_action(edit_url), build_delete_action(delete_url)],
    }


def apresentar_linha_lista_simples_roteiro(roteiro, *, edit_url="#", delete_url="#", delete_modal=False):
    card = apresentar_roteiro_card(roteiro)
    periodo = "—"
    if card["inicio_display"] or card["fim_display"]:
        periodo = f"{card['inicio_display'] or '—'} a {card['fim_display'] or '—'}"

    trechos_count = card["trechos_count"]
    trechos_label = "1 trecho" if trechos_count == 1 else f"{trechos_count} trechos"

    return {
        "avatar": "RT",
        "title": card["rota_display"],
        "badges": [],
        "meta": [
            build_meta("Período", periodo),
            build_meta("Trechos", trechos_label),
            build_meta("Valor", card["valor_diarias_display"] or "—"),
        ],
        "search_extra": " ".join(t["rota"] for t in card["trechos"]),
        "status_value": card["status_variant"],
        "edit_url": edit_url,
        "delete_url": delete_url,
        "delete_modal": delete_modal,
    }


def apresentar_contexto_formulario_roteiro_avulso(
    *,
    evento,
    form,
    obj,
    destinos_atuais,
    trechos_list,
    roteiro_state,
    route_options,
):
    """Contexto do wizard de roteiro avulso (dict para template); sem HTML."""
    return montar_contexto_editor_roteiro(
        evento=evento,
        form=form,
        obj=obj,
        destinos_atuais=destinos_atuais,
        trechos_list=trechos_list,
        is_avulso=True,
        roteiro_state=roteiro_state,
        route_options=route_options,
    )
