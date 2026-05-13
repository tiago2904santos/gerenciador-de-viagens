import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ConfiguracaoChaveAssinatura(models.Model):
    STORAGE_PKCS12 = "pkcs12"
    STORAGE_PKCS11 = "pkcs11"
    STORAGE_CHOICES = [
        (STORAGE_PKCS12, "PKCS#12"),
        (STORAGE_PKCS11, "PKCS#11"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=120)
    storage_kind = models.CharField(max_length=16, choices=STORAGE_CHOICES, default=STORAGE_PKCS12)
    alias = models.CharField(max_length=120, blank=True, default="")
    pkcs12_path = models.CharField(max_length=512, blank=True, default="")
    certificate_fingerprint_sha256 = models.CharField(max_length=64, blank=True, default="")
    ativo = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name = "Configuração de chave de assinatura"
        verbose_name_plural = "Configurações de chaves de assinatura"

    def __str__(self) -> str:
        return self.nome


class AssinaturaDigital(models.Model):
    STATUS_PENDING = "pending"
    STATUS_VALID = "valid"
    STATUS_INVALID = "invalid"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendente"),
        (STATUS_VALID, "Válida"),
        (STATUS_INVALID, "Inválida"),
        (STATUS_FAILED, "Falhou"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    artefato = models.ForeignKey(
        "documentos.DocumentoArtefato",
        on_delete=models.CASCADE,
        related_name="assinaturas_registro",
    )
    chave = models.ForeignKey(
        ConfiguracaoChaveAssinatura,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assinaturas_emitidas",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    signer_subject = models.CharField(max_length=512, blank=True, default="")
    signer_serial = models.CharField(max_length=255, blank=True, default="")
    hash_documento = models.CharField(max_length=64)
    hash_documento_assinado = models.CharField(max_length=64, blank=True, default="")
    signature_field_name = models.CharField(max_length=120, default="AssinaturaCentralViagens")
    appearance = models.JSONField(default=dict, blank=True)
    evidencias = models.JSONField(default=dict, blank=True)
    codigo_verificacao = models.CharField(max_length=32, unique=True, db_index=True)
    nome_assinante = models.CharField(max_length=160, blank=True, default="")
    cpf_assinante = models.CharField(max_length=14, blank=True, default="")
    email_assinante = models.EmailField(blank=True, default="")
    metodo_autenticacao = models.CharField(max_length=40, blank=True, default="")
    ip_assinatura = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    posicao_carimbo_json = models.JSONField(blank=True, default=dict)
    pagina_carimbo = models.PositiveIntegerField(default=1)
    url_validacao = models.URLField(max_length=600, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    validado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Assinatura digital"
        verbose_name_plural = "Assinaturas digitais"

    def __str__(self) -> str:
        return f"{self.status} — {self.codigo_verificacao} — {self.artefato_id}"

class PedidoAssinaturaDocumento(models.Model):
    STATUS_PENDENTE = "pendente"
    STATUS_VISUALIZADA = "visualizada"
    STATUS_ASSINADO = "assinado"
    STATUS_EXPIRADO = "expirado"
    STATUS_RECUSADA = "recusada"
    STATUS_REVOGADA = "revogada"
    STATUS_CANCELADO = "cancelado"
    STATUS_SUBSTITUIDO = "substituido"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_VISUALIZADA, "Visualizada"),
        (STATUS_ASSINADO, "Assinado"),
        (STATUS_EXPIRADO, "Expirado"),
        (STATUS_RECUSADA, "Recusada"),
        (STATUS_REVOGADA, "Revogada"),
        (STATUS_CANCELADO, "Cancelado"),
        (STATUS_SUBSTITUIDO, "Substituido"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    artefato = models.ForeignKey(
        "documentos.DocumentoArtefato",
        on_delete=models.CASCADE,
        related_name="pedidos_assinatura",
    )
    token = models.CharField(max_length=96, unique=True, db_index=True)
    assinante_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pedidos_assinatura_documental",
    )
    assinante_servidor = models.ForeignKey(
        "cadastros.Servidor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pedidos_assinatura_documental",
    )
    nome_assinante_snapshot = models.CharField(max_length=160)
    cpf_assinante_snapshot = models.CharField(max_length=14, blank=True, default="")
    email_assinante_snapshot = models.EmailField(blank=True, default="")
    cargo_assinante_snapshot = models.CharField(max_length=160, blank=True, default="")
    unidade_assinante_snapshot = models.CharField(max_length=160, blank=True, default="")
    tipo_documento = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDENTE, db_index=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pedidos_assinatura_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField(db_index=True)
    visualizado_em = models.DateTimeField(null=True, blank=True)
    assinado_em = models.DateTimeField(null=True, blank=True)
    recusado_em = models.DateTimeField(null=True, blank=True)
    revogado_em = models.DateTimeField(null=True, blank=True)
    ip_visualizacao = models.GenericIPAddressField(null=True, blank=True)
    user_agent_visualizacao = models.TextField(blank=True, default="")
    ip_assinatura = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    motivo_recusa = models.TextField(blank=True, default="")
    posicao_etiqueta_json = models.JSONField(blank=True, default=dict)
    assinatura = models.OneToOneField(
        AssinaturaDigital,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pedido_documental",
    )
    hash_documento_original = models.CharField(max_length=64, blank=True, default="")
    hash_documento_assinado = models.CharField(max_length=64, blank=True, default="")
    auditoria = models.JSONField(blank=True, default=dict)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Pedido de assinatura documental"
        verbose_name_plural = "Pedidos de assinatura documental"
        indexes = [
            models.Index(fields=["artefato", "status", "expira_em"]),
        ]

    def __str__(self) -> str:
        return f"{self.status} - {self.tipo_documento} - {self.artefato_id}"

    @property
    def esta_expirado(self) -> bool:
        return bool(self.expira_em and self.expira_em <= timezone.now())


class EventoAssinatura(models.Model):
    id = models.BigAutoField(primary_key=True)
    assinatura = models.ForeignKey(
        AssinaturaDigital,
        on_delete=models.CASCADE,
        related_name="eventos",
    )
    tipo = models.CharField(max_length=32, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Evento de assinatura"
        verbose_name_plural = "Eventos de assinatura"

    def __str__(self) -> str:
        return f"{self.tipo} @ {self.criado_em}"
