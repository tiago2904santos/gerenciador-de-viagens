from django.urls import reverse

from core.utils.masks import format_protocolo

# Reaproveita a formatação já consolidada na lista de ofícios para manter
# o visual do card idêntico (trechos, valor, datas e badge temporal).
from oficios.presenters import (
    _format_brl_diarias,
    _format_dt_trecho,
    _label_cidade_uf_trecho,
    _temporal_badge_oficio,
)

from .forms import CAMPOS_COM_MODELO
from .forms import CAMPOS_CUSTEIO_COM_OUTRO


def _destino_display(oficio) -> str:
    try:
        destinos = list(oficio.roteiro.destinos.select_related("cidade", "estado").order_by("ordem"))
        if not destinos:
            return ""
        parts = [f"{d.cidade} ({d.estado.sigla})" for d in destinos[:3]]
        result = ", ".join(parts)
        if len(destinos) > 3:
            result += f" +{len(destinos) - 3}"
        return result
    except Exception:
        return ""


def _periodo_display(oficio) -> str:
    try:
        from django.utils import timezone as tz_module
        roteiro = oficio.roteiro
        saida_dt = roteiro.saida_dt
        if not saida_dt:
            return ""
        current_tz = tz_module.get_current_timezone()
        saida = saida_dt.astimezone(current_tz).date() if tz_module.is_aware(saida_dt) else saida_dt.date()
        chegada_dt = getattr(roteiro, "retorno_chegada_dt", None) or getattr(roteiro, "chegada_dt", None)
        if chegada_dt:
            chegada = chegada_dt.astimezone(current_tz).date() if tz_module.is_aware(chegada_dt) else chegada_dt.date()
            if saida == chegada:
                return saida.strftime("%d/%m/%Y")
            return f"{saida.strftime('%d/%m/%Y')} a {chegada.strftime('%d/%m/%Y')}"
        return saida.strftime("%d/%m/%Y")
    except Exception:
        return ""


def _build_campos_modelo(form) -> list:
    """Para cada campo de texto longo: select de modelos + textarea + URL de gerência."""
    base_url = reverse("prestacoes_contas:modelos_index")
    campos = []
    for campo, label in CAMPOS_COM_MODELO:
        select = form[f"modelo_{campo}"]
        campos.append(
            {
                "campo": campo,
                "label": label,
                "select": select,
                "textarea": form[campo],
                "manage_url": f"{base_url}#grupo-{campo}",
                "tem_modelos": select.field.queryset.exists(),
            }
        )
    return campos


def _build_campos_custeio(form) -> list:
    campos = [
        {
            "campo": "diaria",
            "label": "Diária",
            "field": form["diaria"],
            "other": None,
            "uses_other": False,
        }
    ]
    for campo, label in CAMPOS_CUSTEIO_COM_OUTRO:
        campos.append(
            {
                "campo": campo,
                "label": label,
                "field": form[campo],
                "other": form[f"{campo}_outro"],
                "uses_other": True,
            }
        )
    return campos


def _build_identificacao(pc) -> dict:
    oficio = pc.oficio
    servidor = pc.servidor
    return {
        "numero": oficio.numero_formatado,
        "protocolo": format_protocolo(oficio.protocolo) or "—",
        "data_oficio": oficio.data_criacao.strftime("%d/%m/%Y") if oficio.data_criacao else "—",
        "custeio": oficio.get_custeio_display() if oficio.custeio else "—",
        "destino": _destino_display(oficio) or "—",
        "periodo": _periodo_display(oficio) or "—",
        "nome_servidor": servidor.nome,
        "rg_servidor": servidor.rg_formatado,
        "cargo": str(servidor.cargo) if servidor.cargo_id else "—",
        "unidade": str(servidor.unidade) if servidor.unidade_id else "",
        "is_motorista": oficio.motorista_id == servidor.id,
    }


def _build_prestacao_steps(prestacao, atual: str) -> list:
    """Etapas do wizard da prestação de contas."""
    documentos_url = reverse("prestacoes_contas:documentos", args=[prestacao.pk])
    rt_url = reverse("prestacoes_contas:rt_criar", args=[prestacao.pk])
    diario_url = reverse("prestacoes_contas:diario_criar", args=[prestacao.pk])
    consolidado_url = reverse("prestacoes_contas:consolidado", args=[prestacao.pk])
    etapas = [
        ("documentos", "Etapa 1", "Documentos", documentos_url),
        ("rt", "Etapa 2", "Relatório Técnico", rt_url),
        ("diario", "Etapa 3", "Diário de Bordo", diario_url),
        ("consolidado", "Etapa 4", "PDF Final", consolidado_url),
    ]
    steps = []
    atingiu_atual = False
    for chave, step_label, titulo, url in etapas:
        if chave == atual:
            state_class = "is-current"
            aria_current = "step"
            atingiu_atual = True
            status = "Em edição"
        elif atingiu_atual:
            state_class = ""
            aria_current = ""
            status = "A seguir"
        else:
            state_class = "is-complete"
            aria_current = ""
            status = "Concluído"
        steps.append(
            {
                "marker": "✓" if state_class == "is-complete" else str(len(steps) + 1),
                "step_label": step_label,
                "title": titulo,
                "status": status,
                "state_class": state_class,
                "aria_current": aria_current,
                "url": url,
            }
        )
    return steps


def _trecho_display(linha) -> dict:
    """Dados somente-leitura de um trecho (origem/destino/datas) para o card do diário."""
    from django.utils import timezone as tz

    trecho = linha.trecho

    def cidade(c, e):
        if c is not None:
            return str(getattr(c, "nome", c)).upper()
        if e is not None:
            return str(getattr(e, "sigla", e)).upper()
        return "—"

    def fmt(dt):
        if not dt:
            return {"data": "", "hora": ""}
        local = tz.localtime(dt) if tz.is_aware(dt) else dt
        return {"data": local.strftime("%d/%m/%Y"), "hora": local.strftime("%H:%M")}

    origem = cidade(getattr(trecho, "origem_cidade", None), getattr(trecho, "origem_estado", None)) if trecho else "—"
    destino = cidade(getattr(trecho, "destino_cidade", None), getattr(trecho, "destino_estado", None)) if trecho else "—"
    saida = fmt(getattr(trecho, "saida_dt", None)) if trecho else {"data": "", "hora": ""}
    chegada = fmt(getattr(trecho, "chegada_dt", None)) if trecho else {"data": "", "hora": ""}
    return {
        "ordem": linha.ordem + 1,
        "origem": origem,
        "destino": destino,
        "rota": f"{origem} → {destino}",
        "saida": saida,
        "chegada": chegada,
    }


def apresentar_prestacao_card(prestacao, solicitacao_form=None):
    """Monta o contexto de um card de prestação no layout da lista de ofícios.

    Cada prestação é de um único servidor; por isso o card mostra apenas o
    servidor da prestação, mas reaproveita os dados de roteiro/diárias do
    ofício associado.
    """
    oficio = prestacao.oficio
    servidor = prestacao.servidor

    # ── Servidor (único viajante do card) ──
    cargo_nome = servidor.cargo.nome if servidor.cargo_id and servidor.cargo else ""
    unidade_nome = str(servidor.unidade) if servidor.unidade_id else ""
    is_motorista = bool(oficio.motorista_id and servidor.pk == oficio.motorista_id)

    # ── Identificação ──
    data_criacao_display = ""
    if oficio.data_criacao:
        try:
            data_criacao_display = oficio.data_criacao.strftime("%d/%m/%Y")
        except Exception:
            pass

    temporal_label, temporal_tone = _temporal_badge_oficio(oficio)

    # ── Roteiro: placa/modelo, trechos e diárias (espelha o card de ofício) ──
    veiculo_placa = ""
    veiculo_modelo = ""
    if oficio.viatura_id:
        v = oficio.viatura
        veiculo_placa = v.placa_formatada
        veiculo_modelo = (v.modelo or "").strip()
    elif (oficio.transporte_placa_manual or "").strip():
        from core.utils.masks import format_placa

        veiculo_placa = format_placa(oficio.transporte_placa_manual)
        veiculo_modelo = (oficio.transporte_modelo_manual or "").strip()

    trechos_display = []
    valor_diarias_display = ""
    valor_diarias_extenso = ""
    if oficio.roteiro_id:
        roteiro = oficio.roteiro
        for t in roteiro.trechos.all():
            orig = _label_cidade_uf_trecho(t.origem_cidade, t.origem_estado)
            dest = _label_cidade_uf_trecho(t.destino_cidade, t.destino_estado)
            trechos_display.append({
                "rota": f"{orig} → {dest}",
                "saida": _format_dt_trecho(t.saida_dt),
                "chegada": _format_dt_trecho(t.chegada_dt),
            })
        if roteiro.valor_diarias:
            valor_diarias_display = _format_brl_diarias(roteiro.valor_diarias)
            valor_diarias_extenso = (roteiro.valor_diarias_extenso or "").strip()

    # ── Relatório técnico (download condicional) ──
    rt = None
    try:
        rt = prestacao.relatorio_tecnico
    except Exception:
        rt = None
    rt_download_url = (
        reverse("prestacoes_contas:rt_download", args=[rt.pk]) if rt else ""
    )

    return {
        "prestacao_pk": prestacao.pk,
        # identificação
        "numero_display": oficio.numero_formatado,
        "protocolo_display": format_protocolo(oficio.protocolo) or "",
        "data_criacao_display": data_criacao_display,
        "temporal_label": temporal_label,
        "temporal_tone": temporal_tone,
        # status da prestação
        "status_label": prestacao.status_display,
        "status_tone": prestacao.status_variant,
        "status_value": prestacao.status,
        # servidor único
        "servidor": {
            "name": servidor.nome,
            "cargo": cargo_nome,
            "unidade": unidade_nome,
            "is_motorista": is_motorista,
        },
        # roteiro / transporte
        "veiculo_placa": veiculo_placa,
        "veiculo_modelo": veiculo_modelo,
        "trechos": trechos_display,
        "valor_diarias_display": valor_diarias_display,
        "valor_diarias_extenso": valor_diarias_extenso,
        # solicitação
        "numero_solicitacao": prestacao.numero_solicitacao,
        "solicitacao_form": solicitacao_form,
        # ações / urls
        "documentos_url": reverse("prestacoes_contas:documentos", args=[prestacao.pk]),
        "rt_url": reverse("prestacoes_contas:rt_criar", args=[prestacao.pk]),
        "tem_rt": rt is not None,
        "rt_download_url": rt_download_url,
        "diario_url": reverse("prestacoes_contas:diario_criar", args=[prestacao.pk]),
        "consolidado_url": reverse("prestacoes_contas:consolidado", args=[prestacao.pk]),
        "autosave_url": reverse("prestacoes_contas:prestacao_autosave", args=[prestacao.pk]),
        # filtro / busca
        "search_text": f"{oficio.numero_formatado} {format_protocolo(oficio.protocolo) or ''} {servidor.nome}",
    }
