# Eventos serao agrupadores OPCIONAIS de documentos, nao fluxo obrigatorio.
from django.db import models

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

    TIPO_PCPR_COMUNIDADE = "pcpr_comunidade"
    TIPO_OPERACAO_POLICIAL = "operacao_policial"
    TIPO_PARANA_EM_ACAO = "parana_em_acao"
    TIPO_EXPO = "expo"
    TIPO_JUSTICA_BAIRRO = "justica_bairro"
    TIPO_OUTROS = "outros"
    TIPO_CHOICES = [
        (TIPO_PCPR_COMUNIDADE, "PCPR na Comunidade"),
        (TIPO_OPERACAO_POLICIAL, "Operação Policial"),
        (TIPO_PARANA_EM_ACAO, "Paraná em Ação"),
        (TIPO_EXPO, "Expo"),
        (TIPO_JUSTICA_BAIRRO, "Justiça no Bairro"),
        (TIPO_OUTROS, "Outros"),
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
    tipo = models.CharField("Tipo do evento", max_length=30, choices=TIPO_CHOICES, blank=True, default="")
    tipo_outro = models.CharField("Tipo personalizado (quando Outros)", max_length=120, blank=True, default="")
    destinos_extras = models.JSONField("Destinos adicionais", default=list, blank=True)
    motivo = models.TextField("Motivo", blank=True, default="")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_RASCUNHO)
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
