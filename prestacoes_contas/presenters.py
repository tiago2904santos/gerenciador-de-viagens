from django.urls import reverse

from cadastros.selectors import get_configuracao_sistema
from core import entity_cards
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


def _whatsapp_phone(servidor):
    """Telefone com DDI 55, só quando tem os 11 dígitos (DDD + celular); senão vazio."""
    telefone = (getattr(servidor, "telefone", "") or "").strip()
    return f"55{telefone}" if len(telefone) == 11 and telefone.isdigit() else ""


def _anexo_assinado_info(anexos, *, tipo, anexar_url, prestacao_pk):
    atual = next(
        (anexo for anexo in reversed(list(anexos)) if anexo.tipo == tipo),
        None,
    )
    if atual is None:
        return {
            "assinado": False,
            "anexar_url": anexar_url,
            "nome_original": "",
            "view_url": "",
            "remover_url": "",
        }
    return {
        "assinado": True,
        "anexar_url": anexar_url,
        "nome_original": atual.nome_original or atual.arquivo.name.rsplit("/", 1)[-1],
        "view_url": atual.arquivo.url,
        "remover_url": reverse(
            "prestacoes_contas:prestacao_documento_excluir",
            args=[prestacao_pk, atual.pk],
        ),
    }


def _servidor_row(ps, solicitacao_form=None, prestacao_anexos=None):
    """Dados de um servidor no card: identificação + solicitação inline + status."""
    servidor = ps.servidor
    cargo_nome = servidor.cargo.nome if servidor.cargo_id and servidor.cargo else ""
    unidade_nome = str(servidor.unidade) if servidor.unidade_id else ""

    # Comprovante de saque (individual): usa os anexos já pré-carregados.
    anexos = list(ps.documentos_anexos.all())
    comprovante_ok = any(
        anexo.tipo == PrestacaoDocumentoAnexo.TIPO_COMPROVANTE
        for anexo in anexos
    )

    if solicitacao_form is None:
        solicitacao_form = PrestacaoSolicitacaoForm(instance=ps, prefix=f"ps-{ps.pk}")

    row = {
        "ps_pk": ps.pk,
        "name": servidor.nome,
        "cargo": cargo_nome,
        "unidade": unidade_nome,
        "is_motorista": ps.is_motorista,
        "numero_solicitacao": ps.numero_solicitacao,
        "data_liberacao_diarias": (
            ps.data_liberacao_diarias.isoformat() if ps.data_liberacao_diarias else ""
        ),
        "prazo_limite_saque": ps.prazo_limite_saque.isoformat() if ps.prazo_limite_saque else "",
        "solicitacao_form": solicitacao_form,
        "solicitacao_autosave_url": reverse(
            "prestacoes_contas:prestacao_servidor_solicitacao_autosave", args=[ps.pk]
        ),
        "comprovante_ok": comprovante_ok,
        "pacote_url": reverse("prestacoes_contas:consolidado_download", args=[ps.pk]),
        "rt_download_url": reverse(
            "prestacoes_contas:rt_download_servidor_formato", args=[ps.pk, "pdf"]
        ),
        # aviso de liberação de diárias (WhatsApp) — partes fixas do texto
        "whatsapp_phone": _whatsapp_phone(servidor),
        "whatsapp_diaria_override": (ps.diaria_valor_override or "").strip(),
    }
    row["rt_assinado"] = _anexo_assinado_info(
        anexos,
        tipo=PrestacaoDocumentoAnexo.TIPO_RT_ASSINADO,
        anexar_url=reverse(
            "prestacoes_contas:prestacao_servidor_assinado_anexar",
            args=[ps.pk, PrestacaoDocumentoAnexo.TIPO_RT_ASSINADO],
        ),
        prestacao_pk=ps.prestacao_id,
    )
    row["comprovante_anexo"] = _anexo_assinado_info(
        anexos,
        tipo=PrestacaoDocumentoAnexo.TIPO_COMPROVANTE,
        anexar_url=reverse(
            "prestacoes_contas:prestacao_servidor_assinado_anexar",
            args=[ps.pk, PrestacaoDocumentoAnexo.TIPO_COMPROVANTE],
        ),
        prestacao_pk=ps.prestacao_id,
    )
    row["diario_assinado"] = _anexo_assinado_info(
        prestacao_anexos or [],
        tipo=PrestacaoDocumentoAnexo.TIPO_DB_ASSINADO,
        anexar_url=reverse(
            "prestacoes_contas:prestacao_servidor_assinado_anexar",
            args=[ps.pk, PrestacaoDocumentoAnexo.TIPO_DB_ASSINADO],
        ),
        prestacao_pk=ps.prestacao_id,
    )
    return row


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
    prestacao_anexos = list(prestacao.documentos_anexos.all())
    servidores = [
        _servidor_row(ps, solicitacao_forms.get(ps.pk), prestacao_anexos)
        for ps in prestacao.servidores_prestacao.all()
    ]
    # O motorista aparece sempre como primeiro nome da lista (ordem estável entre os demais).
    servidores.sort(key=lambda s: not s["is_motorista"])

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

    # ── Aviso de liberação de diárias (WhatsApp): partes comuns a todo servidor ──
    # "Unidade sede" = a unidade configurada em Configurações > "Dados da
    # unidade e Endereço dos documentos" (a mesma usada como ORIGEM no
    # cabeçalho do ofício gerado), não o solicitante do ofício.
    configuracao = get_configuracao_sistema()
    unidade_sede_display = configuracao.unidade.nome if configuracao.unidade_id else ""
    if destino_display and data_evento_display:
        evento_wa_display = f"{destino_display}, de {data_evento_display}"
    else:
        evento_wa_display = destino_display or data_evento_display
    for row in servidores:
        row["whatsapp_oficio"] = oficio.numero_formatado
        row["whatsapp_unidade"] = unidade_sede_display
        row["whatsapp_evento"] = evento_wa_display
        row["whatsapp_diaria"] = row.pop("whatsapp_diaria_override") or valor_diarias_display

    # ── Relatório técnico compartilhado (download é por servidor) ──
    rt = None
    try:
        rt = prestacao.relatorio_tecnico
    except Exception:
        rt = None

    diario = None
    try:
        diario = prestacao.diario_bordo
    except Exception:
        diario = None

    diario_pdf_url = (
        reverse("prestacoes_contas:diario_download_formato", args=[diario.pk, "pdf"])
        if diario is not None
        else ""
    )
    for row in servidores:
        row["diario_pdf_url"] = diario_pdf_url

    despacho_assinado = _anexo_assinado_info(
        prestacao_anexos,
        tipo=PrestacaoDocumentoAnexo.TIPO_DESPACHO,
        anexar_url=reverse(
            "prestacoes_contas:prestacao_despacho_assinado_anexar",
            args=[prestacao.pk],
        ),
        prestacao_pk=prestacao.pk,
    )

    search_parts = [oficio.numero_formatado, format_protocolo(oficio.protocolo) or ""]
    search_parts += [s["name"] for s in servidores]

    protocolo_display = format_protocolo(oficio.protocolo) or ""
    header_value = " · ".join(
        p
        for p in [oficio.numero_formatado, protocolo_display, destino_display, data_evento_display]
        if p
    )
    header_chips = [entity_cards.chip(prestacao.status_variant, prestacao.status_display)]
    if temporal_label:
        header_chips.append(entity_cards.chip(temporal_tone, temporal_label))

    return {
        "prestacao_pk": prestacao.pk,
        "status_variant": prestacao.status or "outro",
        "header": entity_cards.header(
            [entity_cards.header_item("Ofício", header_value, wide=True, wrap=True)],
            header_chips,
        ),
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
        # arquivamento / conclusão
        "arquivada": prestacao.arquivada,
        "finalizada": prestacao.finalizada,
        "arquivar_url": reverse("prestacoes_contas:prestacao_arquivar", args=[prestacao.pk]),
        "finalizar_url": reverse("prestacoes_contas:prestacao_finalizar", args=[prestacao.pk]),
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
        "despacho_assinado": despacho_assinado,
        # filtro / busca
        "search_text": " ".join(p for p in search_parts if p),
    }
