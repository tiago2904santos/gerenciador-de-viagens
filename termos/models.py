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
    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="termos_autorizacao",
        verbose_name="Area de trabalho",
    )
    evento = models.ForeignKey(
        "eventos.Evento",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
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

    def save(self, *args, **kwargs):
        if self.area_id is None:
            if self.evento_id and self.evento and self.evento.area_id:
                self.area = self.evento.area
            elif self.oficio_id and self.oficio and self.oficio.area_id:
                self.area = self.oficio.area
            else:
                from core.tenancy import get_current_area

                self.area = get_current_area()
        super().save(*args, **kwargs)

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
            do_oficio = self.oficio.servidores_termo_autorizacao.select_related("cargo", "unidade").order_by("nome")
            if do_oficio.exists():
                return do_oficio
        if self.evento_id:
            do_evento = self._servidores_do_evento()
            if do_evento is not None:
                return do_evento
        return Servidor.objects.none()

    def _servidores_do_evento(self):
        """Servidores dos ofícios do evento (termo de autorização, com fallback nos participantes).

        Usado quando o termo genérico do evento não tem servidores próprios nem
        ofício vinculado — assim o download do termo genérico também gera um termo
        individual para cada servidor do evento.
        """
        ids: list[int] = []
        oficios = self.evento.oficios.prefetch_related(
            "servidores_termo_autorizacao",
            "servidores",
        )
        for oficio in oficios:
            do_termo = list(oficio.servidores_termo_autorizacao.all()) or list(oficio.servidores.all())
            ids.extend(servidor.pk for servidor in do_termo)
        ids = list(dict.fromkeys(ids))
        if not ids:
            return None
        return (
            Servidor.objects.filter(pk__in=ids)
            .select_related("cargo", "unidade")
            .order_by("nome")
        )

    def viatura_efetiva(self):
        if self.viatura_id:
            return self.viatura
        if self.oficio_id:
            return self.oficio.viatura
        return None

    def servidores_efetivos_com_oficio(self):
        """Servidores efetivos, junto com o oficio de origem de cada um.

        Quando o termo e generico do evento (sem oficio proprio) e os servidores
        vem por fallback dos oficios do evento, cada servidor carrega o oficio
        que realmente o originou — necessario para exibir numero e viatura
        corretos por servidor, já que o termo genérico em si não tem nenhum.
        """
        if not self.pk:
            return []
        selecionados = list(self.servidores.select_related("cargo", "unidade").order_by("nome"))
        if selecionados:
            oficio = self.oficio if self.oficio_id else None
            return [(servidor, oficio) for servidor in selecionados]
        if self.oficio_id:
            do_oficio = list(
                self.oficio.servidores_termo_autorizacao.select_related("cargo", "unidade").order_by("nome")
            )
            if do_oficio:
                return [(servidor, self.oficio) for servidor in do_oficio]
        if self.evento_id:
            pares = []
            vistos: set[int] = set()
            oficios = self.evento.oficios.select_related("viatura").prefetch_related(
                "servidores_termo_autorizacao", "servidores",
            )
            for oficio in oficios:
                do_termo = list(oficio.servidores_termo_autorizacao.all()) or list(oficio.servidores.all())
                for servidor in do_termo:
                    if servidor.pk in vistos:
                        continue
                    vistos.add(servidor.pk)
                    pares.append((servidor, oficio))
            return pares
        return []

    def _primeiro_destino_oficio(self):
        roteiro = getattr(self.oficio, "roteiro", None)
        if not roteiro:
            return None
        return roteiro.destinos.select_related("cidade", "estado").order_by("ordem", "pk").first()
