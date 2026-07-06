# Eventos serao agrupadores OPCIONAIS de documentos, nao fluxo obrigatorio.
from django.db import models
from django.utils import timezone

from core.normalizers import normalize_spaces
from core.normalizers import normalize_upper
from cadastros.models import TimeStampedModel


class Evento(models.Model):
    """Agrupador OPCIONAL de documentos relacionados a uma viagem/acao.

    Evento nunca e obrigatorio: todo documento continua podendo ser criado de
    forma avulsa nos apps de origem. O evento apenas agrega os documentos reais
    (via FK opcional `evento` em cada documento) e reaproveita informacoes
    comuns (destino, datas, responsavel) para pre-preencher Oficio, Termo,
    Plano de Trabalho e Ordem de Servico.
    """

    STATUS_RASCUNHO = "rascunho"
    STATUS_EM_PREPARACAO = "em_preparacao"
    STATUS_DOCUMENTOS_GERADOS = "documentos_gerados"
    STATUS_EM_EXECUCAO = "em_execucao"
    STATUS_FINALIZADO = "finalizado"
    STATUS_CANCELADO = "cancelado"
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, "Rascunho"),
        (STATUS_EM_PREPARACAO, "Em preparacao"),
        (STATUS_DOCUMENTOS_GERADOS, "Documentos gerados"),
        (STATUS_EM_EXECUCAO, "Em execucao"),
        (STATUS_FINALIZADO, "Finalizado"),
        (STATUS_CANCELADO, "Cancelado"),
    ]

    titulo = models.CharField("Titulo", max_length=255, blank=True, default="")
    descricao = models.TextField("Descricao/objetivo", blank=True, default="")
    destino_uf = models.CharField("UF do destino", max_length=2, blank=True, default="")
    destino_cidade = models.CharField("Cidade do destino", max_length=255, blank=True, default="")
    data_inicio = models.DateField("Data inicial", null=True, blank=True)
    data_fim = models.DateField("Data final", null=True, blank=True)
    horario_inicio = models.TimeField("Horario inicial", null=True, blank=True)
    horario_fim = models.TimeField("Horario final", null=True, blank=True)
    unidade_responsavel = models.ForeignKey(
        "cadastros.Unidade",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="eventos",
        verbose_name="Unidade responsavel",
    )
    responsavel = models.ForeignKey(
        "cadastros.Servidor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="eventos_responsavel",
        verbose_name="Responsavel",
    )
    tipos = models.ManyToManyField(
        "eventos.TipoEvento",
        blank=True,
        related_name="eventos",
        verbose_name="Tipos do evento",
    )
    destinos_extras = models.JSONField("Destinos adicionais", default=list, blank=True)
    motivo = models.TextField("Motivo", blank=True, default="")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_RASCUNHO)
    motivo_cancelamento = models.TextField("Motivo do cancelamento", blank=True, default="")
    cancelado_em = models.DateTimeField("Cancelado em", null=True, blank=True)
    drive_folder_id = models.CharField("ID da pasta no Drive", max_length=255, blank=True, default="")
    drive_folder_url = models.URLField("URL da pasta no Drive", blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data_inicio", "-criado_em"]
        verbose_name = "Evento"
        verbose_name_plural = "Eventos"

    def __str__(self) -> str:
        return self.titulo or f"Evento #{self.pk or 'novo'}"

    @property
    def periodo_display(self) -> str:
        if not self.data_inicio:
            return "Periodo nao informado"
        if not self.data_fim or self.data_fim == self.data_inicio:
            return self.data_inicio.strftime("%d/%m/%Y")
        return f"{self.data_inicio.strftime('%d/%m/%Y')} a {self.data_fim.strftime('%d/%m/%Y')}"

    @property
    def destino_display(self) -> str:
        cidade = (self.destino_cidade or "").strip()
        uf = (self.destino_uf or "").strip()
        if cidade and uf:
            return f"{cidade}/{uf}"
        return cidade or uf or "Destino nao informado"

    @property
    def tipos_display(self) -> str:
        if not self.pk:
            return ""
        return " / ".join(self.tipos.values_list("nome", flat=True))

    def cancelar(self, motivo: str) -> None:
        """Cancela o evento e cascateia o cancelamento para todos os documentos vinculados."""
        motivo = (motivo or "").strip()
        self.status = self.STATUS_CANCELADO
        self.motivo_cancelamento = motivo
        self.cancelado_em = timezone.now()
        self.save(update_fields=["status", "motivo_cancelamento", "cancelado_em"])

        motivo_cascade = f"Evento cancelado: {motivo}" if motivo else "Evento cancelado."
        for related_name in ("oficios", "ordens_servico", "planos_trabalho", "termos_autorizacao", "roteiros"):
            manager = getattr(self, related_name)
            for documento in manager.filter(cancelado=False):
                documento.cancelar(motivo_cascade)


class TipoEvento(TimeStampedModel):
    """Tipo gerenciavel do evento (ex.: "PCPR na Comunidade", "Expo").

    Um evento pode ter mais de um tipo (ex.: acao conjunta "PCPR na Comunidade"
    + "Justica no Bairro"). A lista e mantida pelo usuario na tela de gerenciar
    tipos, sem valores fixos no codigo.
    """

    nome = models.CharField(max_length=120, unique=True)
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["ordem", "nome"]
        verbose_name = "Tipo de evento"
        verbose_name_plural = "Tipos de evento"

    def __str__(self) -> str:
        return self.nome

    def save(self, *args, **kwargs):
        self.nome = normalize_spaces(self.nome)
        super().save(*args, **kwargs)


EVENTO_SOLICITACAO_EXTENSOES = ["pdf", "png", "jpg", "jpeg"]


def evento_solicitacao_upload_to(instance, filename):
    return f"eventos/{instance.evento_id or 'novo'}/solicitacoes/{filename}"


class EventoDocumentoSolicitacao(models.Model):
    evento = models.ForeignKey(
        Evento,
        on_delete=models.CASCADE,
        related_name="documentos_solicitacao",
    )
    arquivo = models.FileField(upload_to=evento_solicitacao_upload_to)
    nome_original = models.CharField(max_length=255, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["criado_em"]
        verbose_name = "Documento de solicitação do evento"
        verbose_name_plural = "Documentos de solicitação do evento"

    def __str__(self):
        return self.nome_original or str(self.arquivo)


class ModeloMotivoEvento(TimeStampedModel):
    nome = models.CharField(max_length=120, unique=True)
    texto = models.TextField()
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=100)
    is_padrao = models.BooleanField(default=False)

    class Meta:
        ordering = ["ordem", "nome"]
        verbose_name = "Modelo de motivo de evento"
        verbose_name_plural = "Modelos de motivo de evento"

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.nome = normalize_upper(self.nome)
        self.texto = normalize_spaces(self.texto)
        if self.is_padrao:
            ModeloMotivoEvento.objects.exclude(pk=self.pk).update(is_padrao=False)
        super().save(*args, **kwargs)


class EventoAnexo(models.Model):
    """Arquivo de apoio do evento (convite, oficio solicitante, comprovante)."""

    TIPO_CONVITE = "convite"
    TIPO_OFICIO_SOLICITANTE = "oficio_solicitante"
    TIPO_COMPROVANTE = "comprovante"
    TIPO_OUTRO = "outro"
    TIPO_CHOICES = [
        (TIPO_CONVITE, "Convite"),
        (TIPO_OFICIO_SOLICITANTE, "Oficio solicitante"),
        (TIPO_COMPROVANTE, "Comprovante"),
        (TIPO_OUTRO, "Outro"),
    ]

    # CASCADE e correto aqui: o anexo pertence ao evento (nao e um documento
    # independente). A regra de SET_NULL vale para os documentos reais, que
    # precisam sobreviver a exclusao do evento.
    evento = models.ForeignKey(
        Evento,
        on_delete=models.CASCADE,
        related_name="anexos",
    )
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, default=TIPO_OUTRO)
    titulo = models.CharField("Titulo", max_length=255, blank=True, default="")
    arquivo = models.FileField("Arquivo", upload_to="eventos/anexos/%Y/%m/")
    observacoes = models.TextField("Observacoes", blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Anexo de evento"
        verbose_name_plural = "Anexos de evento"

    def __str__(self) -> str:
        return self.titulo or f"Anexo {self.get_tipo_display()} (#{self.pk or 'novo'})"
