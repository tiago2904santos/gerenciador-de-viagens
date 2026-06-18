from django.db import models

from cadastros.models import TimeStampedModel
from core.normalizers import normalize_spaces
from core.normalizers import normalize_upper


class ModeloJustificativa(TimeStampedModel):
    nome = models.CharField(max_length=120, unique=True)
    texto = models.TextField()
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=100)
    is_padrao = models.BooleanField(default=False)

    class Meta:
        ordering = ["ordem", "nome"]
        verbose_name = "Modelo de justificativa"
        verbose_name_plural = "Modelos de justificativa"

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.nome = normalize_upper(self.nome)
        self.texto = normalize_spaces(self.texto)
        if self.is_padrao:
            ModeloJustificativa.objects.exclude(pk=self.pk).update(is_padrao=False)
        super().save(*args, **kwargs)


class Justificativa(TimeStampedModel):
    STATUS_RASCUNHO = "RASCUNHO"
    STATUS_FINALIZADA = "FINALIZADA"
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, "Rascunho"),
        (STATUS_FINALIZADA, "Finalizada"),
    ]

    evento = models.ForeignKey(
        "eventos.Evento",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="justificativas",
    )
    oficio = models.OneToOneField(
        "oficios.Oficio",
        on_delete=models.CASCADE,
        related_name="justificativa",
    )
    modelo = models.ForeignKey(
        ModeloJustificativa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="justificativas",
    )
    texto = models.TextField(blank=True, default="")
    obrigatoria = models.BooleanField(default=False)
    dias_antecedencia = models.IntegerField(null=True, blank=True)
    prazo_dias = models.PositiveIntegerField(default=10)
    primeira_saida_dt = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO)

    class Meta:
        verbose_name = "Justificativa de ofício"
        verbose_name_plural = "Justificativas de ofício"

    def __str__(self):
        return f"Justificativa do Ofício {self.oficio.numero_formatado}"

    def save(self, *args, **kwargs):
        self.texto = normalize_spaces(self.texto)
        super().save(*args, **kwargs)
