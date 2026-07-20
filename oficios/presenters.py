import json

from core import entity_cards
from core.presenters.actions import build_action
from core.presenters.actions import build_delete_action
from core.presenters.actions import build_edit_action
from core.presenters.badges import build_badge
from core.presenters.meta import build_meta
from core.utils.masks import format_placa
from core.utils.masks import format_protocolo
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode

from .models import Oficio


def _format_brl_diarias(value) -> str:
    """Exibição legível do valor das diárias (sem dependência de locale)."""
    if value is None:
        return "—"
    d = Decimal(str(value)).quantize(Decimal("0.01"))
    s = f"{d:.2f}"
    whole, cents = s.split(".")
    whole_rev = whole[::-1]
    grouped = ".".join(whole_rev[i : i + 3] for i in range(0, len(whole_rev), 3))[::-1]
    return f"R$ {grouped},{cents}"


def _status_variant(status: str) -> str:
    if status in {Oficio.STATUS_GERADO, Oficio.STATUS_FINALIZADO}:
        return "status-chip--success"
    if status == Oficio.STATUS_ARQUIVADO:
        return "status-chip--muted"
    return "status-chip--warning"


def _oficio_faixa_lateral_class(status: str) -> str:
    if status in {Oficio.STATUS_GERADO, Oficio.STATUS_FINALIZADO}:
        return "roteiro-list-card--faixa-finalizado-concluido"
    if status == Oficio.STATUS_RASCUNHO:
        return "roteiro-list-card--faixa-rascunho-futuro"
    return "roteiro-list-card--faixa-neutro"


def _destino_display_oficio(oficio) -> str:
    if not oficio.roteiro_id:
        return ""
    destinos = list(oficio.roteiro.destinos.all())
    if not destinos:
        return ""
    parts = [_label_cidade_uf_trecho(d.cidade, d.estado) for d in destinos[:2]]
    result = ", ".join(parts)
    if len(destinos) > 2:
        result += f" +{len(destinos) - 2}"
    return result


def _data_evento_display_oficio(oficio) -> str:
    if not oficio.roteiro_id:
        return ""
    roteiro = oficio.roteiro
    saida_dt = roteiro.saida_dt
    if not saida_dt:
        return ""
    tz = timezone.get_current_timezone()
    saida_date = saida_dt.astimezone(tz).date() if timezone.is_aware(saida_dt) else saida_dt.date()
    chegada_dt = roteiro.retorno_chegada_dt or roteiro.chegada_dt
    if chegada_dt:
        chegada_date = chegada_dt.astimezone(tz).date() if timezone.is_aware(chegada_dt) else chegada_dt.date()
        if saida_date == chegada_date:
            return saida_date.strftime("%d/%m/%Y")
        if saida_date.year == chegada_date.year:
            return f"{saida_date.strftime('%d/%m')} a {chegada_date.strftime('%d/%m/%Y')}"
        return f"{saida_date.strftime('%d/%m/%Y')} a {chegada_date.strftime('%d/%m/%Y')}"
    return saida_date.strftime("%d/%m/%Y")


def _label_cidade_uf_trecho(cidade, estado) -> str:
    cidade_txt = str(cidade).upper() if cidade else ""
    estado_txt = getattr(estado, "sigla", "") if estado else ""
    if "/" in cidade_txt:
        return cidade_txt
    if estado_txt:
        return f"{cidade_txt}/{estado_txt}"
    return cidade_txt


def _format_dt_trecho(dt) -> str:
    if not dt:
        return ""
    tz = timezone.get_current_timezone()
    if timezone.is_aware(dt):
        dt = dt.astimezone(tz)
    return dt.strftime("%d/%m/%Y %H:%M")


def _temporal_badge_oficio(oficio):
    if not oficio.roteiro_id:
        return None, "muted"
    roteiro = oficio.roteiro
    saida_dt = roteiro.saida_dt
    if not saida_dt:
        return None, "muted"
    tz = timezone.get_current_timezone()
    today = timezone.localdate()
    saida_date = saida_dt.astimezone(tz).date() if timezone.is_aware(saida_dt) else saida_dt.date()
    chegada_dt = roteiro.retorno_chegada_dt or roteiro.chegada_dt
    end_date = saida_date
    if chegada_dt:
        end_date = chegada_dt.astimezone(tz).date() if timezone.is_aware(chegada_dt) else chegada_dt.date()
    if today < saida_date:
        dias = (saida_date - today).days
        if dias == 1:
            return "falta 1 dia", "warning"
        return f"faltam {dias} dias", "warning"
    if saida_date <= today <= end_date:
        if today == saida_date:
            return "começa hoje", "info"
        return "em andamento", "info"
    dias = (today - end_date).days
    if dias == 0:
        return "foi hoje", "success"
    if dias == 1:
        return "foi ontem", "success"
    return f"há {dias} dias", "success"


def apresentar_oficio_card(oficio, *, excluir_next_url=None):
    from termos.services import termo_oficio_assinado_info

    servidores = list(oficio.servidores.all())
    termos_pks = {s.pk for s in oficio.servidores_termo_autorizacao.all()}
    servidor_pks = {s.pk for s in servidores}
    motorista_pk = oficio.motorista_id

    # Motorista é carona quando: (a) modo manual, ou (b) servidor cadastrado mas fora do ofício
    if oficio.motorista_modo == Oficio.MOTORISTA_MODO_MANUAL and (oficio.motorista_manual_nome or "").strip():
        motorista_is_carona = True
    elif motorista_pk and motorista_pk not in servidor_pks:
        motorista_is_carona = True
    else:
        motorista_is_carona = False

    # Servidores — com cargo, unidade, badge motorista e botões de termo embutidos
    servidores_display = []
    for s in servidores:
        cargo_nome = s.cargo.nome if s.cargo_id and s.cargo else ""
        unidade_nome = str(s.unidade) if s.unidade_id else ""
        has_termo = s.pk in termos_pks
        termo_open_url = termo_pdf_url = termo_docx_url = ""
        assinado_info = {
            "assinado": False,
            "anexar_assinado_url": "",
            "assinado_nome_original": "",
            "assinado_view_url": "",
            "remover_assinado_url": "",
        }
        if has_termo:
            try:
                termo_open_url = reverse("termos:termo_servidor_pdf_inline", args=[oficio.pk, s.pk])
                termo_pdf_url = reverse("termos:baixar_termo_servidor", args=[oficio.pk, s.pk, "pdf"])
                termo_docx_url = reverse("termos:baixar_termo_servidor", args=[oficio.pk, s.pk, "docx"])
                assinado_info = termo_oficio_assinado_info(oficio, s)
            except Exception:
                pass
        servidores_display.append({
            "servidor_pk": s.pk,
            "initials": _iniciais_nome_servidor(s.nome),
            "name": s.nome,
            "cargo": cargo_nome,
            "unidade": unidade_nome,
            "is_motorista": bool(motorista_pk and s.pk == motorista_pk),
            "telefone": s.telefone_formatado if s.telefone else "",
            "has_termo": has_termo,
            "termo_open_url": termo_open_url,
            "termo_pdf_url": termo_pdf_url,
            "termo_docx_url": termo_docx_url,
            "termo_assinado": assinado_info["assinado"],
            "termo_anexar_assinado_url": assinado_info["anexar_assinado_url"],
            "termo_remover_assinado_url": assinado_info["remover_assinado_url"],
            "termo_assinado_nome_original": assinado_info["assinado_nome_original"],
            "termo_assinado_view_url": assinado_info["assinado_view_url"],
        })

    destino = _destino_display_oficio(oficio)
    data_evento = _data_evento_display_oficio(oficio)
    temporal_label, temporal_tone = ("", "") if oficio.cancelado else _temporal_badge_oficio(oficio)

    # Trechos e diárias do roteiro
    trechos_display = []
    valor_diarias_display = ""
    valor_diarias_extenso = ""
    roteiro_card = None
    if oficio.roteiro_id:
        from roteiros.presenters import apresentar_roteiro_card

        roteiro = oficio.roteiro
        for t in roteiro.trechos.all():
            orig = _label_cidade_uf_trecho(t.origem_cidade, t.origem_estado)
            dest = _label_cidade_uf_trecho(t.destino_cidade, t.destino_estado)
            trechos_display.append({
                "rota": f"{orig} → {dest}",
                "saida": _format_dt_trecho(t.saida_dt),
                "chegada": _format_dt_trecho(t.chegada_dt),
            })
        diarias_oficio = oficio.diarias_para_servidores()
        if diarias_oficio:
            valor_diarias_display = _format_brl_diarias(diarias_oficio["valor_decimal"])
            valor_diarias_extenso = (diarias_oficio["valor_extenso"] or "").strip()
        roteiro_card = apresentar_roteiro_card(roteiro, todos_trechos=True)
        roteiro_card.pop("actions", None)
        if diarias_oficio:
            roteiro_card["diaria_moeda"] = valor_diarias_display
            roteiro_card["valor_diarias_display"] = valor_diarias_display
            roteiro_card["diaria_extenso"] = valor_diarias_extenso
            roteiro_card["valor_diarias_extenso"] = valor_diarias_extenso
            roteiro_card["diaria_vazio"] = False

    # Transporte
    veiculo_placa = ""
    veiculo_modelo = ""
    veiculo_display = ""
    if oficio.viatura_id:
        v = oficio.viatura
        veiculo_placa = v.placa_formatada
        veiculo_modelo = (v.modelo or "").strip()
        veiculo_display = f"{veiculo_placa} – {veiculo_modelo}" if veiculo_modelo else veiculo_placa
    elif (oficio.transporte_placa_manual or "").strip():
        veiculo_placa = format_placa(oficio.transporte_placa_manual)
        veiculo_modelo = (oficio.transporte_modelo_manual or "").strip()
        veiculo_display = f"{veiculo_placa} – {veiculo_modelo}" if veiculo_modelo else veiculo_placa

    motorista_display = _motorista_label_oficio(oficio)
    if motorista_display == "—":
        motorista_display = ""

    # Justificativa
    justificativa = None
    try:
        j = oficio.justificativa
        texto = (j.texto or "").strip()
        if texto:
            status_label = "Preenchida"
            status_css_class = "oficio-lc__badge--success"
        elif getattr(j, "obrigatoria", False):
            status_label = "Pendente"
            status_css_class = "oficio-lc__badge--warning"
        else:
            status_label = ""
            status_css_class = ""

        if status_label:
            created_at_display = "—"
            raw_dt = getattr(j, "created_at", None)
            if raw_dt:
                tz = timezone.get_current_timezone()
                if timezone.is_aware(raw_dt):
                    raw_dt = raw_dt.astimezone(tz)
                created_at_display = raw_dt.strftime("%d/%m/%Y")
            texto_resumido = (texto[:200] + "…") if len(texto) > 200 else texto
            if not texto_resumido:
                texto_resumido = "Texto ainda não informado."
            justificativa = {
                "status_label": status_label,
                "status_css_class": status_css_class,
                "created_at_display": created_at_display,
                "texto_resumido": texto_resumido,
                "detail_url": reverse("oficios:wizard_justificativa", args=[oficio.pk]),
            }
    except Exception:
        pass

    if oficio.cancelado:
        status_chip_label = "Cancelado"
        status_chip_tone = "danger"
        status_variant = "cancelado"
    else:
        status_chip_label = oficio.get_status_display()
        status_chip_tone = (
            "success" if oficio.status in {Oficio.STATUS_GERADO, Oficio.STATUS_FINALIZADO}
            else ("muted" if oficio.status == Oficio.STATUS_ARQUIVADO else "warning")
        )
        status_variant = oficio.status.lower() if oficio.status else "outro"

    data_criacao_display = ""
    if oficio.data_criacao:
        try:
            data_criacao_display = oficio.data_criacao.strftime("%d/%m/%Y")
        except Exception:
            pass

    numero_display = oficio.numero_formatado
    protocolo_display = format_protocolo(oficio.protocolo) or ""
    editar_url = reverse("oficios:dados_viajantes", args=[oficio.pk])
    excluir_url = _excluir_url_oficio(oficio.pk, excluir_next_url)
    cancelar_url = reverse("oficios:cancelar", args=[oficio.pk])
    retificar_url = reverse("oficios:retificar", args=[oficio.pk])
    marcar_complementar_url = reverse("oficios:marcar_complementar", args=[oficio.pk])

    header_parts = [f"Nº {numero_display}"]
    if protocolo_display:
        header_parts.append(f"Protocolo {protocolo_display}")
    if destino:
        header_parts.append(destino)
    if data_evento:
        header_parts.append(data_evento)
    header_chips = []
    if oficio.retificado_documento:
        header_chips.append(entity_cards.chip("warning", "Retificado"))
    elif oficio.complementar_documento:
        header_chips.append(entity_cards.chip("info", "Complementar"))
    if temporal_label:
        header_chips.append(entity_cards.chip(temporal_tone, temporal_label))
    if oficio.cancelado:
        header_chips.append(entity_cards.chip("danger", "Cancelado"))

    search_parts = [numero_display, protocolo_display, destino]
    search_parts.extend(s["name"] for s in servidores_display)

    acoes_gerenciar = [
        entity_cards.menu_post(
            retificar_url,
            "Desfazer retificação" if oficio.retificado_documento else "Retificar ofício",
            "Atualizar o estado de retificação",
            "sync",
            "preview",
        ),
        entity_cards.menu_post(
            marcar_complementar_url,
            "Desfazer complementar" if oficio.complementar_documento else "Ofício complementar",
            "Identificar o documento como complementar",
            "plus",
            "edit",
        ),
    ]
    if not oficio.cancelado:
        acoes_gerenciar.append(
            entity_cards.menu_cancel(cancelar_url, numero_display, title="Cancelar ofício")
        )
    acoes_gerenciar.append(
        entity_cards.menu_delete(excluir_url, numero_display, title="Excluir ofício")
    )

    return {
        "search_text": " ".join(p for p in search_parts if p).strip(),
        "header": entity_cards.header(
            [entity_cards.header_item("Ofício", " · ".join(header_parts), wide=True, wrap=True)],
            header_chips,
        ),
        "status_value": status_variant,
        "cancel_note": oficio.motivo_cancelamento if oficio.cancelado else "",
        "footer": entity_cards.footer(
            edit_url=editar_url,
            edit_aria="Editar ofício",
            menus=[
                entity_cards.documents_menu(
                    f"oficio-document-menu-{oficio.pk}",
                    numero_display,
                    title="Documentos do ofício",
                    view_url=reverse("oficios:oficio_pdf_inline", args=[oficio.pk]),
                    pdf_url=reverse("oficios:baixar_documento", args=[oficio.pk, "pdf"]),
                    docx_url=reverse("oficios:baixar_documento", args=[oficio.pk, "docx"]),
                    view_title="Visualizar ofício",
                    docx_description="Arquivo editável do ofício",
                    trigger_aria=f"Abrir documentos do ofício {numero_display}",
                )
            ],
            danger_menus=[
                entity_cards.menu(
                    f"oficio-action-menu-{oficio.pk}",
                    "Gerenciar ofício",
                    numero_display,
                    acoes_gerenciar,
                    icon="settings",
                    trigger_icon="more",
                    trigger_variant="edit",
                    trigger_aria="Mais ações do ofício",
                    trigger_tooltip="Mais ações",
                )
            ],
        ),
        "oficio_pk": oficio.pk,
        "numero_display": numero_display,
        "protocolo_display": protocolo_display,
        "data_criacao_display": data_criacao_display,
        "destino_display": destino,
        "data_evento_display": data_evento,
        "status_chip_label": status_chip_label,
        "status_chip_tone": status_chip_tone,
        "status_variant": status_variant,
        "cancelado": oficio.cancelado,
        "motivo_cancelamento": oficio.motivo_cancelamento,
        "cancelar_url": cancelar_url,
        "retificado": oficio.retificado_documento,
        "retificar_url": retificar_url,
        "complementar": oficio.complementar_documento,
        "marcar_complementar_url": marcar_complementar_url,
        "temporal_label": temporal_label,
        "temporal_tone": temporal_tone,
        "servidores": servidores_display,
        "servidores_count": len(servidores),
        "custeio_display": oficio.get_custeio_display(),
        "transporte": _montar_transporte_resumo_documentos(oficio),
        "roteiro_card": roteiro_card,
        "veiculo_placa": veiculo_placa,
        "veiculo_modelo": veiculo_modelo,
        "veiculo_display": veiculo_display,
        "motorista_is_carona": motorista_is_carona,
        "motorista_display": motorista_display,
        "trechos": trechos_display,
        "valor_diarias_display": valor_diarias_display,
        "valor_diarias_extenso": valor_diarias_extenso,
        "justificativa": justificativa,
        "justificativa_url": reverse("oficios:wizard_justificativa", args=[oficio.pk]),
        "justificativa_visualizar_url": reverse("oficios:justificativa_pdf_inline", args=[oficio.pk]),
        "justificativa_pdf_url": reverse("oficios:baixar_justificativa_documento", args=[oficio.pk, "pdf"]),
        "justificativa_docx_url": reverse("oficios:baixar_justificativa_documento", args=[oficio.pk, "docx"]),
        "documentos_url": reverse("oficios:wizard_documentos", args=[oficio.pk]),
        "visualizar_url": reverse("oficios:oficio_pdf_inline", args=[oficio.pk]),
        "pdf_url": reverse("oficios:baixar_documento", args=[oficio.pk, "pdf"]),
        "docx_url": reverse("oficios:baixar_documento", args=[oficio.pk, "docx"]),
        "editar_url": editar_url,
        "excluir_url": excluir_url,
    }


def _excluir_url_oficio(pk, next_url=None):
    url = reverse("oficios:excluir", args=[pk])
    if next_url:
        url = f"{url}?{urlencode({'next': next_url})}"
    return url


def _motorista_label_oficio(oficio):
    if oficio.motorista_id:
        return oficio.motorista.nome
    if oficio.motorista_modo == Oficio.MOTORISTA_MODO_MANUAL and (oficio.motorista_manual_nome or "").strip():
        return oficio.motorista_manual_nome.strip()
    return "—"


def _viatura_placa_curta_oficio(oficio):
    if oficio.viatura_id:
        return oficio.viatura.placa_formatada
    if (oficio.transporte_placa_manual or "").strip():
        return format_placa(oficio.transporte_placa_manual)
    return "—"


def _iniciais_nome_servidor(nome: str) -> str:
    nome = (nome or "").strip()
    if not nome:
        return "?"
    parts = nome.split()
    if len(parts) >= 2:
        a, b = parts[0][0], parts[-1][0]
        return f"{a}{b}".upper()
    return nome[:2].upper()


def _montar_viajantes_cards_documentos(oficio):
    """Mini-fichas dos servidores vinculados (cadastro real; sem campos inventados)."""
    motorista_pk = oficio.motorista_id
    termos_pks = set(oficio.servidores_termo_autorizacao.values_list("pk", flat=True))
    cards = []
    qs = oficio.servidores.select_related("cargo", "unidade").order_by("nome")
    for servidor in qs:
        cargo_nome = servidor.cargo.nome if servidor.cargo_id else ""
        unidade_label = str(servidor.unidade) if servidor.unidade_id else ""
        cpf_m = ""
        if (servidor.cpf or "").strip():
            cpf_m = servidor.cpf_formatado
        rg_m = ""
        if servidor.sem_rg or (servidor.rg or "").strip():
            rg_m = servidor.rg_formatado
        tel_m = ""
        if (servidor.telefone or "").strip():
            tel_m = servidor.telefone_formatado
        cards.append(
            {
                "nome": servidor.nome,
                "iniciais": _iniciais_nome_servidor(servidor.nome),
                "cargo": cargo_nome,
                "funcao": "",
                "matricula": "",
                "rg": rg_m,
                "cpf": cpf_m,
                "unidade": unidade_label,
                "telefone": tel_m,
                "email": "",
                "is_motorista": bool(motorista_pk and servidor.pk == motorista_pk),
                "has_termo": servidor.pk in termos_pks,
            }
        )
    return cards


def _montar_transporte_resumo_documentos(oficio):
    """Strings formatadas para o cartão Transporte na etapa documentos (sem lógica no template)."""
    motorista = _motorista_label_oficio(oficio)
    motorista_no_oficio = bool(
        oficio.motorista_id and oficio.servidores.filter(pk=oficio.motorista_id).exists(),
    )
    motorista_externo = bool(
        motorista != "â€”"
        and (
            oficio.motorista_modo == Oficio.MOTORISTA_MODO_MANUAL
            or (oficio.motorista_id and not motorista_no_oficio)
        )
    )
    porte = "Sim" if oficio.porte_transporte_armas else "Não"
    if oficio.viatura_id:
        v = oficio.viatura
        placa = v.placa_formatada
        modelo = (v.modelo or "").strip() or "—"
        tipo = v.get_tipo_display() if (v.tipo or "").strip() else "—"
        combustivel = str(v.combustivel) if v.combustivel_id else "—"
        unidade = str(v.unidade) if v.unidade_id else (str(oficio.solicitante) if oficio.solicitante_id else "—")
    else:
        placa = _viatura_placa_curta_oficio(oficio)
        modelo = (oficio.transporte_modelo_manual or "").strip() or "—"
        tm = (oficio.transporte_tipo_manual or "").strip()
        tipo = oficio.get_transporte_tipo_manual_display() if tm else "—"
        combustivel = (
            str(oficio.transporte_combustivel_manual) if oficio.transporte_combustivel_manual_id else "—"
        )
        unidade = str(oficio.solicitante) if oficio.solicitante_id else "—"

    return {
        "viatura": placa,
        "placa": placa,
        "modelo": modelo,
        "tipo": tipo,
        "tipo_viatura": tipo,
        "combustivel": combustivel,
        "porte_armas": porte,
        "unidade": unidade,
        "motorista": motorista,
        "mostrar_motorista_externo": motorista_externo,
    }


def _montar_justificativa_resumo_documentos(j_et, j_obj, texto_j):
    """Resumo editorial da justificativa para a etapa documentos (textos fixos aqui, não no template)."""
    modelo_nome = "—"
    if j_obj and j_obj.modelo_id:
        modelo = getattr(j_obj, "modelo", None)
        if modelo is not None:
            modelo_nome = modelo.nome

    if j_et.get("obrigatoria"):
        if texto_j:
            chip_label = "Obrigatória preenchida"
            chip_variant = "success"
        else:
            chip_label = "Obrigatória pendente"
            chip_variant = "warning"
    else:
        chip_label = "Não exigida"
        chip_variant = "muted"

    ev_rule = j_et.get("regra") or {}
    dias_ant = j_et.get("dias_antecedencia")
    if dias_ant is None:
        dias_ant = ev_rule.get("dias_antecedencia")

    antecedencia_valor = "—"
    if dias_ant is not None:
        antecedencia_valor = f"{dias_ant} dias"

    st = j_et.get("status") or ""
    if st == "not_started":
        antecedencia_helper = "Informe a data de saída no roteiro para calcular a antecedência."
    elif not j_et.get("obrigatoria"):
        antecedencia_helper = "Não aplicável"
    elif dias_ant is None:
        antecedencia_helper = "—"
    elif dias_ant < 0:
        antecedencia_helper = "Saída anterior ao prazo mínimo"
    else:
        antecedencia_helper = "Dentro do prazo mínimo"

    if not j_et.get("obrigatoria"):
        texto_registrado = (
            texto_j if texto_j else "Justificativa não exigida pela regra de prazo."
        )
    elif not texto_j:
        texto_registrado = "Texto ainda não informado."
    else:
        texto_registrado = texto_j

    return {
        "chip_label": chip_label,
        "chip_variant": chip_variant,
        "antecedencia_valor": antecedencia_valor,
        "antecedencia_label": antecedencia_valor,
        "antecedencia_helper": antecedencia_helper,
        "modelo_nome": modelo_nome,
        "texto_registrado": texto_registrado,
    }


def apresentar_pagina_detalhe_oficio(oficio):
    viatura_label = _viatura_placa_curta_oficio(oficio)
    motorista_label = _motorista_label_oficio(oficio)
    return {
        "status": oficio.get_status_display(),
        "status_class": _status_variant(oficio.status),
        "numero_formatado": oficio.numero_formatado,
        "protocolo": format_protocolo(oficio.protocolo) or "—",
        "motivo": oficio.motivo or "—",
        "data_criacao": oficio.data_criacao.strftime("%d/%m/%Y"),
        "servidores": [servidor.nome for servidor in oficio.servidores.all()],
        "viatura": viatura_label,
        "motorista": motorista_label,
        "custeio": oficio.get_custeio_display(),
        "custeio_observacao": oficio.custeio_observacao or "—",
    }


def apresentar_opcoes_documentais_oficio(oficio):
    _ = oficio
    return [
        {"label": "DOCX (em breve)", "enabled": False},
        {"label": "PDF (em breve)", "enabled": False},
    ]


def apresentar_acoes_oficio(
    *,
    editar_url: str,
    excluir_url: str,
    visualizar_documento_url: str | None = None,
    visualizar_documento_nova_aba: bool = False,
    detalhe_url: str | None = None,
):
    """`detalhe_url` é aceito mas ignorado (compatibilidade com chamadas antigas)."""
    actions = []
    if visualizar_documento_url:
        actions.append(
            build_action(
                "Visualizar documento",
                visualizar_documento_url,
                link_target="_blank" if visualizar_documento_nova_aba else None,
                link_rel="noopener noreferrer" if visualizar_documento_nova_aba else None,
            )
        )
    actions.extend(
        [
            build_edit_action(editar_url),
            build_delete_action(excluir_url),
        ],
    )
    return [a for a in actions if a]


def apresentar_oficio_wizard_header(etapa_atual, oficio=None):
    titles = {
        "dados_viajantes": "Dados e viajantes",
        "roteiro": "Roteiro e diárias",
        "justificativa": "Justificativa",
        "documentos": "Documentos",
        "resumo": "Documentos",
    }
    step_numbers = {
        "dados_viajantes": 1,
        "roteiro": 2,
        "justificativa": 3,
        "documentos": 4,
        "resumo": 4,
    }
    subtitle = titles.get(etapa_atual, "Dados e viajantes")
    step_number = step_numbers.get(etapa_atual, 1)
    ctx = {
        "title": "Cadastro de ofício",
        "subtitle": subtitle,
        "description": f"Etapa {step_number} de 4 — {subtitle}",
    }
    if oficio is not None:
        ctx["status_label"] = oficio.get_status_display()
        if oficio.status == Oficio.STATUS_RASCUNHO:
            ctx["status_variant"] = "draft"
        elif oficio.status == Oficio.STATUS_ARQUIVADO:
            ctx["status_variant"] = "pending"
        else:
            ctx["status_variant"] = "active"
    return ctx


def _map_justificativa_etapa_para_completion(etapa: dict) -> str:
    st = etapa.get("status") or ""
    if st == "not_required":
        return "complete"
    if st == "not_started":
        return "not_started"
    if st == "incomplete":
        return "incomplete"
    if st == "complete":
        return "complete"
    return "not_started"


def apresentar_status_etapa_oficio(status):
    labels = {
        "not_started": "Não iniciada",
        "current": "Atual",
        "incomplete": "Incompleta",
        "complete": "Concluída",
        "locked": "Bloqueada",
    }
    return {
        "status": status,
        "label": labels.get(status, "Não iniciada"),
    }


def _oficio_step_state_class(step: dict) -> str:
    state = step.get("state") or step.get("completion_state") or "not_started"
    if state == "current":
        return "is-current"
    if state == "complete":
        return "is-complete"
    if state == "locked":
        return "is-disabled"
    if state in ("incomplete",):
        return "is-missing"
    if state in ("not_started", "not_required"):
        return "is-pending"
    return "is-pending"


def _oficio_step_marker(step: dict) -> tuple[str, bool]:
    state = step.get("state") or step.get("completion_state") or "not_started"
    if state == "complete":
        return "✓", True
    if state == "locked":
        return str(step.get("number") or ""), True
    return str(step.get("number") or ""), False


def apresentar_oficio_wizard_page_steps(steps):
    """Adapta steps do wizard de ofício para o componente global page_stepper."""
    page_steps = []
    for step in steps or []:
        state_class = _oficio_step_state_class(step)
        marker, marker_hidden = _oficio_step_marker(step)
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


def apresentar_oficio_wizard_steps(
    oficio=None,
    etapa_atual="dados_viajantes",
    dados_viajantes_status=None,
    transporte_status=None,
    roteiro_status=None,
    justificativa_status=None,
    documentos_status=None,
):
    dados_viajantes_status = dados_viajantes_status or "not_started"
    transporte_status = transporte_status or "not_started"
    roteiro_status = roteiro_status or "not_started"
    if oficio is not None and justificativa_status is None:
        from justificativas.services import avaliar_etapa_justificativa_oficio

        justificativa_status = _map_justificativa_etapa_para_completion(
            avaliar_etapa_justificativa_oficio(oficio)
        )
    else:
        justificativa_status = justificativa_status or "not_started"
    documentos_status = documentos_status or "not_started"
    steps = [
        {"key": "dados_viajantes", "number": 1, "title": "Dados e viajantes"},
        {"key": "roteiro", "number": 2, "title": "Roteiro e diárias"},
        {"key": "justificativa", "number": 3, "title": "Justificativa"},
        {"key": "documentos", "number": 4, "title": "Documentos"},
    ]
    for step in steps:
        key = step["key"]
        if key == "dados_viajantes":
            step["url"] = reverse("oficios:dados_viajantes", args=[oficio.pk]) if oficio else ""
            step["state"] = "current" if etapa_atual == key else dados_viajantes_status
            step["completion_state"] = dados_viajantes_status
        elif key == "roteiro":
            step["url"] = reverse("oficios:wizard_roteiro", args=[oficio.pk]) if oficio else ""
            step["state"] = "current" if etapa_atual == key else roteiro_status
            step["completion_state"] = roteiro_status
        elif key == "justificativa":
            step["url"] = reverse("oficios:wizard_justificativa", args=[oficio.pk]) if oficio else ""
            step["state"] = "current" if etapa_atual == key else justificativa_status
            step["completion_state"] = justificativa_status
        elif key == "documentos":
            step["url"] = reverse("oficios:wizard_documentos", args=[oficio.pk]) if oficio else ""
            step["state"] = "current" if etapa_atual == key else documentos_status
            step["completion_state"] = documentos_status
        else:
            step["url"] = ""
            step["state"] = "locked"
            step["completion_state"] = "locked"
        status_data = apresentar_status_etapa_oficio(step["completion_state"])
        step["state_label"] = status_data["label"]
    return steps


def apresentar_oficio_wizard_summary(oficio):
    if oficio is None:
        raise ValueError("Cadastro de oficio exige um rascunho persistido.")

    return {
        "numero_label": oficio.numero_formatado,
        "data_criacao_label": oficio.data_criacao.strftime("%d/%m/%Y"),
        "status_label": oficio.get_status_display(),
        "status_state": str(oficio.status or "").lower(),
    }


def apresentar_modelo_motivo_card(modelo):
    texto = (modelo.texto or "").strip()
    if len(texto) > 140:
        texto = f"{texto[:140]}..."
    return {
        "id": modelo.pk,
        "nome": modelo.nome,
        "is_padrao": modelo.is_padrao,
        "texto_preview": texto or "—",
        "editar_url": reverse("oficios:modelo_motivo_editar", args=[modelo.pk]),
        "excluir_url": reverse("oficios:modelo_motivo_excluir", args=[modelo.pk]),
    }


def apresentar_linha_lista_simples_modelo_motivo(modelo, edit_url="#", delete_url="#", delete_modal=False):
    badges = []
    if modelo.is_padrao:
        badges.append(build_badge("Padrão", "default"))
    texto = (modelo.texto or "").strip()
    if len(texto) > 90:
        texto = f"{texto[:90]}..."
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
        "set_default_url": (
            reverse("oficios:modelo_motivo_definir_padrao", args=[modelo.pk])
            if not modelo.is_padrao
            else ""
        ),
    }


def apresentar_oficio_wizard_documentos_context(oficio):
    """Dados exibidos na etapa 5 (documentos / resumo final)."""
    from django.urls import reverse
    from django.utils import timezone

    from justificativas.selectors import get_or_none_justificativa_by_oficio
    from justificativas.services import avaliar_etapa_justificativa_oficio
    from justificativas.services import get_primeira_saida_oficio

    detalhe = apresentar_pagina_detalhe_oficio(oficio)
    transporte = _montar_transporte_resumo_documentos(oficio)
    viajantes_cards = _montar_viajantes_cards_documentos(oficio)
    roteiro = oficio.roteiro
    diarias_oficio = oficio.diarias_para_servidores()

    def cidade_uf_label(cidade, estado):
        cidade_label = str(cidade).upper() if cidade else ""
        if "/" in cidade_label:
            return cidade_label
        estado_label = getattr(estado, "sigla", "") or str(estado or "")
        return f"{cidade_label}/{estado_label}".upper() if estado_label else cidade_label

    destinos = []
    destinos_rota_labels = []
    if roteiro:
        destinos_qs = list(roteiro.destinos.select_related("cidade", "estado").order_by("ordem"))
        destinos = [f"{d.cidade} ({d.estado.sigla})" for d in destinos_qs]
        destinos_rota_labels = [cidade_uf_label(d.cidade, d.estado) for d in destinos_qs]

    primeira = get_primeira_saida_oficio(oficio)
    primeira_label = "—"
    if primeira:
        primeira_label = primeira.astimezone(timezone.get_current_timezone()).strftime("%d/%m/%Y %H:%M")

    retorno_label = "—"
    if roteiro and roteiro.retorno_saida_dt:
        dt = roteiro.retorno_saida_dt
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        retorno_label = dt.astimezone(timezone.get_current_timezone()).strftime("%d/%m/%Y %H:%M")

    dist_txt = "—"
    if roteiro:
        dist = roteiro.rota_distancia_manual_km or roteiro.rota_distancia_calculada_km
        if dist is not None:
            dist_txt = f"{dist} km"

    tempo_txt = "—"
    if roteiro:
        mins = roteiro.rota_duracao_manual_min or roteiro.rota_duracao_calculada_min
        if mins:
            tempo_txt = f"{mins} min"

    j_et = avaliar_etapa_justificativa_oficio(oficio)
    j_obj = get_or_none_justificativa_by_oficio(oficio)
    texto_j = (j_obj.texto or "").strip() if j_obj else ""

    sede = "—"
    sede_rota_label = "—"
    if roteiro:
        if roteiro.origem_cidade_id:
            sede = str(roteiro.origem_cidade)
            sede_rota_label = cidade_uf_label(roteiro.origem_cidade, roteiro.origem_estado)
        elif roteiro.origem_estado_id:
            sede = str(roteiro.origem_estado)
            sede_rota_label = str(roteiro.origem_estado).upper()

    destino_principal = destinos[0] if destinos else "—"

    roteiro_card = None
    if roteiro:
        from roteiros.presenters import apresentar_roteiro_card

        roteiro_card = apresentar_roteiro_card(roteiro, todos_trechos=True)
        roteiro_card.pop("actions", None)
        roteiro_card["subtitle"] = "Roteiro utilizado para geração dos documentos"
        roteiro_card["title"] = " > ".join([sede_rota_label, *destinos_rota_labels])
        if diarias_oficio:
            valor_moeda = _format_brl_diarias(diarias_oficio["valor_decimal"])
            valor_extenso = (diarias_oficio["valor_extenso"] or "").strip()
            roteiro_card["valor_diarias_display"] = valor_moeda
            roteiro_card["diaria_moeda"] = valor_moeda
            roteiro_card["valor_diarias_extenso"] = valor_extenso
            roteiro_card["diaria_extenso"] = valor_extenso
            roteiro_card["diaria_vazio"] = False

    justificativa_resumo = _montar_justificativa_resumo_documentos(j_et, j_obj, texto_j)

    from oficios.document_generation import get_document_generation_status
    from oficios.services import validar_oficio_para_documento

    generation_status = get_document_generation_status(oficio)

    pendencias_doc = list(validar_oficio_para_documento(oficio).get("pendencias") or [])
    doc_ok = not pendencias_doc
    pdf_ok = bool(generation_status.get("pdf_available"))
    disponivel = doc_ok and pdf_ok
    if not doc_ok:
        doc_msg = "Complete o ofício para gerar e consultar os documentos."
    elif not pdf_ok:
        doc_msg = generation_status.get("pdf_message") or "PDF indisponível."
    else:
        doc_msg = ""

    from termos.services import termo_oficio_assinado_info

    termos_items = []
    servidores_termo = oficio.servidores_termo_autorizacao.select_related("cargo", "unidade").order_by("nome")
    for servidor in servidores_termo:
        assinado_info = termo_oficio_assinado_info(oficio, servidor)
        termos_items.append(
            {
                "titulo": f"Termo de Autorização — {servidor.nome}",
                "servidor_nome": servidor.nome,
                "servidor_id": servidor.pk,
                "servidor_pk": servidor.pk,
                "inline_url": reverse("termos:termo_servidor_pdf_inline", args=[oficio.pk, servidor.pk]),
                **assinado_info,
                "download_pdf_url": reverse(
                    "termos:baixar_termo_servidor",
                    args=[oficio.pk, servidor.pk, "pdf"],
                ),
                "download_docx_url": reverse(
                    "termos:baixar_termo_servidor",
                    args=[oficio.pk, servidor.pk, "docx"],
                ),
                "disponivel": disponivel,
            },
        )

    documentos_inline = {
        "oficio": {
            "titulo": "Documento original (Ofício)",
            "url": reverse("oficios:oficio_pdf_inline", args=[oficio.pk]),
            "download_pdf_url": reverse("oficios:baixar_documento", args=[oficio.pk, "pdf"]),
            "download_docx_url": reverse("oficios:baixar_documento", args=[oficio.pk, "docx"]),
            "disponivel": disponivel,
            "mensagem": doc_msg,
        },
        "justificativa": {
            "titulo": "Justificativa",
            "url": reverse("oficios:justificativa_pdf_inline", args=[oficio.pk]),
            "download_pdf_url": reverse("oficios:baixar_justificativa_documento", args=[oficio.pk, "pdf"]),
            "download_docx_url": reverse("oficios:baixar_justificativa_documento", args=[oficio.pk, "docx"]),
            "disponivel": disponivel,
            "mensagem": doc_msg,
        },
        "termos": termos_items,
        "termos_vazio": not termos_items,
        "termos_empty_message": "Nenhum servidor selecionado para Termo de Autorização.",
        "termos_download_todos_pdf_url": (
            reverse("termos:baixar_termos_todos_pdf", args=[oficio.pk]) if termos_items else None
        ),
        "termos_download_todos_docx_url": (
            reverse("termos:baixar_termo_lote_zip", args=[oficio.pk, "docx"]) if termos_items else None
        ),
        "mensagem_indisponivel": doc_msg,
    }

    return {
        "detalhe": detalhe,
        "transporte": transporte,
        "viajantes_cards": viajantes_cards,
        "destinos": destinos,
        "destino_principal_label": destino_principal,
        "primeira_saida_label": primeira_label,
        "retorno_label": retorno_label,
        "distancia_label": dist_txt,
        "tempo_rota_label": tempo_txt,
        "sede_label": sede,
        "roteiro": roteiro,
        "roteiro_card": roteiro_card,
        "justificativa_etapa": j_et,
        "justificativa_texto": texto_j,
        "justificativa_resumo": justificativa_resumo,
        "quantidade_diarias": (diarias_oficio["quantidade"] if diarias_oficio else "") or "—",
        "valor_diarias": diarias_oficio["valor_decimal"] if diarias_oficio else None,
        "valor_diarias_display": _format_brl_diarias(diarias_oficio["valor_decimal"] if diarias_oficio else None),
        "valor_diarias_extenso": (diarias_oficio["valor_extenso"] if diarias_oficio else "") or "—",
        "generation_status": generation_status,
        "documentos_inline": documentos_inline,
    }

