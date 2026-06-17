"""Services internos da Central de Protocolos.

Esta é a **única** camada do app que conversa com a integração eProtocolo
(``integracoes.eprotocolo.services``). As views chamam SOMENTE este módulo —
nunca o client HTTP diretamente.

Responsabilidades:
    * orquestrar criação/vínculo/envio/tramitação/sincronização;
    * traduzir os resultados da integração em registros locais (models);
    * registrar logs técnicos mascarados (sem token/secret/CPF cru);
    * nunca quebrar a experiência por ausência de credenciais (modo mock).
"""

from __future__ import annotations

import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from integracoes.eprotocolo import mappers
from integracoes.eprotocolo import services as epro
from integracoes.eprotocolo import settings as cfg
from integracoes.eprotocolo.client import mascarar_dados
from integracoes.eprotocolo.exceptions import EProtocoloError
from integracoes.eprotocolo.schemas import ResultadoOperacao

from .models import (
    Protocolo,
    ProtocoloAssinatura,
    ProtocoloDocumento,
    ProtocoloLog,
    ProtocoloMovimentacao,
    ProtocoloPendencia,
    ProtocoloTramitacao,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------
def registrar_log(protocolo, acao, *, resultado: ResultadoOperacao | None = None,
                  erro: Exception | None = None, endpoint="", metodo="",
                  request_payload=None) -> ProtocoloLog:
    """Registra um log técnico de integração, sempre com payloads mascarados."""
    sucesso = erro is None and (resultado is None or resultado.sucesso)
    response_payload = {}
    status_code = None
    modo_mock = False
    if resultado is not None:
        response_payload = resultado.dados or {}
        modo_mock = resultado.mock
    if isinstance(erro, EProtocoloError):
        status_code = erro.status_code
        if erro.payload:
            response_payload = erro.payload

    return ProtocoloLog.objects.create(
        protocolo=protocolo if getattr(protocolo, "pk", None) else None,
        acao=acao,
        endpoint=endpoint,
        metodo=metodo,
        status_code=status_code,
        sucesso=sucesso,
        modo_mock=modo_mock,
        erro="" if erro is None else str(erro),
        request_payload=mascarar_dados(request_payload or {}),
        response_payload=mascarar_dados(response_payload or {}),
    )


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------
def gerar_payload_protocolo(protocolo: Protocolo) -> dict:
    """Gera o payload de criação do protocolo.

    Usa o mapper do documento de origem quando há vínculo interno; caso
    contrário monta um payload mínimo a partir dos próprios campos do protocolo.
    """
    if protocolo.origem_object is not None:
        return mappers.mapear_documento(protocolo.origem_object)

    payload = {
        "codOrgao": protocolo.cod_orgao or cfg.get("COD_ORGAO_PADRAO", ""),
        "nomeOrgao": protocolo.nome_orgao or cfg.get("NOME_ORGAO_PADRAO", ""),
        "codLocalOrigem": protocolo.cod_local_origem or cfg.get("COD_LOCAL_ORIGEM_PADRAO", ""),
        "assunto": protocolo.assunto_resumo,
        "descricao": protocolo.descricao_resumo,
        "tipoOrigem": "MANUAL",
    }
    return payload


def _aplicar_dados_criacao(protocolo: Protocolo, resultado: ResultadoOperacao, payload: dict):
    dados = resultado.dados or {}
    numero = dados.get("numero") or ""
    protocolo.numero = numero
    protocolo.situacao_eprotocolo = dados.get("situacao", "") or protocolo.situacao_eprotocolo
    protocolo.cod_orgao = protocolo.cod_orgao or payload.get("codOrgao", "")
    protocolo.nome_orgao = protocolo.nome_orgao or payload.get("nomeOrgao", "")
    protocolo.cod_local_origem = protocolo.cod_local_origem or payload.get("codLocalOrigem", "")
    protocolo.cod_local_atual = dados.get("codLocalAtual", "") or protocolo.cod_local_origem
    protocolo.nome_local_atual = dados.get("nomeLocalAtual", "") or protocolo.nome_local_origem
    if not protocolo.assunto_resumo:
        protocolo.assunto_resumo = (payload.get("assunto") or "")[:255]
    if not protocolo.descricao_resumo:
        protocolo.descricao_resumo = payload.get("descricao") or ""
    protocolo.payload_atual_json = mascarar_dados(dados)
    protocolo.modo_mock = resultado.mock
    protocolo.criado_no_eprotocolo_em = timezone.now()
    protocolo.status_local = Protocolo.STATUS_CRIADO


# ---------------------------------------------------------------------------
# Criação / vínculo
# ---------------------------------------------------------------------------
@transaction.atomic
def criar_protocolo_a_partir_de_documento(documento, *, criar_no_eprotocolo=True) -> Protocolo:
    """Cria um Protocolo local vinculado a um documento interno.

    Quando ``criar_no_eprotocolo`` é True (padrão), também chama a integração
    (real ou mock) e salva o número retornado. Nunca quebra: erros de
    integração deixam o protocolo em status ``erro`` com log registrado.
    """
    ct = ContentType.objects.get_for_model(documento.__class__)
    protocolo = Protocolo.objects.create(
        origem_tipo=Protocolo.ORIGEM_INTERNA,
        origem_content_type=ct,
        origem_object_id=documento.pk,
        status_local=Protocolo.STATUS_RASCUNHO,
    )

    if not criar_no_eprotocolo:
        return protocolo

    payload = gerar_payload_protocolo(protocolo)
    try:
        resultado = epro.criar_protocolo(payload)
    except EProtocoloError as exc:
        protocolo.status_local = Protocolo.STATUS_ERRO
        protocolo.save(update_fields=["status_local"])
        registrar_log(protocolo, "criar_protocolo", erro=exc,
                      endpoint="criar_protocolo", metodo="POST", request_payload=payload)
        raise

    _aplicar_dados_criacao(protocolo, resultado, payload)
    protocolo.save()
    _registrar_movimentacao(protocolo, "CRIACAO", resultado.mensagem or "Protocolo criado.")
    registrar_log(protocolo, "criar_protocolo", resultado=resultado,
                  endpoint="criar_protocolo", metodo="POST", request_payload=payload)
    return protocolo


@transaction.atomic
def vincular_protocolo_manual(numero, *, documento=None, assunto="", descricao="") -> Protocolo:
    """Cadastra um protocolo já existente no eProtocolo (origem externa/manual).

    Pode opcionalmente vincular a um documento interno. Não chama a API de
    criação (o protocolo já existe lá fora); apenas registra localmente.
    """
    origem_tipo = Protocolo.ORIGEM_INTERNA if documento is not None else Protocolo.ORIGEM_MANUAL
    ct = obj_id = None
    if documento is not None:
        ct = ContentType.objects.get_for_model(documento.__class__)
        obj_id = documento.pk

    protocolo = Protocolo.objects.create(
        numero=(numero or "").strip(),
        origem_tipo=origem_tipo,
        origem_content_type=ct,
        origem_object_id=obj_id,
        assunto_resumo=(assunto or "")[:255],
        descricao_resumo=descricao or "",
        status_local=Protocolo.STATUS_CRIADO if numero else Protocolo.STATUS_RASCUNHO,
    )
    _registrar_movimentacao(protocolo, "VINCULO_MANUAL", "Protocolo vinculado manualmente.")
    registrar_log(protocolo, "vincular_protocolo_manual",
                  resultado=ResultadoOperacao(sucesso=True, dados={"numero": protocolo.numero},
                                              mock=cfg.em_modo_mock()))
    return protocolo


# ---------------------------------------------------------------------------
# Documentos
# ---------------------------------------------------------------------------
def enviar_documento_principal(protocolo: Protocolo) -> ProtocoloDocumento | None:
    """Gera o PDF do documento de origem e o envia ao eProtocolo.

    Best-effort: se o PDF não puder ser gerado neste ambiente (dependências de
    conversão ausentes), retorna ``None`` e registra log — o usuário pode então
    anexar o PDF manualmente.
    """
    if protocolo.origem_object is None:
        return None
    conteudo, nome_arquivo, tipo = resolver_pdf_documento(protocolo.origem_object)
    if conteudo is None:
        registrar_log(protocolo, "enviar_documento_principal",
                      erro=EProtocoloError("PDF do documento indisponível neste ambiente."))
        return None
    return anexar_documento(protocolo, tipo=tipo, nome_arquivo=nome_arquivo, conteudo=conteudo)


def anexar_documento(protocolo: Protocolo, *, tipo, nome_arquivo, conteudo: bytes,
                     origem_object=None) -> ProtocoloDocumento:
    """Envia um PDF (bytes) ao eProtocolo e registra o ProtocoloDocumento local."""
    numero = protocolo.numero or ""
    try:
        resultado = epro.enviar_documento(numero, conteudo, nome_arquivo,
                                          metadata={"tipo": tipo})
    except EProtocoloError as exc:
        registrar_log(protocolo, "enviar_documento", erro=exc,
                      endpoint="enviar_documento", metodo="POST",
                      request_payload={"nomeArquivo": nome_arquivo, "tipo": tipo})
        raise

    dados = resultado.dados or {}
    ct = obj_id = None
    if origem_object is not None:
        ct = ContentType.objects.get_for_model(origem_object.__class__)
        obj_id = origem_object.pk
    elif protocolo.origem_object is not None:
        ct = protocolo.origem_content_type
        obj_id = protocolo.origem_object_id

    documento = ProtocoloDocumento.objects.create(
        protocolo=protocolo,
        tipo_documento=tipo,
        nome_arquivo=nome_arquivo,
        codigo_documento_eprotocolo=dados.get("codigoDocumento", ""),
        md5=dados.get("md5", epro.calcular_md5(conteudo)),
        tamanho_bytes=dados.get("tamanhoBytes", len(conteudo)),
        enviado_em=timezone.now(),
        esta_no_volume=bool(dados.get("estaNoVolume", False)),
        origem_content_type=ct,
        origem_object_id=obj_id,
        payload_json=mascarar_dados(dados),
    )
    if protocolo.status_local in (Protocolo.STATUS_RASCUNHO, Protocolo.STATUS_CRIADO):
        protocolo.status_local = Protocolo.STATUS_DOCUMENTOS_ENVIADOS
        protocolo.save(update_fields=["status_local"])
    _registrar_movimentacao(protocolo, "DOCUMENTO_ENVIADO", f"Documento enviado: {nome_arquivo}.")
    registrar_log(protocolo, "enviar_documento", resultado=resultado,
                  endpoint="enviar_documento", metodo="POST",
                  request_payload={"nomeArquivo": nome_arquivo, "tipo": tipo})
    return documento


def concluir_cadastro_eprotocolo(protocolo: Protocolo) -> ResultadoOperacao:
    try:
        resultado = epro.concluir_protocolo(protocolo.numero or "")
    except EProtocoloError as exc:
        registrar_log(protocolo, "concluir_protocolo", erro=exc,
                      endpoint="concluir_protocolo", metodo="POST")
        raise
    protocolo.situacao_eprotocolo = (resultado.dados or {}).get("situacao", "") or protocolo.situacao_eprotocolo
    protocolo.save(update_fields=["situacao_eprotocolo"])
    _registrar_movimentacao(protocolo, "CADASTRO_CONCLUIDO", "Cadastro concluído no eProtocolo.")
    registrar_log(protocolo, "concluir_protocolo", resultado=resultado,
                  endpoint="concluir_protocolo", metodo="POST")
    return resultado


# ---------------------------------------------------------------------------
# Assinaturas
# ---------------------------------------------------------------------------
def solicitar_assinatura_documento(protocolo: Protocolo, documento, cpf, nome=None,
                                   observacao="") -> ProtocoloAssinatura:
    cpf_digitos = "".join(ch for ch in (cpf or "") if ch.isdigit())
    payload = {
        "tipo": "ASSINATURA",
        "cpfDestinatario": cpf_digitos,
        "nomeDestinatario": nome or "",
        "codigoDocumento": getattr(documento, "codigo_documento_eprotocolo", "") if documento else "",
        "observacao": observacao,
    }
    try:
        resultado = epro.criar_pendencia(protocolo.numero or "", payload)
    except EProtocoloError as exc:
        registrar_log(protocolo, "solicitar_assinatura", erro=exc,
                      endpoint="criar_pendencia", metodo="POST",
                      request_payload=payload)
        raise

    dados = resultado.dados or {}
    agora = timezone.now()
    assinatura = ProtocoloAssinatura.objects.create(
        protocolo=protocolo,
        documento=documento,
        cpf_assinante=cpf_digitos,
        nome_assinante=nome or "",
        status=ProtocoloAssinatura.STATUS_PENDENTE,
        observacao=observacao,
        solicitado_em=agora,
        payload_json=mascarar_dados(dados),
    )
    # Pendência espelhada para acompanhamento.
    ProtocoloPendencia.objects.create(
        protocolo=protocolo,
        documento=documento,
        codigo_pendencia=dados.get("codigoPendencia", ""),
        tipo="ASSINATURA",
        status=ProtocoloPendencia.STATUS_PENDENTE,
        cpf_destinatario=cpf_digitos,
        nome_destinatario=nome or "",
        criado_em=agora,
        payload_json=mascarar_dados(dados),
    )
    protocolo.status_local = Protocolo.STATUS_AGUARDANDO_ASSINATURA
    protocolo.save(update_fields=["status_local"])
    _registrar_movimentacao(protocolo, "ASSINATURA_SOLICITADA",
                            f"Assinatura solicitada a {nome or 'destinatário'}.")
    registrar_log(protocolo, "solicitar_assinatura", resultado=resultado,
                  endpoint="criar_pendencia", metodo="POST", request_payload=payload)
    return assinatura


# ---------------------------------------------------------------------------
# Tramitação
# ---------------------------------------------------------------------------
def tramitar(protocolo: Protocolo, cod_local_para, *, cpf_destinatario=None,
             parecer=None, nome_local_para="", nome_destinatario="") -> ProtocoloTramitacao:
    cpf_digitos = "".join(ch for ch in (cpf_destinatario or "") if ch.isdigit())
    payload = {
        "codLocalDe": protocolo.cod_local_atual or protocolo.cod_local_origem,
        "codLocalPara": cod_local_para,
        "cpfDestinatario": cpf_digitos,
        "parecer": parecer or "",
        "codTipoTramitacao": cfg.get("COD_TIPO_TRAMITACAO_PADRAO", ""),
    }
    try:
        resultado = epro.tramitar_protocolo(protocolo.numero or "", payload)
    except EProtocoloError as exc:
        registrar_log(protocolo, "tramitar", erro=exc,
                      endpoint="tramitar_protocolo", metodo="POST", request_payload=payload)
        raise

    dados = resultado.dados or {}
    tramitacao = ProtocoloTramitacao.objects.create(
        protocolo=protocolo,
        cod_local_de=payload["codLocalDe"],
        nome_local_de=protocolo.nome_local_atual or protocolo.nome_local_origem,
        cod_local_para=cod_local_para,
        nome_local_para=nome_local_para,
        cpf_destinatario=cpf_digitos,
        nome_destinatario=nome_destinatario,
        parecer=parecer or "",
        data_tramitacao=timezone.now(),
        payload_json=mascarar_dados(dados),
    )
    protocolo.cod_local_atual = cod_local_para
    protocolo.nome_local_atual = nome_local_para or protocolo.nome_local_atual
    protocolo.status_local = Protocolo.STATUS_EM_TRAMITACAO
    protocolo.ultima_movimentacao_em = timezone.now()
    protocolo.save(update_fields=["cod_local_atual", "nome_local_atual",
                                  "status_local", "ultima_movimentacao_em"])
    _registrar_movimentacao(protocolo, "TRAMITACAO",
                            f"Tramitado para {nome_local_para or cod_local_para}.")
    registrar_log(protocolo, "tramitar", resultado=resultado,
                  endpoint="tramitar_protocolo", metodo="POST", request_payload=payload)
    return tramitacao


# ---------------------------------------------------------------------------
# Sincronização
# ---------------------------------------------------------------------------
@transaction.atomic
def sincronizar_protocolo(protocolo: Protocolo) -> Protocolo:
    """Atualiza situação, local, responsável e coleções a partir do eProtocolo."""
    if not protocolo.numero:
        protocolo.ultima_sincronizacao_em = timezone.now()
        protocolo.save(update_fields=["ultima_sincronizacao_em"])
        return protocolo

    numero = protocolo.numero
    try:
        consulta = epro.consultar_protocolo(numero)
    except EProtocoloError as exc:
        registrar_log(protocolo, "sincronizar", erro=exc,
                      endpoint="consultar_protocolo", metodo="GET")
        raise

    dados = consulta.dados or {}
    protocolo.situacao_eprotocolo = dados.get("situacao", "") or protocolo.situacao_eprotocolo
    protocolo.cod_local_atual = dados.get("codLocalAtual", "") or protocolo.cod_local_atual
    protocolo.nome_local_atual = dados.get("nomeLocalAtual", "") or protocolo.nome_local_atual
    protocolo.cpf_responsavel_atual = dados.get("cpfResponsavelAtual", "") or protocolo.cpf_responsavel_atual
    protocolo.nome_responsavel_atual = dados.get("nomeResponsavelAtual", "") or protocolo.nome_responsavel_atual
    protocolo.payload_atual_json = mascarar_dados(dados)
    protocolo.modo_mock = consulta.mock
    protocolo.ultima_sincronizacao_em = timezone.now()

    _sincronizar_movimentacoes(protocolo, numero)
    _sincronizar_tramitacoes(protocolo, numero)
    _sincronizar_pendencias(protocolo, numero)

    if protocolo.status_local not in (Protocolo.STATUS_CONCLUIDO, Protocolo.STATUS_CANCELADO):
        if protocolo.pendencias_abertas.exists():
            protocolo.status_local = Protocolo.STATUS_COM_PENDENCIA
        elif (dados.get("situacao") or "").upper() == "CONCLUIDO":
            protocolo.status_local = Protocolo.STATUS_CONCLUIDO
        elif protocolo.status_local == Protocolo.STATUS_CRIADO:
            protocolo.status_local = Protocolo.STATUS_EM_TRAMITACAO

    protocolo.save()
    registrar_log(protocolo, "sincronizar", resultado=consulta,
                  endpoint="consultar_protocolo", metodo="GET")
    return protocolo


def sincronizar_protocolos_ativos():
    """Sincroniza todos os protocolos ativos com número. Retorna (ok, falhas)."""
    ok = falhas = 0
    qs = Protocolo.objects.filter(ativo=True).exclude(numero="")
    for protocolo in qs:
        try:
            sincronizar_protocolo(protocolo)
            ok += 1
        except EProtocoloError:
            falhas += 1
            logger.warning("Falha ao sincronizar protocolo %s", protocolo.numero)
    return ok, falhas


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------
def _registrar_movimentacao(protocolo, tipo, descricao, *, local="", usuario=""):
    ProtocoloMovimentacao.objects.create(
        protocolo=protocolo, tipo=tipo, descricao=descricao,
        local=local or protocolo.nome_local_atual, usuario=usuario,
        data_movimentacao=timezone.now(),
    )
    protocolo.ultima_movimentacao_em = timezone.now()
    protocolo.save(update_fields=["ultima_movimentacao_em"])


def _sincronizar_movimentacoes(protocolo, numero):
    try:
        resultado = epro.listar_movimentacoes(numero)
    except EProtocoloError:
        return
    itens = (resultado.dados or {}).get("movimentacoes", []) or []
    for item in itens:
        descricao = item.get("descricao", "")
        tipo = item.get("tipo", "")
        if protocolo.movimentacoes.filter(tipo=tipo, descricao=descricao).exists():
            continue
        ProtocoloMovimentacao.objects.create(
            protocolo=protocolo, tipo=tipo, descricao=descricao,
            local=item.get("local", ""), usuario=item.get("usuario", ""),
            data_movimentacao=_parse_data(item.get("data")), payload_json=mascarar_dados(item),
        )


def _sincronizar_tramitacoes(protocolo, numero):
    try:
        resultado = epro.listar_tramitacoes(numero)
    except EProtocoloError:
        return
    for item in (resultado.dados or {}).get("tramitacoes", []) or []:
        cod_para = item.get("codLocalPara", "")
        data = _parse_data(item.get("dataTramitacao"))
        if protocolo.tramitacoes.filter(cod_local_para=cod_para, data_tramitacao=data).exists():
            continue
        ProtocoloTramitacao.objects.create(
            protocolo=protocolo,
            cod_local_de=item.get("codLocalDe", ""), nome_local_de=item.get("nomeLocalDe", ""),
            cod_local_para=cod_para, nome_local_para=item.get("nomeLocalPara", ""),
            cpf_destinatario="".join(ch for ch in str(item.get("cpfDestinatario", "")) if ch.isdigit()),
            nome_destinatario=item.get("nomeDestinatario", ""), parecer=item.get("parecer", ""),
            data_tramitacao=data, payload_json=mascarar_dados(item),
        )


def _sincronizar_pendencias(protocolo, numero):
    try:
        resultado = epro.listar_pendencias(numero)
    except EProtocoloError:
        return
    for item in (resultado.dados or {}).get("pendencias", []) or []:
        codigo = item.get("codigoPendencia", "")
        defaults = {
            "tipo": item.get("tipo", ""),
            "status": (item.get("status", "") or "pendente").lower(),
            "nome_destinatario": item.get("nomeDestinatario", ""),
            "payload_json": mascarar_dados(item),
        }
        if codigo:
            protocolo.pendencias.update_or_create(codigo_pendencia=codigo, defaults=defaults)


def _parse_data(valor):
    if not valor:
        return None
    from django.utils.dateparse import parse_datetime
    parsed = parse_datetime(str(valor))
    if parsed and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_default_timezone())
    return parsed


# ---------------------------------------------------------------------------
# Resolução de PDF dos documentos internos (best-effort, lazy, isolado)
# ---------------------------------------------------------------------------
def resolver_pdf_documento(documento) -> tuple[bytes | None, str, str]:
    """Tenta obter (bytes_pdf, nome_arquivo, tipo) de um documento interno.

    Decoupled e tolerante: qualquer falha de geração retorna ``(None, nome, tipo)``
    para que o fluxo de envio principal não quebre. O usuário pode anexar o PDF
    manualmente nesse caso.
    """
    nome_classe = type(documento).__name__
    tipo = {
        "Oficio": ProtocoloDocumento.TIPO_OFICIO,
        "TermoAutorizacao": ProtocoloDocumento.TIPO_TERMO,
        "Justificativa": ProtocoloDocumento.TIPO_JUSTIFICATIVA,
        "PlanoTrabalho": ProtocoloDocumento.TIPO_PLANO,
        "OrdemServico": ProtocoloDocumento.TIPO_ORDEM,
    }.get(nome_classe, ProtocoloDocumento.TIPO_ANEXO)

    if nome_classe == "Oficio":
        return _resolver_pdf_oficio(documento, tipo)
    referencia = getattr(documento, "pk", "doc")
    return None, f"{nome_classe.lower()}-{referencia}.pdf", tipo


def _resolver_pdf_oficio(oficio, tipo) -> tuple[bytes | None, str, str]:
    nome = f"oficio-{(getattr(oficio, 'numero_formatado', '') or oficio.pk).replace('/', '-')}.pdf"
    try:
        from documentos.services.facade import build_default_facade
        from documentos.services.types import DocumentoFormato, DocumentoTipo
        from oficios.documents import build_canonical_document_payload
        from oficios.docxtpl_context import build_oficio_docxtpl_context

        payload = build_canonical_document_payload(oficio, DocumentoTipo.OFICIO)
        docxtpl = build_oficio_docxtpl_context(oficio)
        doc = build_default_facade().gerar(
            tipo=DocumentoTipo.OFICIO, formato=DocumentoFormato.PDF,
            payload=payload, reference=(getattr(oficio, "numero_formatado", "") or str(oficio.pk)).replace("/", "-"),
            docxtpl_context=docxtpl,
        )
        return doc.conteudo, nome, tipo
    except Exception:  # pragma: no cover - depende de dependências de conversão
        logger.exception("Não foi possível gerar PDF do ofício para o protocolo.")
        return None, nome, tipo
