from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class DriveCredenciais(models.Model):
    """Tokens OAuth 2.0 da conta Google autorizada. Registro único (singleton)."""

    access_token = models.TextField()
    refresh_token = models.TextField()
    token_expiry = models.DateTimeField(null=True, blank=True)
    scope = models.TextField(blank=True)
    pasta_raiz_id = models.CharField(max_length=200, blank=True, default="")
    pasta_raiz_nome = models.CharField(max_length=255, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Credencial Google Drive"
        verbose_name_plural = "Credenciais Google Drive"

    def __str__(self) -> str:
        return f"OAuth Drive (atualizado {self.atualizado_em:%d/%m/%Y %H:%M})"


class DriveReorganizacaoJob(models.Model):
    """Acompanha uma reorganização em massa rodando em segundo plano.

    Evita o timeout (erro interno) do request síncrono: o botão inicia o job,
    retorna na hora, e a página acompanha o status por polling.
    """

    STATUS_EM_ANDAMENTO = "em_andamento"
    STATUS_CONCLUIDA = "concluida"
    STATUS_ERRO = "erro"
    STATUS_CHOICES = [
        (STATUS_EM_ANDAMENTO, "Em andamento"),
        (STATUS_CONCLUIDA, "Concluída"),
        (STATUS_ERRO, "Erro"),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_EM_ANDAMENTO, db_index=True)
    total_eventos = models.PositiveIntegerField(default=0)
    eventos_processados = models.PositiveIntegerField(default=0)
    avulsos = models.PositiveIntegerField(default=0)
    erros = models.PositiveIntegerField(default=0)
    mensagem = models.TextField(blank=True, default="")
    iniciado_em = models.DateTimeField(auto_now_add=True)
    finalizado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Job de reorganização do Drive"
        verbose_name_plural = "Jobs de reorganização do Drive"
        ordering = ["-iniciado_em"]

    def __str__(self) -> str:
        return f"Reorganização {self.get_status_display()} ({self.iniciado_em:%d/%m %H:%M})"


class DriveArquivo(models.Model):
    """Registro de um DocumentoArtefato enviado ao Google Drive."""

    artefato = models.OneToOneField(
        "documentos.DocumentoArtefato",
        on_delete=models.CASCADE,
        related_name="drive_arquivo",
    )
    file_id = models.CharField(max_length=200)
    url = models.URLField(max_length=500, blank=True)
    nome = models.CharField(max_length=255, blank=True)
    mime_type = models.CharField(max_length=255, blank=True)
    mock = models.BooleanField(default=False)
    # Atalho de aparição dupla (pasta global por tipo).
    atalho_id = models.CharField(max_length=200, blank=True, default="")
    atalho_pasta_id = models.CharField(max_length=200, blank=True, default="")
    enviado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Arquivo no Drive"
        verbose_name_plural = "Arquivos no Drive"
        ordering = ["-enviado_em"]

    def __str__(self) -> str:
        return f"Drive: {self.nome or self.file_id}"


class DriveArquivoExterno(models.Model):
    """Rastreia no Drive arquivos que NÃO são ``DocumentoArtefato``.

    Cobre os ``FileField`` de prestação de contas (despacho, comprovante,
    relatório técnico/diário assinados, anexos) e de evento (convite, ofício
    solicitante, documentos de solicitação). Usa ``GenericForeignKey`` + nome do
    campo para idempotência, evitando criar uma coluna ``drive_*`` em cada
    modelo de origem.
    """

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    origem = GenericForeignKey("content_type", "object_id")
    campo = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Nome do FileField de origem (vazio quando o modelo tem um único arquivo).",
    )

    file_id = models.CharField(max_length=200)
    url = models.URLField(max_length=500, blank=True)
    nome = models.CharField(max_length=255, blank=True)
    pasta_id = models.CharField(max_length=200, blank=True, default="")
    mime_type = models.CharField(max_length=255, blank=True)
    mock = models.BooleanField(default=False)
    # Atalho de aparição dupla (pasta global por tipo).
    atalho_id = models.CharField(max_length=200, blank=True, default="")
    atalho_pasta_id = models.CharField(max_length=200, blank=True, default="")
    enviado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Arquivo externo no Drive"
        verbose_name_plural = "Arquivos externos no Drive"
        ordering = ["-enviado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "campo"],
                name="drive_arquivo_externo_unico_por_campo",
            )
        ]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self) -> str:
        return f"Drive externo: {self.nome or self.file_id}"


class DriveSyncStatus(models.Model):
    """Registra falhas de sincronização com o Drive (existe só enquanto há erro).

    Um registro por (content_type, object_id) de origem (``DocumentoArtefato``,
    ``PrestacaoContas``, ``EventoAnexo``, ``EventoDocumentoSolicitacao``).
    Criado na primeira falha, incrementado a cada nova tentativa malsucedida e
    apagado assim que a sincronização for bem-sucedida. Alimenta o retry em
    segundo plano (Celery) e o painel de pendências da tela de configuração.

    ``object_id`` é ``CharField`` (não ``PositiveIntegerField``) porque
    ``DocumentoArtefato`` usa chave primária UUID, diferente dos demais
    modelos rastreados aqui (pk inteiro).
    """

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=64)
    origem = GenericForeignKey("content_type", "object_id")

    tentativas = models.PositiveIntegerField(default=1)
    ultimo_erro = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pendência de sincronização com o Drive"
        verbose_name_plural = "Pendências de sincronização com o Drive"
        ordering = ["-atualizado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id"], name="drive_sync_status_unico"
            )
        ]

    def __str__(self) -> str:
        return f"{self.content_type.name} #{self.object_id} ({self.tentativas}x)"
