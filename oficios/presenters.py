from core.presenters.actions import build_action
from core.presenters.actions import build_delete_action
from core.presenters.actions import build_edit_action
from core.presenters.badges import build_badge
from core.presenters.meta import build_meta
from core.utils.masks import format_placa
from core.utils.masks import format_protocolo
from decimal import Decimal

from django.urls import reverse

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


def apresentar_oficio_card(oficio, *, assinatura_pdf: str | None = None):
    card = {
        "number_label": "N° do Ofício",
        "number": oficio.numero_formatado,
        "status": oficio.get_status_display(),
        "status_class": _status_variant(oficio.status),
        "status_chip_label": oficio.get_status_display(),
        "status_chip_class": _status_variant(oficio.status),
        "status_variant": oficio.status.lower() if oficio.status else "outro",
        "faixa_lateral_class": _oficio_faixa_lateral_class(oficio.status),
        "title": f"Ofício {oficio.numero_formatado}",
        "subtitle": oficio.motivo[:120] if oficio.motivo else "Sem motivo",
        "side_title": "Ofício",
        "side_items": [
            build_meta("Status", oficio.get_status_display()),
        ],
        "meta": [
            build_meta("Protocolo", format_protocolo(oficio.protocolo) or "—"),
            build_meta("Data criação", oficio.data_criacao.strftime("%d/%m/%Y")),
            build_meta("Custeio", oficio.get_custeio_display()),
            build_meta("Viajantes", str(oficio.servidores.count())),
        ],
    }
    if oficio.status == Oficio.STATUS_FINALIZADO and assinatura_pdf in ("assinado", "aguardando"):
        suffix = "Assinado" if assinatura_pdf == "assinado" else "Aguardando assinatura"
        card["status"] = f"Finalizado — {suffix}"
        card["status_chip_label"] = card["status"]
        card["side_items"].append(build_meta("Assinatura", suffix))
    return card


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
        "assinaturas": "Central de assinaturas",
        "resumo": "Documentos",
    }
    step_numbers = {
        "dados_viajantes": 1,
        "roteiro": 2,
        "justificativa": 3,
        "documentos": 4,
        "assinaturas": 5,
        "resumo": 4,
    }
    subtitle = titles.get(etapa_atual, "Dados e viajantes")
    step_number = step_numbers.get(etapa_atual, 1)
    ctx = {
        "title": "Cadastro de ofício",
        "subtitle": subtitle,
        "description": f"Etapa {step_number} de 5 — {subtitle}",
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
    assinaturas_status=None,
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
    if assinaturas_status is None:
        assinaturas_status = documentos_status
    steps = [
        {"key": "dados_viajantes", "number": 1, "title": "Dados e viajantes"},
        {"key": "roteiro", "number": 2, "title": "Roteiro e diárias"},
        {"key": "justificativa", "number": 3, "title": "Justificativa"},
        {"key": "documentos", "number": 4, "title": "Documentos"},
        {"key": "assinaturas", "number": 5, "title": "Central de assinaturas"},
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
        elif key == "assinaturas":
            step["url"] = reverse("oficios:wizard_assinaturas", args=[oficio.pk]) if oficio else ""
            step["state"] = "current" if etapa_atual == key else assinaturas_status
            step["completion_state"] = assinaturas_status
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


def apresentar_linha_lista_simples_modelo_motivo(modelo, edit_url="#", delete_url="#"):
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
        "delete_url": delete_url,
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
    destinos = []
    if roteiro:
        destinos = [f"{d.cidade} ({d.estado.sigla})" for d in roteiro.destinos.order_by("ordem")]

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
    if roteiro:
        if roteiro.origem_cidade_id:
            sede = str(roteiro.origem_cidade)
        elif roteiro.origem_estado_id:
            sede = str(roteiro.origem_estado)

    destino_principal = destinos[0] if destinos else "—"

    roteiro_card = None
    if roteiro:
        from roteiros.presenters import apresentar_roteiro_card

        roteiro_card = apresentar_roteiro_card(roteiro)
        roteiro_card.pop("actions", None)
        roteiro_card["subtitle"] = "Roteiro utilizado para geração dos documentos"

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

    termos_items = []
    servidores_termo = oficio.servidores_termo_autorizacao.select_related("cargo", "unidade").order_by("nome")
    for servidor in servidores_termo:
        termos_items.append(
            {
                "titulo": f"Termo de Autorização — {servidor.nome}",
                "servidor_nome": servidor.nome,
                "servidor_id": servidor.pk,
                "servidor_pk": servidor.pk,
                "inline_url": reverse("termos:termo_servidor_pdf_inline", args=[oficio.pk, servidor.pk]),
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
            "disponivel": disponivel,
            "mensagem": doc_msg,
        },
        "justificativa": {
            "titulo": "Justificativa",
            "url": reverse("oficios:justificativa_pdf_inline", args=[oficio.pk]),
            "disponivel": disponivel,
            "mensagem": doc_msg,
        },
        "termos": termos_items,
        "termos_vazio": not termos_items,
        "termos_empty_message": "Nenhum servidor selecionado para Termo de Autorização.",
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
        "quantidade_diarias": (roteiro.quantidade_diarias if roteiro else "") or "—",
        "valor_diarias": roteiro.valor_diarias if roteiro else None,
        "valor_diarias_display": _format_brl_diarias(roteiro.valor_diarias if roteiro else None),
        "valor_diarias_extenso": (roteiro.valor_diarias_extenso if roteiro else "") or "—",
        "generation_status": generation_status,
        "documentos_inline": documentos_inline,
    }

