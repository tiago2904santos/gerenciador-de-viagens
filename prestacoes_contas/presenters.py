from django.urls import reverse

from core.utils.masks import format_protocolo

# Reaproveita a formatação já consolidada na lista de ofícios para manter
# o visual do card idêntico (trechos, valor, datas e badge temporal).
from oficios.presenters import (
    _data_evento_display_oficio,
    _destino_display_oficio,
    _format_brl_diarias,
    _format_dt_trecho,
    _label_cidade_uf_trecho,
    _temporal_badge_oficio,
)

from .forms import PrestacaoSolicitacaoForm
from .models import PrestacaoDocumentoAnexo


def _servidor_row(ps, solicitacao_form=None):
    """Dados de um servidor no card: identificação + solicitação inline + status."""
    servidor = ps.servidor
    cargo_nome = servidor.cargo.nome if servidor.cargo_id and servidor.cargo else ""
    unidade_nome = str(servidor.unidade) if servidor.unidade_id else ""

    # Comprovante de saque (individual): usa os anexos já pré-carregados.
    comprovante_ok = any(
        anexo.tipo == PrestacaoDocumentoAnexo.TIPO_COMPROVANTE
        for anexo in ps.documentos_anexos.all()
    )

    if solicitacao_form is None:
        solicitacao_form = PrestacaoSolicitacaoForm(instance=ps, prefix=f"ps-{ps.pk}")

    return {
        "ps_pk": ps.pk,
        "name": servidor.nome,
        "cargo": cargo_nome,
        "unidade": unidade_nome,
        "is_motorista": ps.is_motorista,
        "numero_solicitacao": ps.numero_solicitacao,
        "solicitacao_form": solicitacao_form,
        "solicitacao_autosave_url": reverse(
            "prestacoes_contas:prestacao_servidor_solicitacao_autosave", args=[ps.pk]
        ),
        "comprovante_ok": comprovante_ok,
        "pacote_url": reverse("prestacoes_contas:consolidado_download", args=[ps.pk]),
        "rt_download_url": reverse("prestacoes_contas:rt_download_servidor", args=[ps.pk]),
    }


def apresentar_prestacao_card(prestacao, solicitacao_forms=None):
    """Monta o contexto de um card de prestação (um por ofício) no layout da lista de ofícios.

    Reúne todos os servidores do ofício: o trabalho compartilhado (roteiro,
    diárias, despacho, texto do RT e diário de bordo) aparece uma vez; o número
    da solicitação e o comprovante de saque são exibidos por servidor.

    ``solicitacao_forms`` é um dict ``{ps_pk: PrestacaoSolicitacaoForm}`` opcional
    (usado para reexibir erros de validação); quando ausente, cada linha cria o
    seu próprio form não-vinculado.
    """
    oficio = prestacao.oficio
    solicitacao_forms = solicitacao_forms or {}

    # ── Servidores da prestação ──
    servidores = [
        _servidor_row(ps, solicitacao_forms.get(ps.pk))
        for ps in prestacao.servidores_prestacao.all()
    ]

    # ── Identificação ──
    data_criacao_display = ""
    if oficio.data_criacao:
        try:
            data_criacao_display = oficio.data_criacao.strftime("%d/%m/%Y")
        except Exception:
            pass

    destino_display = _destino_display_oficio(oficio)
    data_evento_display = _data_evento_display_oficio(oficio)
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

    # ── Relatório técnico compartilhado (download é por servidor) ──
    rt = None
    try:
        rt = prestacao.relatorio_tecnico
    except Exception:
        rt = None

    search_parts = [oficio.numero_formatado, format_protocolo(oficio.protocolo) or ""]
    search_parts += [s["name"] for s in servidores]

    return {
        "prestacao_pk": prestacao.pk,
        # identificação
        "numero_display": oficio.numero_formatado,
        "protocolo_display": format_protocolo(oficio.protocolo) or "",
        "destino_display": destino_display,
        "data_evento_display": data_evento_display,
        "data_criacao_display": data_criacao_display,
        "temporal_label": temporal_label,
        "temporal_tone": temporal_tone,
        # status da prestação
        "status_label": prestacao.status_display,
        "status_tone": prestacao.status_variant,
        "status_value": prestacao.status,
        # servidores (lista)
        "servidores": servidores,
        "servidores_count": len(servidores),
        # roteiro / transporte
        "veiculo_placa": veiculo_placa,
        "veiculo_modelo": veiculo_modelo,
        "trechos": trechos_display,
        "valor_diarias_display": valor_diarias_display,
        "valor_diarias_extenso": valor_diarias_extenso,
        # ações / urls (nível ofício)
        "documentos_url": reverse("prestacoes_contas:documentos", args=[prestacao.pk]),
        "rt_url": reverse("prestacoes_contas:rt_criar", args=[prestacao.pk]),
        "tem_rt": rt is not None,
        "diario_url": reverse("prestacoes_contas:diario_criar", args=[prestacao.pk]),
        "consolidado_url": reverse("prestacoes_contas:consolidado", args=[prestacao.pk]),
        # filtro / busca
        "search_text": " ".join(p for p in search_parts if p),
    }
