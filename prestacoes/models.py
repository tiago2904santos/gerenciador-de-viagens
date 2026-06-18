from django.db import models

from cadastros.models import Servidor
from cadastros.models import TimeStampedModel
from cadastros.models import Viatura
from eventos.models import Evento


class StatusDocumento:
    RASCUNHO = "rascunho"
    EM_PREENCHIMENTO = "em_preenchimento"
    FINALIZADO = "finalizado"

    CHOICES = [
        (RASCUNHO, "Rascunho"),
        (EM_PREENCHIMENTO, "Em preenchimento"),
        (FINALIZADO, "Finalizado"),
    ]


class StatusAssinatura:
    PENDENTE = "pendente"
    ASSINADO = "assinado"
    DISPENSADO = "dispensado"

    CHOICES = [
        (PENDENTE, "Pendente"),
        (ASSINADO, "Assinado"),
        (DISPENSADO, "Dispensado"),
    ]


class RelatorioTecnico(TimeStampedModel):
    evento = models.ForeignKey(
        Evento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="relatorios_tecnicos",
    )
    titulo = models.CharField(max_length=255)
    objetivo = models.TextField(blank=True, default="")
    periodo = models.CharField(max_length=120, blank=True, default="")
    local = models.CharField(max_length=255, blank=True, default="")
    servidores_participantes = models.TextField(blank=True, default="")
    atividades_realizadas = models.TextField(blank=True, default="")
    resultados_obtidos = models.TextField(blank=True, default="")
    intercorrencias = models.TextField(blank=True, default="")
    conclusao = models.TextField(blank=True, default="")
    status = models.CharField(max_length=30, choices=StatusDocumento.CHOICES, default=StatusDocumento.RASCUNHO)
    assinatura_status = models.CharField(
        max_length=30,
        choices=StatusAssinatura.CHOICES,
        default=StatusAssinatura.PENDENTE,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Relatório técnico"
        verbose_name_plural = "Relatórios técnicos"

    def __str__(self):
        return self.titulo


class DiarioBordo(TimeStampedModel):
    evento = models.ForeignKey(
        Evento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diarios_bordo",
    )
    titulo = models.CharField(max_length=255)
    destino = models.CharField(max_length=255, blank=True, default="")
    periodo = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=30, choices=StatusDocumento.CHOICES, default=StatusDocumento.RASCUNHO)
    assinatura_status = models.CharField(
        max_length=30,
        choices=StatusAssinatura.CHOICES,
        default=StatusAssinatura.PENDENTE,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Diário de bordo"
        verbose_name_plural = "Diários de bordo"

    def __str__(self):
        return self.titulo


class DiarioBordoRegistro(TimeStampedModel):
    diario = models.ForeignKey(DiarioBordo, on_delete=models.CASCADE, related_name="registros")
    data = models.DateField()
    hora_saida = models.TimeField(null=True, blank=True)
    hora_chegada = models.TimeField(null=True, blank=True)
    origem = models.CharField(max_length=255, blank=True, default="")
    destino = models.CharField(max_length=255, blank=True, default="")
    viatura = models.ForeignKey(
        Viatura,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diario_bordo_registros",
    )
    motorista = models.ForeignKey(
        Servidor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diario_bordo_registros_motorista",
    )
    km_inicial = models.PositiveIntegerField(null=True, blank=True)
    km_final = models.PositiveIntegerField(null=True, blank=True)
    atividades = models.TextField(blank=True, default="")
    observacoes = models.TextField(blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["data", "hora_saida", "pk"]
        verbose_name = "Registro do diário de bordo"
        verbose_name_plural = "Registros do diário de bordo"

    def __str__(self):
        return f"{self.diario} - {self.data:%d/%m/%Y}"


class PrestacaoContas(TimeStampedModel):
    STATUS_PENDENTE = "pendente"
    STATUS_EM_PREENCHIMENTO = "em_preenchimento"
    STATUS_ENVIADA = "enviada"
    STATUS_APROVADA = "aprovada"
    STATUS_REPROVADA = "reprovada"
    STATUS_FINALIZADA = "finalizada"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_EM_PREENCHIMENTO, "Em preenchimento"),
        (STATUS_ENVIADA, "Enviada"),
        (STATUS_APROVADA, "Aprovada"),
        (STATUS_REPROVADA, "Reprovada"),
        (STATUS_FINALIZADA, "Finalizada"),
    ]

    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="prestacoes_contas")
    relatorio_tecnico = models.ForeignKey(
        RelatorioTecnico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prestacoes_contas",
    )
    diario_bordo = models.ForeignKey(
        DiarioBordo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prestacoes_contas",
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDENTE)
    observacoes = models.TextField(blank=True, default="")
    assinatura_responsavel_status = models.CharField(
        max_length=30,
        choices=StatusAssinatura.CHOICES,
        default=StatusAssinatura.PENDENTE,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Prestação de contas"
        verbose_name_plural = "Prestações de contas"

    def __str__(self):
        return f"Prestação de contas - {self.evento}"
