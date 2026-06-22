from django.db import models
from django.core.validators import FileExtensionValidator

from cadastros.models import Servidor
from oficios.models import Oficio
from roteiros.models import RoteiroTrecho


PRESTACAO_DOCUMENTO_EXTENSOES = ["pdf", "png", "jpg", "jpeg"]


def prestacao_documento_upload_to(instance, filename):
    return f"prestacoes_contas/{instance.pk or 'nova'}/{filename}"


def prestacao_documento_anexo_upload_to(instance, filename):
    return f"prestacoes_contas/{instance.prestacao_id or 'nova'}/{filename}"


def assinatura_origem_upload_to(instance, filename):
    return f"prestacoes_contas/{instance.prestacao_id or 'nova'}/assinaturas/origem_{instance.tipo}_{filename}"


def assinatura_png_upload_to(instance, filename):
    return f"prestacoes_contas/{instance.prestacao_id or 'nova'}/assinaturas/png_{instance.tipo}_{filename}"


def assinatura_assinado_upload_to(instance, filename):
    return f"prestacoes_contas/{instance.prestacao_id or 'nova'}/assinaturas/assinado_{instance.tipo}_{filename}"


class PrestacaoContas(models.Model):
    STATUS_PENDENTE = "pendente"
    STATUS_EM_PREENCHIMENTO = "em_preenchimento"
    STATUS_ENVIADA = "enviada"
    STATUS_APROVADA = "aprovada"
    STATUS_REPROVADA = "reprovada"

    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_EM_PREENCHIMENTO, "Em preenchimento"),
        (STATUS_ENVIADA, "Enviada"),
        (STATUS_APROVADA, "Aprovada"),
        (STATUS_REPROVADA, "Reprovada"),
    ]

    oficio = models.ForeignKey(
        Oficio,
        on_delete=models.CASCADE,
        related_name="prestacoes_contas",
    )
    servidor = models.ForeignKey(
        Servidor,
        on_delete=models.CASCADE,
        related_name="prestacoes_contas",
    )
    # Cópia editável do roteiro (o que realmente ocorreu na viagem). Quando
    # preenchida, substitui o roteiro do ofício no diário sem alterar o ofício.
    roteiro_ajustado = models.ForeignKey(
        "roteiros.Roteiro",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    numero_solicitacao = models.CharField(
        "Número da solicitação",
        max_length=60,
        blank=True,
        default="",
    )
    despacho_assinado = models.FileField(
        "Despacho assinado do ofício",
        upload_to=prestacao_documento_upload_to,
        blank=True,
        validators=[FileExtensionValidator(PRESTACAO_DOCUMENTO_EXTENSOES)],
    )
    comprovante_saque_transferencia = models.FileField(
        "Comprovante de saque/transferência",
        upload_to=prestacao_documento_upload_to,
        blank=True,
        validators=[FileExtensionValidator(PRESTACAO_DOCUMENTO_EXTENSOES)],
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDENTE)
    observacoes = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Prestação de Contas"
        verbose_name_plural = "Prestações de Contas"
        constraints = [
            models.UniqueConstraint(
                fields=["oficio", "servidor"],
                name="unique_prestacao_por_servidor_oficio",
            )
        ]

    def __str__(self):
        return f"Prestação — {self.servidor} / Ofício {self.oficio.numero_formatado}"

    @property
    def status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    @property
    def status_variant(self):
        return {
            self.STATUS_PENDENTE: "pending",
            self.STATUS_EM_PREENCHIMENTO: "warning",
            self.STATUS_ENVIADA: "info",
            self.STATUS_APROVADA: "success",
            self.STATUS_REPROVADA: "danger",
        }.get(self.status, "muted")


class PrestacaoDocumentoAnexo(models.Model):
    TIPO_DESPACHO = "despacho"
    TIPO_COMPROVANTE = "comprovante"

    TIPO_CHOICES = [
        (TIPO_DESPACHO, "Despacho assinado do ofício"),
        (TIPO_COMPROVANTE, "Comprovante de saque/transferência"),
    ]

    prestacao = models.ForeignKey(
        PrestacaoContas,
        on_delete=models.CASCADE,
        related_name="documentos_anexos",
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, db_index=True)
    arquivo = models.FileField(
        upload_to=prestacao_documento_anexo_upload_to,
        validators=[FileExtensionValidator(PRESTACAO_DOCUMENTO_EXTENSOES)],
    )
    nome_original = models.CharField(max_length=255, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["tipo", "criado_em", "pk"]
        verbose_name = "Anexo da prestação de contas"
        verbose_name_plural = "Anexos da prestação de contas"

    def __str__(self):
        return self.nome_original or self.arquivo.name


class RelatorioTecnico(models.Model):
    prestacao = models.OneToOneField(
        PrestacaoContas,
        on_delete=models.CASCADE,
        related_name="relatorio_tecnico",
    )
    motivo = models.TextField(blank=True, default="")
    diaria = models.CharField(max_length=255, blank=True, default="")
    translado = models.CharField(max_length=255, blank=True, default="")
    combustivel = models.CharField(max_length=255, blank=True, default="")
    passagem = models.CharField(max_length=255, blank=True, default="")
    atividade = models.TextField(blank=True, default="")
    conclusao = models.TextField(blank=True, default="")
    medidas = models.TextField(blank=True, default="")
    info_complementares = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Relatório Técnico"
        verbose_name_plural = "Relatórios Técnicos"

    def __str__(self):
        return f"RT — {self.prestacao}"


class DiarioBordo(models.Model):
    """Diário de bordo do veículo gerado a partir do roteiro do ofício da prestação.

    Os dados de cabeçalho (motorista, viatura, ofício, e-protocolo) vêm do ofício;
    os trechos vêm do roteiro. O usuário complementa KM inicial/final e a
    necessidade de abastecimento de cada trecho (ver ``DiarioBordoTrecho``).
    """

    prestacao = models.OneToOneField(
        PrestacaoContas,
        on_delete=models.CASCADE,
        related_name="diario_bordo",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Diário de Bordo"
        verbose_name_plural = "Diários de Bordo"

    def __str__(self):
        return f"Diário de bordo — {self.prestacao}"


class DiarioBordoTrecho(models.Model):
    """Linha do diário de bordo, espelhando um trecho do roteiro do ofício."""

    diario = models.ForeignKey(
        DiarioBordo,
        on_delete=models.CASCADE,
        related_name="trechos",
    )
    trecho = models.ForeignKey(
        RoteiroTrecho,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diario_bordo_trechos",
    )
    ordem = models.PositiveIntegerField(default=0)
    km_inicial = models.PositiveIntegerField(null=True, blank=True)
    km_final = models.PositiveIntegerField(null=True, blank=True)
    abastecimento = models.BooleanField(null=True, blank=True)

    class Meta:
        ordering = ["diario", "ordem", "pk"]
        verbose_name = "Trecho do diário de bordo"
        verbose_name_plural = "Trechos do diário de bordo"

    def __str__(self):
        return f"Trecho {self.ordem} — {self.diario_id}"


class AssinaturaDocumento(models.Model):
    """Assinatura eletrônica de um documento da prestação (RT ou Diário de Bordo).

    Registro canônico — há no máximo um por ``(prestacao, tipo)``. O "link" enviado
    ao signatário é representado por ``link_token`` (compartilhado entre RT e DB quando
    se gera um link único). O signatário confirma identidade (5 primeiros dígitos do
    CPF + nome), posiciona a assinatura e envia; o PDF carimbado fica em
    ``arquivo_assinado`` e passa a ser usado pelo sistema.
    """

    TIPO_RT = "rt"
    TIPO_DB = "db"
    TIPO_CHOICES = [
        (TIPO_RT, "Relatório Técnico"),
        (TIPO_DB, "Diário de Bordo"),
    ]

    STATUS_PENDENTE = "pendente"
    STATUS_ASSINADA = "assinada"
    STATUS_CANCELADA = "cancelada"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_ASSINADA, "Assinada"),
        (STATUS_CANCELADA, "Cancelada"),
    ]

    MODO_FONTE = "fonte"
    MODO_DESENHO = "desenho"
    MODO_CHOICES = [
        (MODO_FONTE, "Fonte"),
        (MODO_DESENHO, "Desenho"),
    ]

    prestacao = models.ForeignKey(
        PrestacaoContas,
        on_delete=models.CASCADE,
        related_name="assinaturas",
    )
    tipo = models.CharField(max_length=4, choices=TIPO_CHOICES, db_index=True)
    signer = models.ForeignKey(
        Servidor,
        on_delete=models.PROTECT,
        related_name="assinaturas_documentos",
    )
    nome_esperado = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDENTE)

    # Link enviado ao signatário (token compartilhado entre RT/DB no "link único").
    link_token = models.CharField(max_length=64, blank=True, default="", db_index=True)
    link_criado_em = models.DateTimeField(null=True, blank=True)
    link_expira_em = models.DateTimeField(null=True, blank=True)

    # Verificação de identidade.
    identidade_confirmada_em = models.DateTimeField(null=True, blank=True)

    # Snapshot do PDF não assinado (garante que o carimbo bate com o que foi exibido).
    arquivo_origem = models.FileField(upload_to=assinatura_origem_upload_to, blank=True)

    # Resultado da assinatura.
    modo = models.CharField(max_length=10, choices=MODO_CHOICES, blank=True, default="")
    fonte = models.CharField(max_length=60, blank=True, default="")
    assinatura_png = models.FileField(upload_to=assinatura_png_upload_to, blank=True)
    pagina = models.PositiveIntegerField(default=0)
    pos_x = models.FloatField(null=True, blank=True)
    pos_y = models.FloatField(null=True, blank=True)
    largura = models.FloatField(null=True, blank=True)
    altura = models.FloatField(null=True, blank=True)
    arquivo_assinado = models.FileField(upload_to=assinatura_assinado_upload_to, blank=True)
    assinado_em = models.DateTimeField(null=True, blank=True)
    assinado_ip = models.CharField(max_length=64, blank=True, default="")
    codigo_verificacao = models.CharField(max_length=12, blank=True, default="")

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["prestacao", "tipo"]
        verbose_name = "Assinatura de documento"
        verbose_name_plural = "Assinaturas de documentos"
        constraints = [
            models.UniqueConstraint(
                fields=["prestacao", "tipo"],
                name="uniq_assinatura_prestacao_tipo",
            )
        ]

    def __str__(self):
        return f"Assinatura {self.get_tipo_display()} — {self.prestacao_id}"

    @property
    def assinada(self) -> bool:
        return self.status == self.STATUS_ASSINADA and bool(self.arquivo_assinado)

    @property
    def link_expirado(self) -> bool:
        from django.utils import timezone as _tz

        return bool(self.link_expira_em and self.link_expira_em < _tz.now())

    @property
    def link_ativo(self) -> bool:
        return bool(self.link_token) and not self.link_expirado and not self.assinada

    @property
    def cpf_prefixo_esperado(self) -> str:
        cpf = (self.signer.cpf or "").strip() if self.signer_id else ""
        return cpf[:5]


class ModeloTextoRelatorioTecnico(models.Model):
    """Textos reutilizáveis para preencher rapidamente os campos do RT."""

    CAMPO_MOTIVO = "motivo"
    CAMPO_ATIVIDADE = "atividade"
    CAMPO_CONCLUSAO = "conclusao"
    CAMPO_MEDIDAS = "medidas"
    CAMPO_INFO = "info_complementares"

    CAMPO_CHOICES = [
        (CAMPO_MOTIVO, "Descrição do evento"),
        (CAMPO_ATIVIDADE, "Objetivo da participação"),
        (CAMPO_CONCLUSAO, "Conclusão"),
        (CAMPO_MEDIDAS, "Medidas a serem adotadas pelo órgão"),
        (CAMPO_INFO, "Informações complementares"),
    ]

    campo = models.CharField(max_length=30, choices=CAMPO_CHOICES, db_index=True)
    nome = models.CharField(max_length=120)
    texto = models.TextField()
    ordem = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["campo", "ordem", "nome"]
        verbose_name = "Modelo de texto do RT"
        verbose_name_plural = "Modelos de texto do RT"
        constraints = [
            models.UniqueConstraint(
                fields=["campo", "nome"],
                name="unique_modelo_texto_rt_campo_nome",
            )
        ]

    def __str__(self):
        return f"{self.get_campo_display()} — {self.nome}"
