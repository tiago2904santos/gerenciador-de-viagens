from django.db import models

from cadastros.models import Servidor
from oficios.models import Oficio
from roteiros.models import RoteiroTrecho


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
