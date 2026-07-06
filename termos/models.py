from __future__ import annotations

from django.db import models

from cadastros.models import CancelavelModel
from cadastros.models import Cidade
from cadastros.models import Estado
from cadastros.models import Servidor
from cadastros.models import TimeStampedModel
from cadastros.models import Viatura
from oficios.models import Oficio


class TermoAutorizacao(TimeStampedModel, CancelavelModel):
    evento = models.ForeignKey(
        "eventos.Evento",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="termos_autorizacao",
    )
    oficio = models.ForeignKey(
        Oficio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="termos_autorizacao",
        verbose_name="Oficio vinculado",
    )
    destino_estado = models.ForeignKey(
        Estado,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="UF do destino",
    )
    destino_cidade = models.ForeignKey(
        Cidade,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="termos_autorizacao",
        verbose_name="Cidade do destino",
    )
    destinos_extras = models.JSONField("Destinos adicionais", default=list, blank=True)
    data_evento_inicio = models.DateField("Data inicial do evento", null=True, blank=True)
    data_evento_fim = models.DateField("Data final do evento", null=True, blank=True)
    servidores = models.ManyToManyField(
        Servidor,
        blank=True,
        related_name="termos_autorizacao",
        verbose_name="Servidores",
    )
    viatura = models.ForeignKey(
        Viatura,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="termos_autorizacao",
        verbose_name="Viatura",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Termo de autorizacao"
        verbose_name_plural = "Termos de autorizacao"

    def __str__(self) -> str:
        return f"Termo #{self.pk or 'novo'} - {self.destino_display}"

    @property
    def destino_display(self) -> str:
        destino = self.destino_efetivo()
        return destino or "Destino nao informado"

    @property
    def periodo_display(self) -> str:
        inicio, fim = self.periodo_efetivo()
        if not inicio:
            return "Periodo nao informado"
        if not fim or fim == inicio:
            return inicio.strftime("%d/%m/%Y")
        return f"{inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}"

    def destino_efetivo(self) -> str:
        destinos = []
        if self.destino_cidade_id:
            destinos.append(f"{self.destino_cidade.nome}/{self.destino_cidade.uf}")
        for destino in self.destinos_extras or []:
            if not isinstance(destino, dict):
                continue
            cidade = (destino.get("cidade") or "").strip()
            uf = (destino.get("estado") or "").strip()
            if cidade and uf:
                destinos.append(f"{cidade}/{uf}")
            elif cidade or uf:
                destinos.append(cidade or uf)
        if destinos:
            return ", ".join(dict.fromkeys(destinos))
        if self.destino_estado_id:
            return self.destino_estado.sigla
        destino = self._primeiro_destino_oficio()
        return str(destino) if destino else ""

    def periodo_efetivo(self):
        inicio = self.data_evento_inicio
        fim = self.data_evento_fim or inicio
        if inicio:
            return inicio, fim
        roteiro = getattr(self.oficio, "roteiro", None)
        if not roteiro:
            return None, None
        saida = getattr(roteiro, "saida_dt", None)
        retorno = getattr(roteiro, "retorno_chegada_dt", None) or getattr(roteiro, "retorno_saida_dt", None)
        inicio = saida.date() if saida else None
        fim = retorno.date() if retorno else inicio
        return inicio, fim

    def servidores_efetivos(self):
        if not self.pk:
            return Servidor.objects.none()
        selecionados = self.servidores.select_related("cargo", "unidade").order_by("nome")
        if selecionados.exists():
            return selecionados
        if self.oficio_id:
            return self.oficio.servidores_termo_autorizacao.select_related("cargo", "unidade").order_by("nome")
        return Servidor.objects.none()

    def viatura_efetiva(self):
        if self.viatura_id:
            return self.viatura
        if self.oficio_id:
            return self.oficio.viatura
        return None

    def _primeiro_destino_oficio(self):
        roteiro = getattr(self.oficio, "roteiro", None)
        if not roteiro:
            return None
        return roteiro.destinos.select_related("cidade", "estado").order_by("ordem", "pk").first()
