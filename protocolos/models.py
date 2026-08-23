"""Models da Central de Protocolos.

Protocolo é uma **camada de processo/tramitação**, não um novo tipo de
documento. Ele se vincula (via ``GenericForeignKey``) a um documento interno já
existente (Ofício, Termo, Justificativa, Plano de Trabalho, Ordem de Serviço)
ou pode ser cadastrado manualmente como protocolo externo.

Nenhum dado sensível (token, client_secret) é persistido. CPFs são guardados
crus apenas onde necessário e mascarados na exibição (ver ``cpf_mascarado``).
"""

from __future__ import annotations

import re

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils import timezone


def mascarar_cpf(cpf: str | None) -> str:
    """Mascara um CPF para exibição: 123.***.***-09."""
    digitos = "".join(ch for ch in (cpf or "") if ch.isdigit())
    if len(digitos) != 11:
        return cpf or ""
    return f"{digitos[0:3]}.***.***-{digitos[9:11]}"


class Protocolo(models.Model):
    # -- estado interno ----------------------------------------------------
    STATUS_RASCUNHO = "rascunho"
    STATUS_CRIADO = "criado"
    STATUS_DOCUMENTOS_ENVIADOS = "documentos_enviados"
    STATUS_AGUARDANDO_ASSINATURA = "aguardando_assinatura"
    STATUS_EM_TRAMITACAO = "em_tramitacao"
    STATUS_COM_PENDENCIA = "com_pendencia"
    STATUS_CONCLUIDO = "concluido"
    STATUS_ERRO = "erro"
    STATUS_CANCELADO = "cancelado"
    STATUS_LOCAL_CHOICES = [
        (STATUS_RASCUNHO, "Rascunho"),
        (STATUS_CRIADO, "Criado"),
        (STATUS_DOCUMENTOS_ENVIADOS, "Documentos enviados"),
        (STATUS_AGUARDANDO_ASSINATURA, "Aguardando assinatura"),
        (STATUS_EM_TRAMITACAO, "Em tramitação"),
        (STATUS_COM_PENDENCIA, "Com pendência"),
        (STATUS_CONCLUIDO, "Concluído"),
        (STATUS_ERRO, "Erro"),
        (STATUS_CANCELADO, "Cancelado"),
    ]

    ORIGEM_INTERNA = "interna"
    ORIGEM_MANUAL = "manual"
    ORIGEM_EPROTOCOLO_REAL = "eprotocolo_real"
    ORIGEM_CHOICES = [
        (ORIGEM_INTERNA, "Documento interno"),
        (ORIGEM_MANUAL, "Externo / manual"),
        (ORIGEM_EPROTOCOLO_REAL, "eProtocolo real"),
    ]

    numero = models.CharField(
        "Número do protocolo", max_length=30, blank=True, default="", db_index=True,
        help_text="Número no eProtocolo (ex.: 24.123.456-7). Vazio enquanto pendente.",
    )
    status_local = models.CharField(
        max_length=30, choices=STATUS_LOCAL_CHOICES, default=STATUS_RASCUNHO, db_index=True,
    )
    situacao_eprotocolo = models.CharField(
        "Situação no eProtocolo", max_length=60, blank=True, default="",
    )
    origem_tipo = models.CharField(max_length=20, choices=ORIGEM_CHOICES, default=ORIGEM_INTERNA)

    # -- vínculo genérico com documento interno ----------------------------
    origem_content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    origem_object_id = models.PositiveIntegerField(null=True, blank=True)
    origem_object = GenericForeignKey("origem_content_type", "origem_object_id")

    # -- resumo ------------------------------------------------------------
    assunto_resumo = models.CharField(max_length=255, blank=True, default="")
    descricao_resumo = models.TextField(blank=True, default="")

    # -- órgão / locais ----------------------------------------------------
    cod_orgao = models.CharField(max_length=30, blank=True, default="")
    nome_orgao = models.CharField(max_length=200, blank=True, default="")
    cod_local_origem = models.CharField(max_length=30, blank=True, default="")
    nome_local_origem = models.CharField(max_length=200, blank=True, default="")
    cod_local_atual = models.CharField(max_length=30, blank=True, default="")
    nome_local_atual = models.CharField(max_length=200, blank=True, default="")

    # -- responsável atual -------------------------------------------------
    cpf_responsavel_atual = models.CharField(max_length=11, blank=True, default="")
    nome_responsavel_atual = models.CharField(max_length=200, blank=True, default="")

    # -- datas -------------------------------------------------------------
    criado_no_sistema_em = models.DateTimeField(default=timezone.now, editable=False)
    criado_no_eprotocolo_em = models.DateTimeField(null=True, blank=True)
    ultima_sincronizacao_em = models.DateTimeField(null=True, blank=True)
    ultima_movimentacao_em = models.DateTimeField(null=True, blank=True)

    # -- diversos ----------------------------------------------------------
    payload_atual_json = models.JSONField(default=dict, blank=True)
    modo_mock = models.BooleanField(
        default=False, help_text="Criado/atualizado em modo mock (sem integração real).",
    )
    ativo = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-criado_no_sistema_em"]
        verbose_name = "Protocolo"
        verbose_name_plural = "Protocolos"
        constraints = [
            models.UniqueConstraint(
                fields=["numero"],
                condition=~models.Q(numero=""),
                name="protocolo_numero_unico_quando_preenchido",
            )
        ]

    def __str__(self) -> str:
        return self.numero or f"Protocolo #{self.pk} (pendente)"

    # -- URLs (conveniência para templates) -------------------------------
    def get_absolute_url(self):
        return reverse("protocolos:detail", args=[self.pk])

    def get_detail_url(self):
        return self.get_absolute_url()

    def get_atualizar_url(self):
        return reverse("protocolos:atualizar", args=[self.pk])

    def get_enviar_documento_url(self):
        return reverse("protocolos:enviar_documento", args=[self.pk])

    def get_solicitar_assinatura_url(self):
        return reverse("protocolos:solicitar_assinatura", args=[self.pk])

    def get_tramitar_url(self):
        return reverse("protocolos:tramitar", args=[self.pk])

    def get_concluir_url(self):
        return reverse("protocolos:concluir", args=[self.pk])

    def get_movimentacoes_url(self):
        return reverse("protocolos:movimentacoes", args=[self.pk])

    def get_logs_url(self):
        return reverse("protocolos:logs", args=[self.pk])

    # -- helpers de exibição ----------------------------------------------
    @property
    def numero_display(self) -> str:
        if not self.numero:
            return "Pendente"
        from core.utils.masks import format_protocolo
        return format_protocolo(self.numero) or self.numero

    @property
    def cpf_responsavel_mascarado(self) -> str:
        return mascarar_cpf(self.cpf_responsavel_atual)

    @property
    def origem_label(self) -> str:
        if self.origem_object is not None:
            return str(self.origem_object)
        origem_demo = (self.payload_atual_json or {}).get("origemDemo")
        if origem_demo:
            return origem_demo
        if self.origem_tipo == self.ORIGEM_EPROTOCOLO_REAL:
            return "eProtocolo real"
        if self.origem_tipo == self.ORIGEM_MANUAL:
            return "Externo / manual"
        return "—"

    @property
    def origem_tipo_documento(self) -> str:
        if self.origem_content_type_id:
            return self.origem_content_type.model_class().__name__
        return ""

    @property
    def documento_especie_display(self) -> str:
        if self.origem_content_type_id:
            return self.origem_content_type.model_class()._meta.verbose_name.title()
        payload = self.payload_atual_json or {}
        for chave in ("especie", "nomeEspecie", "especieDocumento", "tipoDocumento"):
            valor = payload.get(chave)
            if valor:
                return str(valor)
        origem_demo = (self.payload_atual_json or {}).get("origemDemo", "")
        if origem_demo:
            return re.sub(r"\s+(?:no\.?)?\s*\d+/\d{4}.*$", "", origem_demo, flags=re.IGNORECASE).strip() or origem_demo
        primeiro_documento = next(iter(self.documentos.all()), None)
        if primeiro_documento:
            return primeiro_documento.get_tipo_documento_display()
        if self.origem_tipo == self.ORIGEM_EPROTOCOLO_REAL:
            return "eProtocolo real"
        if self.origem_tipo == self.ORIGEM_MANUAL:
            return "Externo / manual"
        return "-"

    @property
    def documento_numero_ano_display(self) -> str:
        if self.origem_object is not None:
            numero_formatado = getattr(self.origem_object, "numero_formatado", "")
            if numero_formatado:
                return numero_formatado
            numero = getattr(self.origem_object, "numero", None)
            ano = getattr(self.origem_object, "ano", None)
            if numero and ano:
                return f"{numero}/{ano}"
        origem_demo = (self.payload_atual_json or {}).get("origemDemo", "")
        match = re.search(r"(\d+/\d{4})", origem_demo)
        if match:
            return match.group(1)
        payload = self.payload_atual_json or {}
        for chave in ("documento", "numeroAnoDocumento", "numeroDocumentoAno", "numeroDocumentoFormatado"):
            valor = payload.get(chave)
            if valor:
                return str(valor)
        numero = payload.get("numeroDocumento")
        ano = payload.get("anoDocumento")
        if numero and ano:
            return f"{numero}/{ano}"
        return "-"

    @property
    def palavra_chave_1_display(self) -> str:
        payload = self.payload_atual_json or {}
        for chave in ("palavraChave1", "palavraChave", "nomePalavraChave", "codPalavraChave"):
            valor = payload.get(chave)
            if valor:
                return str(valor)
        palavras = payload.get("palavrasChave")
        if isinstance(palavras, str) and palavras:
            return palavras
        if isinstance(palavras, list) and palavras:
            primeira = palavras[0]
            if isinstance(primeira, dict):
                return str(primeira.get("nome") or primeira.get("descricao") or primeira.get("codigo") or "-")
            return str(primeira)
        return "-"

    @property
    def assunto_display(self) -> str:
        if self.assunto_resumo:
            return self.assunto_resumo
        payload = self.payload_atual_json or {}
        for chave in ("assunto", "nomeAssunto", "descricaoAssunto"):
            valor = payload.get(chave)
            if valor:
                return str(valor)
        return "-"

    @property
    def descricao_display(self) -> str:
        if self.descricao_resumo:
            return self.descricao_resumo
        payload = self.payload_atual_json or {}
        for chave in ("descricao", "detalhamento", "descricaoProtocolo", "detalhamentoProtocolo"):
            valor = payload.get(chave)
            if valor:
                return str(valor)
        return "-"

    @property
    def interessado_display(self) -> str:
        primeiro = self._primeiro_interessado_payload()
        if isinstance(primeiro, dict):
            for chave in ("nome", "nomeInteressado", "razaoSocial", "descricao"):
                valor = primeiro.get(chave)
                if valor:
                    return str(valor)
        elif primeiro:
            return str(primeiro)

        payload = self.payload_atual_json or {}
        for chave in ("interessado", "nomeInteressado", "requerente", "solicitante"):
            valor = payload.get(chave)
            if valor:
                return str(valor)
        return self.nome_responsavel_atual or "-"

    def _primeiro_interessado_payload(self):
        payload = self.payload_atual_json or {}
        for chave in ("interessados", "interessado1", "servidores"):
            itens = payload.get(chave)
            if isinstance(itens, list) and itens:
                return itens[0]
            if isinstance(itens, dict):
                return itens
        return None

    @property
    def interessado_tipo_display(self) -> str:
        interessado = self._primeiro_interessado_payload()
        if isinstance(interessado, dict):
            for chave in ("tipo", "tipoInteressado", "categoria"):
                valor = interessado.get(chave)
                if valor:
                    return str(valor)
        return "SECAO"

    @property
    def interessado_tipo_documento_display(self) -> str:
        interessado = self._primeiro_interessado_payload()
        if isinstance(interessado, dict):
            for chave in ("tipoDocumento", "tipoDoc", "tipoIdentificacao"):
                valor = interessado.get(chave)
                if valor:
                    return str(valor)
        if self.cpf_responsavel_atual:
            return "CPF"
        return "-"

    @property
    def interessado_identificacao_display(self) -> str:
        interessado = self._primeiro_interessado_payload()
        if isinstance(interessado, dict):
            for chave in ("identificacao", "documento", "cpf", "cnpj", "numeroDocumento"):
                valor = interessado.get(chave)
                if valor:
                    return str(valor)
        return self.cpf_responsavel_mascarado or "-"

    @property
    def cidade_display(self) -> str:
        payload = self.payload_atual_json or {}
        for chave in ("cidade", "nomeCidade", "municipio", "nomeMunicipio"):
            valor = payload.get(chave)
            if valor:
                return str(valor)
        return "CURITIBA / PR" if self.modo_mock else "-"

    @property
    def acesso_display(self) -> str:
        payload = self.payload_atual_json or {}
        for chave in ("acesso", "nivelAcesso", "tipoAcesso"):
            valor = payload.get(chave)
            if valor:
                return str(valor)
        return "Restrito" if self.modo_mock else "-"

    @property
    def prioridade_display(self) -> str:
        payload = self.payload_atual_json or {}
        for chave in ("prioridade", "prioritario", "urgente"):
            valor = payload.get(chave)
            if valor not in (None, ""):
                if isinstance(valor, bool):
                    return "Sim" if valor else "Nao"
                return str(valor)
        return "Nao"

    @property
    def cadastro_display(self) -> str:
        payload = self.payload_atual_json or {}
        for chave in ("cadastro", "dataCadastro", "criadoEm", "dataCriacao"):
            valor = payload.get(chave)
            if valor:
                return str(valor)
        data = self.criado_no_eprotocolo_em or self.criado_no_sistema_em
        return data.strftime("%d/%m/%Y") if data else "-"

    @property
    def informacao_pendencia_display(self) -> str:
        payload = self.payload_atual_json or {}
        for chave in ("informacaoPendencia", "informacoesPendencia", "complementoPendencia"):
            valor = payload.get(chave)
            if valor:
                return str(valor)
        pendencia = self.pendencias_abertas.first()
        if pendencia:
            destino = pendencia.nome_destinatario or pendencia.cpf_destinatario_mascarado
            if destino:
                return f"{pendencia.tipo or 'Pendencia'} com {destino}"
            return pendencia.tipo or "-"
        return "-"

    @property
    def pendencias_abertas(self):
        return self.pendencias.exclude(
            status__in=[ProtocoloPendencia.STATUS_CONCLUIDA, ProtocoloPendencia.STATUS_CANCELADA]
        )

    @property
    def status_local_variant(self) -> str:
        """Mapeia o status interno para uma variante de chip do design system."""
        return {
            self.STATUS_RASCUNHO: "draft",
            self.STATUS_CRIADO: "info",
            self.STATUS_DOCUMENTOS_ENVIADOS: "info",
            self.STATUS_AGUARDANDO_ASSINATURA: "pending",
            self.STATUS_EM_TRAMITACAO: "info",
            self.STATUS_COM_PENDENCIA: "warning",
            self.STATUS_CONCLUIDO: "success",
            self.STATUS_ERRO: "danger",
            self.STATUS_CANCELADO: "muted",
        }.get(self.status_local, "muted")


class ProtocoloDocumento(models.Model):
    TIPO_OFICIO = "OFICIO"
    TIPO_TERMO = "TERMO_AUTORIZACAO"
    TIPO_JUSTIFICATIVA = "JUSTIFICATIVA"
    TIPO_PLANO = "PLANO_TRABALHO"
    TIPO_ORDEM = "ORDEM_SERVICO"
    TIPO_ANEXO = "ANEXO"
    TIPO_CHOICES = [
        (TIPO_OFICIO, "Ofício"),
        (TIPO_TERMO, "Termo de Autorização"),
        (TIPO_JUSTIFICATIVA, "Justificativa"),
        (TIPO_PLANO, "Plano de Trabalho"),
        (TIPO_ORDEM, "Ordem de Serviço"),
        (TIPO_ANEXO, "Anexo manual"),
    ]

    protocolo = models.ForeignKey(
        Protocolo, on_delete=models.CASCADE, related_name="documentos",
    )
    tipo_documento = models.CharField(max_length=30, choices=TIPO_CHOICES, default=TIPO_ANEXO)
    nome_arquivo = models.CharField(max_length=255, blank=True, default="")
    arquivo_pdf = models.FileField(upload_to="protocolos/documentos/", null=True, blank=True)
    codigo_documento_eprotocolo = models.CharField(max_length=60, blank=True, default="")
    md5 = models.CharField(max_length=32, blank=True, default="")
    tamanho_bytes = models.PositiveIntegerField(null=True, blank=True)
    enviado_em = models.DateTimeField(null=True, blank=True)
    esta_no_volume = models.BooleanField(default=False)
    assinado = models.BooleanField(default=False)

    origem_content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    origem_object_id = models.PositiveIntegerField(null=True, blank=True)
    origem_object = GenericForeignKey("origem_content_type", "origem_object_id")

    payload_json = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Documento do protocolo"
        verbose_name_plural = "Documentos do protocolo"

    def __str__(self) -> str:
        return self.nome_arquivo or f"Documento #{self.pk}"

    @property
    def enviado(self) -> bool:
        return bool(self.codigo_documento_eprotocolo or self.enviado_em)


class ProtocoloAssinatura(models.Model):
    STATUS_PENDENTE = "pendente"
    STATUS_ASSINADO = "assinado"
    STATUS_CANCELADO = "cancelado"
    STATUS_ERRO = "erro"
    STATUS_DESCONHECIDO = "desconhecido"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_ASSINADO, "Assinado"),
        (STATUS_CANCELADO, "Cancelado"),
        (STATUS_ERRO, "Erro"),
        (STATUS_DESCONHECIDO, "Desconhecido"),
    ]

    protocolo = models.ForeignKey(
        Protocolo, on_delete=models.CASCADE, related_name="assinaturas",
    )
    documento = models.ForeignKey(
        ProtocoloDocumento, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assinaturas",
    )
    cpf_assinante = models.CharField(max_length=11, blank=True, default="")
    nome_assinante = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDENTE)
    observacao = models.CharField(max_length=255, blank=True, default="")
    solicitado_em = models.DateTimeField(null=True, blank=True)
    assinado_em = models.DateTimeField(null=True, blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)
    payload_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-solicitado_em", "-pk"]
        verbose_name = "Assinatura do protocolo"
        verbose_name_plural = "Assinaturas do protocolo"

    def __str__(self) -> str:
        return f"Assinatura {self.nome_assinante or self.cpf_assinante_mascarado} ({self.get_status_display()})"

    @property
    def cpf_assinante_mascarado(self) -> str:
        return mascarar_cpf(self.cpf_assinante)


class ProtocoloPendencia(models.Model):
    STATUS_PENDENTE = "pendente"
    STATUS_CONCLUIDA = "concluida"
    STATUS_CANCELADA = "cancelada"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_CONCLUIDA, "Concluída"),
        (STATUS_CANCELADA, "Cancelada"),
    ]

    protocolo = models.ForeignKey(
        Protocolo, on_delete=models.CASCADE, related_name="pendencias",
    )
    documento = models.ForeignKey(
        ProtocoloDocumento, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="pendencias",
    )
    codigo_pendencia = models.CharField(max_length=60, blank=True, default="")
    tipo = models.CharField(max_length=60, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDENTE)
    cpf_destinatario = models.CharField(max_length=11, blank=True, default="")
    nome_destinatario = models.CharField(max_length=200, blank=True, default="")
    criado_em = models.DateTimeField(null=True, blank=True)
    concluido_em = models.DateTimeField(null=True, blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)
    payload_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-criado_em", "-pk"]
        verbose_name = "Pendência do protocolo"
        verbose_name_plural = "Pendências do protocolo"

    def __str__(self) -> str:
        return f"Pendência {self.tipo or self.codigo_pendencia} ({self.get_status_display()})"

    @property
    def cpf_destinatario_mascarado(self) -> str:
        return mascarar_cpf(self.cpf_destinatario)


class ProtocoloTramitacao(models.Model):
    protocolo = models.ForeignKey(
        Protocolo, on_delete=models.CASCADE, related_name="tramitacoes",
    )
    cod_local_de = models.CharField(max_length=30, blank=True, default="")
    nome_local_de = models.CharField(max_length=200, blank=True, default="")
    cod_local_para = models.CharField(max_length=30, blank=True, default="")
    nome_local_para = models.CharField(max_length=200, blank=True, default="")
    cpf_destinatario = models.CharField(max_length=11, blank=True, default="")
    nome_destinatario = models.CharField(max_length=200, blank=True, default="")
    parecer = models.TextField(blank=True, default="")
    data_tramitacao = models.DateTimeField(null=True, blank=True)
    payload_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-data_tramitacao", "-pk"]
        verbose_name = "Tramitação do protocolo"
        verbose_name_plural = "Tramitações do protocolo"

    def __str__(self) -> str:
        return f"{self.nome_local_de or self.cod_local_de} → {self.nome_local_para or self.cod_local_para}"

    @property
    def cpf_destinatario_mascarado(self) -> str:
        return mascarar_cpf(self.cpf_destinatario)


class ProtocoloMovimentacao(models.Model):
    protocolo = models.ForeignKey(
        Protocolo, on_delete=models.CASCADE, related_name="movimentacoes",
    )
    tipo = models.CharField(max_length=60, blank=True, default="")
    descricao = models.TextField(blank=True, default="")
    local = models.CharField(max_length=200, blank=True, default="")
    usuario = models.CharField(max_length=200, blank=True, default="")
    data_movimentacao = models.DateTimeField(null=True, blank=True)
    payload_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-data_movimentacao", "-pk"]
        verbose_name = "Movimentação do protocolo"
        verbose_name_plural = "Movimentações do protocolo"

    def __str__(self) -> str:
        return f"{self.tipo or 'Movimentação'} — {self.descricao[:40]}"


class ProtocoloLog(models.Model):
    """Log técnico de integração. NUNCA armazena token/client_secret/Authorization.

    Payloads são mascarados antes de salvar (ver ``protocolos.services``).
    """

    protocolo = models.ForeignKey(
        Protocolo, on_delete=models.CASCADE, null=True, blank=True, related_name="logs",
    )
    acao = models.CharField(max_length=80, db_index=True)
    endpoint = models.CharField(max_length=255, blank=True, default="")
    metodo = models.CharField(max_length=10, blank=True, default="")
    status_code = models.PositiveIntegerField(null=True, blank=True)
    sucesso = models.BooleanField(default=True)
    modo_mock = models.BooleanField(default=False)
    erro = models.TextField(blank=True, default="")
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(default=timezone.now, editable=False, db_index=True)

    class Meta:
        ordering = ["-criado_em", "-pk"]
        verbose_name = "Log de integração"
        verbose_name_plural = "Logs de integração"

    def __str__(self) -> str:
        marcador = "OK" if self.sucesso else "ERRO"
        return f"[{marcador}] {self.acao} ({self.criado_em:%d/%m/%Y %H:%M})"
