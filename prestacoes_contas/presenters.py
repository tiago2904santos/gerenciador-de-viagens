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
