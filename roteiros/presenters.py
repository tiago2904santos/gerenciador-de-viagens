import json
from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.urls import reverse
from django.utils import timezone

from core import entity_cards
from core.presenters.actions import build_delete_action
from core.presenters.actions import build_edit_action
from core.presenters.actions import build_open_action
from core.presenters.meta import build_meta
from .models import Roteiro
from .roteiro_logic import _build_roteiro_state_from_estrutura
from .roteiro_logic import _calculate_avulso_diarias_from_state
from .roteiro_logic import _get_parana_estado
from .roteiro_logic import _serialize_roteiro_state
from .services.diarias import formatar_valor_diarias
from .services.diarias import infer_tipo_destino_from_paradas
from .services.map_defaults import build_roteiro_map_defaults
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
    if timezone.is_aware(dt):
        dt = dt.astimezone(timezone.get_current_timezone())
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


def _inferir_tipo_destino(destinos, capitais=None):
    paradas = []
    for destino in destinos:
        cidade = getattr(destino, "cidade", None)
        estado = getattr(destino, "estado", None)
        cidade_nome = getattr(cidade, "nome", None)
        uf = getattr(estado, "sigla", None) or getattr(cidade, "uf", None)
        if cidade_nome or uf:
            paradas.append((cidade_nome, uf))
    return infer_tipo_destino_from_paradas(paradas, capitais) if paradas else ""


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


def apresentar_roteiro_card(roteiro, *, todos_trechos=False, capitais=None):
    origem_txt = _label_cidade_uf(roteiro.origem_cidade, roteiro.origem_estado)
    destinos_todos = list(roteiro.destinos.all()) if roteiro.pk else []
    destinos_txt_list = [
        _label_cidade_uf(destino.cidade, destino.estado) for destino in destinos_todos
    ]
    destinos_txt_list = [txt for txt in destinos_txt_list if txt and txt != "—"]

    if destinos_txt_list:
        titulo_rota = " → ".join([origem_txt, *destinos_txt_list])
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
    # Lista de roteiros resume (>4 → 3 + resumo). Documentos precisa da lista completa no scroll.
    if todos_trechos:
        trechos_visiveis, trechos_resumo = trechos_payload, None
    else:
        trechos_visiveis, trechos_resumo = _trechos_visiveis(trechos_payload)
    roteiro_card_layout = _roteiro_card_layout(trechos_count)
    diaria_extenso = (roteiro.valor_diarias_extenso or "").strip()
    if (not diaria_extenso or diaria_extenso == "(preencher manualmente)") and diaria_moeda:
        diaria_extenso = valor_por_extenso_ptbr(getattr(roteiro, "valor_diarias", None))

    inicio_dt, fim_dt = _roteiro_inicio_fim(roteiro)
    temporal_label, temporal_tone = _temporal_badge_roteiro(roteiro)

    inicio_display = _format_roteiro_dt(inicio_dt)
    fim_display = _format_roteiro_dt(fim_dt)
    header_items = [
        entity_cards.header_item(
            "Roteiro", titulo_rota, wide=True, value_class="record-card__info-value--rota"
        )
    ]
    header_chips = [entity_cards.chip(temporal_tone, temporal_label)] if temporal_label else []

    return {
        "search_text": " ".join(
            [titulo_rota, *[t["rota"] for t in trechos_visiveis]]
        ).strip(),
        "header": entity_cards.header(header_items, header_chips),
        "footer": entity_cards.footer(
            edit_url=edit_url,
            edit_aria="Editar roteiro",
            delete_url=delete_url,
            delete_aria="Excluir roteiro",
        ),
        "title": titulo_rota,
        "rota_display": titulo_rota,
        "inicio_display": inicio_display,
        "fim_display": fim_display,
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
        "diaria_tipo_destino": _inferir_tipo_destino(destinos_todos, capitais),
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
        "badges": [{"text": "Cancelado", "variant": "danger"}] if roteiro.cancelado else [],
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


def apresentar_pagina_editor_roteiro(
    *,
    contexto_editor,
    titulo,
    descricao,
    back_url,
    back_label,
    form_action,
    roteiro=None,
):
    """`BE-11`: o invólucro de página do editor, que `novo` e `editar` escreviam igual.

    `back_url` alimenta as duas chaves de voltar — nas duas views a expressão já era a
    mesma, escrita duas vezes. `delete_url` só aparece quando há `roteiro`: numa página
    de criação não há o que excluir, e a chave não pode surgir vazia (o template testa
    presença, não valor).
    """
    contexto = {
        "page_title": titulo,
        "page_description": descricao,
        "back_url": back_url,
        "wizard_header": {
            "title": titulo,
            "description": "Roteiro e diárias",
            "status_label": (
                roteiro.get_status_display() if hasattr(roteiro, "get_status_display") else ""
            ),
            "status_variant": _variante_de_status_do_roteiro(roteiro),
        },
        "wizard_back_label": back_label,
        "wizard_back_url": back_url,
        "wizard_page_steps": [],
        "roteiro_editor_oficio": True,
        "roteiro_form_action": form_action,
    }
    if roteiro is not None:
        contexto["delete_url"] = reverse("roteiros:excluir", args=[roteiro.pk])
    contexto.update(contexto_editor)
    return contexto


def _variante_de_status_do_roteiro(roteiro):
    if roteiro is None:
        return ""
    return "draft" if roteiro.status == Roteiro.STATUS_RASCUNHO else "active"


# ---------------------------------------------------------------------------
# `BE-13` fatia 2 — o contexto do editor de roteiro.
#
# Estas três funções vieram de `roteiros/roteiro_logic.py`, onde eram privadas e
# conviviam com parsing e persistência. Montar o dict que o template consome é
# trabalho de presenter (`docs/PADRAO_APP.md:10`), e é só isso que elas fazem.
#
# `montar_contexto_editor_roteiro` veio junto, de `services/roteiro_editor.py`:
# deixá-la lá faria um service importar um presenter, que é a violação de camada
# que o `BE-13` existe para corrigir.
#
# As quatro funções `_`-privadas que continuam em `roteiro_logic` são importadas
# pelo nome privado — feio, e é o que `roteiro_editor.py` e `route_point_builder.py`
# já faziam antes desta fatia. O contrato público de cada grupo é a fatia 3.
# ---------------------------------------------------------------------------


def montar_contexto_editor_roteiro(
    *,
    evento,
    form,
    obj,
    destinos_atuais,
    trechos_list,
    is_avulso,
    roteiro_state,
    route_options,
    diarias_quantidade_servidores=1,
):
    """Contexto do editor de roteiro para o template (dict; sem HTML)."""
    return _build_roteiro_form_context(
        evento=evento,
        form=form,
        obj=obj,
        destinos_atuais=destinos_atuais,
        trechos_list=trechos_list,
        is_avulso=is_avulso,
        roteiro_state=roteiro_state,
        route_options=route_options,
        diarias_quantidade_servidores=diarias_quantidade_servidores,
    )


def _trechos_list_json_compat(trechos_list):
    """Serializa trechos para trechos_json (string) e para json_script no template."""
    rows = []
    for row in trechos_list or []:
        item = {}
        for k, v in row.items():
            if v is None:
                item[k] = None
            elif hasattr(v, 'isoformat'):
                item[k] = v.isoformat()
            elif isinstance(v, Decimal):
                item[k] = float(v)
            else:
                item[k] = v
        rows.append(item)
    return rows, json.dumps(rows)

def _build_roteiro_diarias_fallback(roteiro, *, quantidade_servidores: int = 1):
    if not roteiro:
        return None
    if roteiro.valor_diarias is None and not roteiro.quantidade_diarias and not roteiro.valor_diarias_extenso:
        return None
    total_valor_decimal = roteiro.valor_diarias
    if total_valor_decimal is None:
        return None
    total_valor = formatar_valor_diarias(total_valor_decimal)
    qs = max(0, int(quantidade_servidores or 0))
    if qs == 0:
        valor_por_servidor_decimal = Decimal('0.00')
        valor_por_servidor_txt = formatar_valor_diarias(valor_por_servidor_decimal)
    elif qs == 1:
        valor_por_servidor_decimal = total_valor_decimal
        valor_por_servidor_txt = total_valor
    else:
        valor_por_servidor_decimal = (
            total_valor_decimal / Decimal(qs)
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        valor_por_servidor_txt = formatar_valor_diarias(valor_por_servidor_decimal)
    return {
        'periodos': [],
        'totais': {
            'total_diarias': roteiro.quantidade_diarias or '',
            'total_horas': '',
            'total_valor': total_valor,
            'total_valor_decimal': total_valor_decimal,
            'valor_extenso': roteiro.valor_diarias_extenso or '',
            'quantidade_servidores': qs,
            'diarias_por_servidor': roteiro.quantidade_diarias or '',
            'valor_por_servidor': valor_por_servidor_txt,
            'valor_por_servidor_decimal': valor_por_servidor_decimal,
            'valor_unitario_referencia': '',
        },
        'tipo_destino': '',
    }

def _build_roteiro_form_context(
    *,
    evento,
    form,
    obj,
    destinos_atuais,
    trechos_list,
    is_avulso=False,
    roteiro_state=None,
    route_options=None,
    seed_source_label='',
    diarias_quantidade_servidores=1,
):
    """
    Monta contexto completo para o formulário de roteiro (guiado e avulso).
    Quando roteiro_state é fornecido, usa diretamente; caso contrário, constrói
    a partir de trechos_list + destinos_atuais (compatibilidade com forms guiados).
    """
    if roteiro_state is None:
        instance = obj or form.instance
        sede_estado_id = getattr(instance, 'origem_estado_id', None)
        sede_cidade_id = getattr(instance, 'origem_cidade_id', None)
        roteiro_state = _build_roteiro_state_from_estrutura(
            trechos_list,
            [{'estado_id': d.get('estado_id'), 'cidade_id': d.get('cidade_id')} for d in (destinos_atuais or [])],
            sede_estado_id,
            sede_cidade_id,
            seed_source_label,
        )
        roteiro_state['roteiro_modo'] = 'ROTEIRO_PROPRIO'

    from roteiros import selectors

    sede_estado_id = roteiro_state.get("sede_estado_id")
    sede_cidade_id = roteiro_state.get("sede_cidade_id")
    estados_qs = selectors.listar_estados_para_select()
    sede_cidades_qs = selectors.listar_cidades_para_select(estado_id=sede_estado_id)
    qs_ctx = max(0, int(diarias_quantidade_servidores or 0))
    diarias_resultado = None
    try:
        diarias_resultado = _calculate_avulso_diarias_from_state(
            roteiro_state,
            quantidade_servidores=qs_ctx,
        )
    except ValueError:
        diarias_resultado = _build_roteiro_diarias_fallback(
            obj or form.instance,
            quantidade_servidores=qs_ctx,
        )
    if diarias_resultado is None:
        diarias_resultado = _build_roteiro_diarias_fallback(
            obj or form.instance,
            quantidade_servidores=qs_ctx,
        )
    destino_estado_fixo = _get_parana_estado()
    rows_src = list(trechos_list or [])
    if not rows_src:
        ts = (roteiro_state or {}).get('trechos') or []
        if ts:
            rows_src = list(ts)
    initial_trechos_data, trechos_json = _trechos_list_json_compat(rows_src)
    serialized_roteiro_state = _serialize_roteiro_state(roteiro_state)
    route_options_json = route_options or []
    if is_avulso:
        serialized_roteiro_state.pop('roteiro_evento_id', None)
        route_options_json = deepcopy(route_options_json)
        for route_option in route_options_json:
            state = route_option.get('state') or {}
            state.pop('roteiro_evento_id', None)
    from roteiros.services.routing.route_service import serialize_existing_route

    roteiro_mapa_inicial = (
        serialize_existing_route(obj)
        if obj and getattr(obj, "pk", None)
        else {"roteiro_id": None, "status": "pendente", "route": None}
    )
    roteiro_mapa_inicial.update(build_roteiro_map_defaults())
    return {
        'evento': evento,
        'object': obj,
        'form': form,
        'destinos_atuais': destinos_atuais,
        'estados': estados_qs,
        'api_cidades_por_estado_url': reverse('roteiros:api_cidades_por_estado', kwargs={'estado_id': 0}),
        'trechos': trechos_list,
        'trechos_json': trechos_json,
        'initial_trechos_data': initial_trechos_data,
        'roteiro_editor_state_json': serialized_roteiro_state,
        'roteiro_diarias_resultado': diarias_resultado,
        'roteiro_seed_source_label': roteiro_state.get('seed_source_label', ''),
        'api_calcular_diarias_url': reverse('roteiros:calcular_diarias'),
        'api_calcular_rota_url': reverse('roteiros:calcular_rota'),
        'api_calcular_rota_preview_url': reverse('roteiros:calcular_rota_preview'),
        'roteiro_mapa_inicial': roteiro_mapa_inicial,
        'roteiro_modo': roteiro_state.get('roteiro_modo', 'ROTEIRO_PROPRIO'),
        'roteiro_id': roteiro_state.get('roteiro_evento_id'),
        'roteiro_evento_id': roteiro_state.get('roteiro_evento_id'),
        'roteiros_evento': route_options or [],
        'roteiro_routes_json': route_options_json,
        'has_event_routes': bool(route_options),
        'is_avulso': is_avulso,
        'retorno_state': roteiro_state.get('retorno', {}),
        'sede_estado_id': sede_estado_id,
        'sede_cidade_id': sede_cidade_id,
        'sede_cidades_qs': sede_cidades_qs,
        'destino_estado_fixo_id': getattr(destino_estado_fixo, 'pk', None),
        'destino_estado_fixo_nome': (
            f'{destino_estado_fixo.nome} ({destino_estado_fixo.sigla})'
            if destino_estado_fixo
            else 'Paraná (PR)'
        ),
        'diarias_quantidade_servidores': qs_ctx,
    }
