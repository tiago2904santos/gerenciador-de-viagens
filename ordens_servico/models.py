from __future__ import annotations

from django.db import models
from django.utils import timezone

from cadastros.models import CancelavelModel
from cadastros.models import Cidade
from cadastros.models import Servidor
from cadastros.models import TimeStampedModel
from oficios.models import Oficio


class OrdemServico(TimeStampedModel, CancelavelModel):
    numero = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    ano = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    evento = models.ForeignKey(
        "eventos.Evento",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="ordens_servico",
    )
    oficios = models.ManyToManyField(
        Oficio,
        blank=True,
        related_name="ordens_servico",
        verbose_name="Ofícios vinculados",
    )
    data_evento_inicio = models.DateField("Data inicial do evento", null=True, blank=True)
    data_evento_fim = models.DateField("Data final do evento", null=True, blank=True)
    destinos = models.ManyToManyField(
        Cidade,
        blank=True,
        related_name="ordens_servico",
        verbose_name="Destinos",
    )
    servidores = models.ManyToManyField(
        Servidor,
        blank=True,
        related_name="ordens_servico",
        verbose_name="Servidores",
    )
    motivo = models.TextField("Motivo", blank=True, default="")

    class Meta:
        ordering = ["-ano", "-numero"]
        verbose_name = "Ordem de Serviço"
        verbose_name_plural = "Ordens de Serviço"

    def __str__(self) -> str:
        return self.numero_formatado

    @property
    def numero_formatado(self) -> str:
        if self.numero and self.ano:
            return f"OS {self.numero:03d}/{self.ano}"
        return f"OS #{self.pk or 'nova'}"

    @property
    def periodo_display(self) -> str:
        inicio = self.data_evento_inicio
        fim = self.data_evento_fim
        if not inicio:
            return "Período não informado"
        if not fim or fim == inicio:
            return inicio.strftime("%d/%m/%Y")
        return f"{inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}"

    @property
    def destinos_display(self) -> str:
        if not self.pk:
            return "Sem destino"
        dest = list(self.destinos.select_related("estado").order_by("nome")[:3])
        if not dest:
            return "Sem destino"
        parts = [f"{c.nome}/{c.uf}" for c in dest]
        return ", ".join(parts)

    def save(self, *args, **kwargs):
        if not self.numero:
            self._assign_numero()
        super().save(*args, **kwargs)

    def _assign_numero(self):
        ano = timezone.localdate().year
        last = (
            OrdemServico.objects.filter(ano=ano)
            .order_by("-numero")
            .values_list("numero", flat=True)
            .first()
        )
        self.numero = (last or 0) + 1
        self.ano = ano
