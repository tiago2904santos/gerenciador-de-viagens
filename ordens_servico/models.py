from __future__ import annotations

from django.db import models
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.constraints import periodo_ordenado
from core.numeracao import NAMESPACE_ORDEM_SERVICO
from core.numeracao import reservar_numero
from core.managers import AreaScopedManager
from core.models import CancelavelModel
from cadastros.models import Cidade
from cadastros.models import Servidor
from core.models import TimeStampedModel
from oficios.models import Oficio


#: Mesmo motivo do `CONSTRAINT_NUMERO_OFICIO`: `core.numeracao` compara o metadado da
#: exceção contra este nome, então ele existe uma vez só.
CONSTRAINT_NUMERO_ORDEM_SERVICO = "ordens_servico_area_ano_numero_unique"


class OrdemServico(TimeStampedModel, CancelavelModel):
    TIPO_PADRAO = "PADRAO"
    TIPO_OPERACAO_RETORNO_POSTERIOR = "OPERACAO_RETORNO_POSTERIOR"
    TIPO_CAMINHAO = "CAMINHAO"
    TIPO_MICROONIBUS = "MICROONIBUS"
    TIPO_CERIMONIAL_ANTECIPADO = "CERIMONIAL_ANTECIPADO"

    FUNCAO_CONDUCAO = "CONDUCAO"
    FUNCAO_TECNICO = "TECNICO"
    FUNCAO_APOIO = "APOIO"
    FUNCAO_COORDENACAO = "COORDENACAO"
    FUNCAO_PREPARACAO = "PREPARACAO"

    FUNCAO_SERVIDOR_CHOICES = [
        (FUNCAO_CONDUCAO, "Condução"),
        (FUNCAO_TECNICO, "Técnico"),
        (FUNCAO_APOIO, "Apoio"),
        (FUNCAO_COORDENACAO, "Coordenação"),
        (FUNCAO_PREPARACAO, "Preparação"),
    ]

    TIPO_NECESSIDADE_CHOICES = [
        (TIPO_PADRAO, "Padrão / texto livre"),
        (TIPO_OPERACAO_RETORNO_POSTERIOR, "Operação policial - um dia posterior"),
        (TIPO_CAMINHAO, "Caminhão - dois dias antes e depois"),
        (TIPO_MICROONIBUS, "Micro-ônibus"),
        (TIPO_CERIMONIAL_ANTECIPADO, "Cerimonial - ida antecipada"),
    ]

    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        null=False,
        blank=True,
        on_delete=models.PROTECT,
        related_name="ordens_servico",
        verbose_name="Area de trabalho",
    )
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
    tipo_necessidade = models.CharField(
        "Tipo de necessidade",
        max_length=40,
        choices=TIPO_NECESSIDADE_CHOICES,
        default=TIPO_PADRAO,
    )
    motorista_equipe = models.ForeignKey(
        Servidor,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Motorista",
    )
    tecnico_equipe = models.ForeignKey(
        Servidor,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Técnico",
    )
    apoio_montagem = models.ForeignKey(
        Servidor,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Apoio de montagem",
    )
    apoio_escolta = models.ForeignKey(
        Servidor,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Apoio de escolta",
    )
    coordenador_cerimonial = models.ForeignKey(
        Servidor,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Coordenação de cerimonial",
    )
    apoio_cerimonial = models.ForeignKey(
        Servidor,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Apoio de cerimonial",
    )
    apoio_preparacao = models.ForeignKey(
        Servidor,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Apoio de preparação",
    )
    funcoes_servidores = models.JSONField("Funções dos servidores", blank=True, default=dict)
    motivo = models.TextField("Motivo", blank=True, default="")

    # `BE-09`: `objects` recorta pela área ativa; `all_objects` é a saída explícita
    # para código que precisa enxergar todas. `default_manager_name` mantém o admin,
    # as relações reversas e `validate_unique` irrestritos — ver `core/managers.py`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        ordering = ["-ano", "-numero"]
        default_manager_name = "all_objects"
        # `DB-10`: a lista recorta por área e ordena por `(-ano, -numero)`, e sem
        # este índice o banco lia a área inteira, ordenava e jogava fora tudo
        # menos a página. Medido com 20.000 OS em três áreas: o `Index Scan` pelo
        # índice da FK devolvia **6.666 linhas** para um `top-N heapsort` que
        # entregava 20. Com o índice, o `Limit` para na vigésima.
        #
        #     sem: 9,231 ms · 136 buffers · Sort Method: top-N heapsort
        #     com: 0,144 ms ·   4 buffers · sem Sort
        #
        # A constraint única parcial logo abaixo **não** substitui este índice: por
        # ser parcial (`WHERE ano IS NOT NULL AND numero IS NOT NULL`) o planner não
        # a usa nesta consulta, e a ordem dela é ascendente.
        indexes = [
            models.Index(fields=["area", "-ano", "-numero"], name="os_area_ano_numero_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["area", "ano", "numero"],
                condition=Q(ano__isnull=False, numero__isnull=False),
                name=CONSTRAINT_NUMERO_ORDEM_SERVICO,
            ),
            # `DB-07`: o período da OS é copiado do evento e reimpresso no documento.
            periodo_ordenado(
                "data_evento_inicio", "data_evento_fim", name="os_periodo_ordenado",
            ),
        ]
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
        # `NOVO-08`: mesmo contrato do `_destinos_display_os` do card de OS
        # (`ordens_servico/presenters.py:82`) — a propriedade do model tinha
        # ficado de fora. Refazer `select_related`/`order_by` aqui descarta o
        # cache de quem já prefetchou, e custa uma consulta por linha da lista.
        prefetched = getattr(self, "_prefetched_objects_cache", {}).get("destinos")
        if prefetched is not None:
            dest = list(prefetched)[:3]
        else:
            dest = list(self.destinos.select_related("estado").order_by("nome")[:3])
        if not dest:
            return "Sem destino"
        parts = [f"{c.nome}/{c.uf}" for c in dest]
        return ", ".join(parts)

    def save(self, *args, **kwargs):
        if self.area_id is None:
            if self.evento_id and self.evento and self.evento.area_id:
                self.area = self.evento.area
            else:
                from core.tenancy import get_current_area

                self.area = get_current_area()
        if self.numero:
            return super().save(*args, **kwargs)

        ano = timezone.localdate().year

        def escolher():
            # `_assign_numero` grava `numero` e `ano` no próprio objeto; devolvê-lo aqui é
            # o que `reservar_numero` usa para conferir a colisão depois.
            self._assign_numero()
            return self.numero

        def gravar(_numero):
            super(OrdemServico, self).save(*args, **kwargs)
            lacuna_id = getattr(self, "_lacuna_numeracao_id", None)
            if lacuna_id is not None:
                OrdemServicoNumeroLacuna.all_objects.filter(
                    pk=lacuna_id,
                    area_id=self.area_id,
                    ano=self.ano,
                    numero=self.numero,
                ).delete()

        def limpar():
            self.numero = None
            self.ano = None
            self._lacuna_numeracao_id = None

        # `BE-15`: o lock e o laço de três tentativas moravam aqui, copiados de
        # `oficios/services.py`. A política de escolha (`max+1`) fica; a mecânica é comum.
        with transaction.atomic():
            reservar_numero(
                namespace=NAMESPACE_ORDEM_SERVICO,
                area_id=self.area_id,
                ano=ano,
                modelo=OrdemServico,
                constraint=CONSTRAINT_NUMERO_ORDEM_SERVICO,
                escolher=escolher,
                gravar=gravar,
                ja_ocupado=self._numero_ocupado,
                apos_colisao=limpar,
            )

    def _numero_ocupado(self, numero: int) -> bool:
        """Outra OS já ocupa este (área, ano, número)?

        `BE-15`: substitui o casamento por texto da mensagem do `IntegrityError`, que só
        funcionava no PostgreSQL — ver o cabeçalho de `core/numeracao.py`.
        """
        # `BE-09`: `all_objects` — o escopo é a área **desta** OS, já no filtro.
        return (
            OrdemServico.all_objects.filter(
                area_id=self.area_id, ano=self.ano, numero=numero
            )
            .exclude(pk=self.pk)
            .exists()
        )

    def _assign_numero(self):
        ano = timezone.localdate().year
        lacuna = (
            OrdemServicoNumeroLacuna.all_objects.filter(
                area_id=self.area_id,
                ano=ano,
            )
            .order_by("numero")
            .first()
        )
        if lacuna is not None:
            self.numero = lacuna.numero
            self.ano = ano
            self._lacuna_numeracao_id = lacuna.pk
            return

        self._lacuna_numeracao_id = None
        # `BE-09`: `all_objects` de propósito. O escopo da numeração é o desta OS
        # (`self.area_id`), decidido nas quatro linhas abaixo — não o da área ativa
        # do request. Com `objects`, uma OS sem área salva por quem está numa área
        # daria `area=ativa AND area IS NULL` = vazio, e todo número voltaria a 1.
        queryset = OrdemServico.all_objects.filter(ano=ano)
        if self.area_id:
            queryset = queryset.filter(area=self.area)
        else:
            queryset = queryset.filter(area__isnull=True)
        last = queryset.order_by("-numero").values_list("numero", flat=True).first()
        self.numero = (last or 0) + 1
        self.ano = ano


class OrdemServicoNumeroLacuna(models.Model):
    """Número de OS liberado por exclusão; saltos manuais não entram aqui."""

    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.PROTECT,
        related_name="ordens_servico_lacunas",
        verbose_name="Area de trabalho",
    )
    ano = models.PositiveIntegerField(db_index=True)
    numero = models.PositiveIntegerField()
    liberado_em = models.DateTimeField(auto_now_add=True)

    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["ano", "numero"]
        verbose_name = "Número de Ordem de Serviço liberado"
        verbose_name_plural = "Números de Ordem de Serviço liberados"
        constraints = [
            models.UniqueConstraint(
                fields=["area", "ano", "numero"],
                name="os_lacuna_area_ano_numero_unique",
            ),
        ]

    def __str__(self):
        return f"{self.numero:02d}/{self.ano}"

