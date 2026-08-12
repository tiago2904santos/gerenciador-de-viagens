from django.db import models
from django.db.models import Q

from core.managers import AreaScopedManager
from core.models import TimeStampedModel
from core.normalizers import normalize_spaces
from core.normalizers import normalize_upper


class ModeloJustificativa(TimeStampedModel):
    """Texto reutilizável de justificativa, **por área de trabalho** (`NOVO-09`).

    Este model é o gêmeo de `oficios.ModeloMotivoOficio` e a forma aqui é a mesma,
    de propósito: mesmo campo `area`, mesmo índice, mesmas quatro constraints
    (global × por área) e o mesmo recorte no `is_padrao`. Antes ele era global, e
    isso tinha três consequências — o texto de uma unidade entrava no documento de
    outra, marcar um modelo como padrão numa área **desmarcava o das outras**, e o
    `unique` no `nome` impedia duas áreas de usarem o mesmo título.
    """

    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="modelos_justificativa",
        verbose_name="Area de trabalho",
    )
    nome = models.CharField(max_length=120)
    texto = models.TextField()
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=100)
    is_padrao = models.BooleanField(default=False)

    # `BE-09`: `objects` recorta pela área ativa; `all_objects` é a saída explícita
    # para código que precisa enxergar todas. `default_manager_name` mantém o admin,
    # as relações reversas e `validate_unique` irrestritos — ver `core/managers.py`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["ordem", "nome"]
        verbose_name = "Modelo de justificativa"
        verbose_name_plural = "Modelos de justificativa"
        indexes = [
            models.Index(
                fields=["area", "ordem", "nome"], name="just_modelo_area_ordem_idx"
            ),
        ]
        # As quatro condicionais, e não um `unique_together`, porque `area` é
        # anulável: em SQL `NULL != NULL`, então um `unique(area, nome)` puro
        # deixaria passar duas linhas globais com o mesmo nome. Idêntico a
        # `oficios/models.py:369-374`.
        constraints = [
            models.UniqueConstraint(
                fields=["nome"],
                condition=Q(area__isnull=True),
                name="just_modelo_nome_global_unique",
            ),
            models.UniqueConstraint(
                fields=["area", "nome"],
                condition=Q(area__isnull=False),
                name="just_modelo_area_nome_unique",
            ),
            models.UniqueConstraint(
                fields=["area"],
                condition=Q(area__isnull=False) & Q(is_padrao=True),
                name="just_modelo_area_padrao_unique",
            ),
            models.UniqueConstraint(
                fields=["is_padrao"],
                condition=Q(area__isnull=True) & Q(is_padrao=True),
                name="just_modelo_global_padrao_unique",
            ),
        ]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.nome = normalize_upper(self.nome)
        self.texto = normalize_spaces(self.texto)
        if self.is_padrao:
            # `NOVO-09`: sem o `.filter(area=self.area)`, marcar um modelo como
            # padrão numa área desmarcava o padrão de **todas** as outras.
            # `BE-09`: `all_objects`, mesmo motivo de `justificativas/services.py` — o
            # escopo é o `self.area`, e recortar desfaria o `NOVO-09`.
            ModeloJustificativa.all_objects.exclude(pk=self.pk).filter(area=self.area).update(
                is_padrao=False
            )
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
        on_delete=models.CASCADE,
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
