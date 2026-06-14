from __future__ import annotations

from django.db import models
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from cadastros.models import Cargo
from cadastros.models import Cidade
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Estado
from cadastros.models import Servidor
from cadastros.models import TimeStampedModel
from cadastros.models import Unidade
from core.normalizers import normalize_spaces
from core.normalizers import normalize_upper


class ProgramaSolicitante(TimeStampedModel):
    """Programa/iniciativa que solicita a ação (ex.: Justiça no Bairro)."""

    nome = models.CharField(max_length=200, unique=True)
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["ordem", "nome"]
        verbose_name = "Programa solicitante"
        verbose_name_plural = "Programas solicitantes"

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.nome = normalize_upper(self.nome)
        super().save(*args, **kwargs)


class HorarioAtendimento(TimeStampedModel):
    """Faixa de horário disponível para seleção nos planos de trabalho."""

    faixa = models.CharField(max_length=60, unique=True)
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["ordem", "faixa"]
        verbose_name = "Horário de atendimento"
        verbose_name_plural = "Horários de atendimento"

    def __str__(self):
        return self.faixa

    def save(self, *args, **kwargs):
        self.faixa = normalize_spaces(self.faixa)
        super().save(*args, **kwargs)


class AtividadePlanoTrabalho(TimeStampedModel):
    """Catálogo gerenciável de atividades do Plano de Trabalho.

    Cada atividade carrega a meta exibida no documento e, opcionalmente, o
    recurso necessário associado — quando uma atividade é selecionada na etapa 3
    do wizard, sua meta e seu recurso entram automaticamente no plano.
    """

    codigo = models.CharField("Código", max_length=40, unique=True)
    nome = models.CharField("Nome", max_length=255)
    meta = models.TextField("Meta")
    recurso_necessario = models.TextField("Recurso necessário", blank=True, default="")
    ordem = models.PositiveIntegerField("Ordem", default=100)
    ativo = models.BooleanField("Ativo", default=True)

    class Meta:
        ordering = ["ordem", "nome"]
        verbose_name = "Atividade (Plano de Trabalho)"
        verbose_name_plural = "Atividades (Plano de Trabalho)"

    def __str__(self):
        return f"{self.codigo} — {self.nome}"

    def save(self, *args, **kwargs):
        if self.codigo:
            self.codigo = slugify(self.codigo).replace("-", "_").upper()
        self.nome = normalize_spaces(self.nome)
        self.meta = (self.meta or "").strip()
        self.recurso_necessario = (self.recurso_necessario or "").strip()
        super().save(*args, **kwargs)


class PlanoTrabalho(TimeStampedModel):
    STATUS_RASCUNHO = "RASCUNHO"
    STATUS_GERADO = "GERADO"
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, "Rascunho"),
        (STATUS_GERADO, "Gerado"),
    ]

    COORDENADOR_MODO_SERVIDOR = "SERVIDOR"
    COORDENADOR_MODO_MANUAL = "MANUAL"
    COORDENADOR_MODO_CHOICES = [
        (COORDENADOR_MODO_SERVIDOR, "Servidor"),
        (COORDENADOR_MODO_MANUAL, "Manual"),
    ]
    COORDENADOR_GENERO_MASCULINO = "MASCULINO"
    COORDENADOR_GENERO_FEMININO = "FEMININO"
    COORDENADOR_GENERO_CHOICES = [
        (COORDENADOR_GENERO_MASCULINO, "Masculino"),
        (COORDENADOR_GENERO_FEMININO, "Feminino"),
    ]

    numero = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    ano = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    sufixo_numero = models.CharField(max_length=20, blank=True, default="")
    data_criacao = models.DateField(default=timezone.localdate, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO)

    # Etapa 1 — identificação e atuação
    contextualizacao = models.TextField("Contextualização", blank=True, default="")
    programa = models.ForeignKey(
        ProgramaSolicitante,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planos_trabalho",
        verbose_name="Programa solicitante",
    )
    programa_outros = models.CharField("Programa (outros)", max_length=200, blank=True, default="")
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
        related_name="planos_trabalho",
        verbose_name="Cidade do destino",
    )
    data_evento_inicio = models.DateField("Data inicial do evento", null=True, blank=True)
    data_evento_fim = models.DateField("Data final do evento", null=True, blank=True)
    horario_atendimento = models.CharField(
        "Horário de atendimento",
        max_length=60,
        blank=True,
        default="09:00 até 17:00",
    )
    coordenacao = models.TextField("Coordenador do evento", blank=True, default="")
    consideracao_final = models.TextField("Considerações finais", blank=True, default="")
    # Quando True, o texto é mantido sincronizado com destino/programa (texto padrão);
    # vira False assim que o usuário edita o campo manualmente.
    contextualizacao_auto = models.BooleanField(default=True)
    coordenacao_auto = models.BooleanField(default=True)
    consideracao_auto = models.BooleanField(default=True)

    coordenador_adm_modo = models.CharField(
        max_length=10,
        choices=COORDENADOR_MODO_CHOICES,
        default=COORDENADOR_MODO_SERVIDOR,
    )
    coordenador_adm = models.ForeignKey(
        Servidor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planos_trabalho_coordenador_adm",
        verbose_name="Coordenador administrativo",
    )
    coordenador_adm_nome_manual = models.CharField(max_length=255, blank=True, default="")
    coordenador_adm_cargo_manual = models.CharField(max_length=120, blank=True, default="")
    coordenador_adm_genero = models.CharField(
        max_length=10,
        choices=COORDENADOR_GENERO_CHOICES,
        blank=True,
        default=COORDENADOR_GENERO_MASCULINO,
    )

    coordenador_op_modo = models.CharField(
        max_length=10,
        choices=COORDENADOR_MODO_CHOICES,
        default=COORDENADOR_MODO_SERVIDOR,
    )
    coordenador_op = models.ForeignKey(
        Servidor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planos_trabalho_coordenador_op",
        verbose_name="Coordenador operacional",
    )
    coordenador_op_nome_manual = models.CharField(max_length=255, blank=True, default="")
    coordenador_op_cargo_manual = models.CharField(max_length=120, blank=True, default="")
    coordenador_op_genero = models.CharField(
        max_length=10,
        choices=COORDENADOR_GENERO_CHOICES,
        blank=True,
        default=COORDENADOR_GENERO_MASCULINO,
    )

    # Etapa 2 — deslocamento e diárias (saída/chegada na sede)
    saida_sede_data = models.DateField("Data de saída da sede", null=True, blank=True)
    saida_sede_hora = models.TimeField("Hora de saída da sede", null=True, blank=True)
    chegada_sede_data = models.DateField("Data de chegada na sede", null=True, blank=True)
    chegada_sede_hora = models.TimeField("Hora de chegada na sede", null=True, blank=True)
    diarias_composicao = models.CharField(max_length=120, blank=True, default="")
    diarias_valor_unitario = models.DecimalField(
        "Valor por servidor",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    diarias_valor_total = models.DecimalField(
        "Valor total do plano",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    # Etapa 3 — atividades, metas e recursos.
    # A seleção fica em ``atividades_selecionadas``; os campos de texto abaixo são
    # regenerados a partir dela (services.sincronizar_atividades) e consumidos pelo DOCX.
    atividades_selecionadas = models.ManyToManyField(
        "AtividadePlanoTrabalho",
        blank=True,
        related_name="planos",
        verbose_name="Atividades previstas",
    )
    metas = models.TextField(blank=True, default="")
    atividades = models.TextField(blank=True, default="")
    recursos_necessarios = models.TextField(blank=True, default="")
    unidade_movel_texto = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-ano", "-numero", "-created_at"]
        verbose_name = "Plano de Trabalho"
        verbose_name_plural = "Planos de Trabalho"
        constraints = [
            models.UniqueConstraint(
                fields=["ano", "numero"],
                condition=Q(ano__isnull=False, numero__isnull=False),
                name="planos_trabalho_ano_numero_unique",
            )
        ]

    def __str__(self):
        return f"Plano de Trabalho {self.numero_formatado}"

    @property
    def numero_formatado(self) -> str:
        if self.numero and self.ano:
            base = f"{self.numero:02d}/{self.ano}"
            return f"{base}/{self.sufixo_numero}" if self.sufixo_numero else base
        return "—"

    @property
    def destino_display(self) -> str:
        destinos = list(self.destinos.select_related("cidade", "estado").order_by("ordem", "pk")) if self.pk else []
        if destinos:
            labels = [f"{destino.cidade.nome}/{destino.cidade.uf}" for destino in destinos if destino.cidade_id]
            if labels:
                return ", ".join(labels)
        if self.destino_cidade_id:
            return f"{self.destino_cidade.nome}/{self.destino_cidade.uf}"
        if self.destino_estado_id:
            return self.destino_estado.sigla
        return "Destino não informado"

    @property
    def periodo_display(self) -> str:
        inicio = self.data_evento_inicio
        fim = self.data_evento_fim or inicio
        if not inicio:
            return "Período não informado"
        if not fim or fim == inicio:
            return inicio.strftime("%d/%m/%Y")
        return f"{inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}"

    @property
    def programa_display(self) -> str:
        if self.programa_id:
            return str(self.programa)
        return self.programa_outros or ""

    @property
    def total_efetivo(self) -> int:
        if not self.pk:
            return 0
        agregado = self.efetivos.aggregate(total=models.Sum("quantidade"))
        return int(agregado["total"] or 0)

    def coordenador_nome_cargo(self, papel: str) -> tuple[str, str]:
        """Resolve (nome, cargo) do coordenador `adm` ou `op` priorizando servidor selecionado."""
        if papel == "adm":
            servidor = self.coordenador_adm if self.coordenador_adm_id else None
            nome_manual = self.coordenador_adm_nome_manual
            cargo_manual = self.coordenador_adm_cargo_manual
        else:
            servidor = self.coordenador_op if self.coordenador_op_id else None
            nome_manual = self.coordenador_op_nome_manual
            cargo_manual = self.coordenador_op_cargo_manual
        if servidor is not None:
            cargo = servidor.cargo.nome if servidor.cargo_id else ""
            return (servidor.nome or "").strip(), (cargo or "").strip()
        return (nome_manual or "").strip(), (cargo_manual or "").strip()

    def coordenador_genero(self, papel: str) -> str:
        valor = self.coordenador_adm_genero if papel == "adm" else self.coordenador_op_genero
        if valor == self.COORDENADOR_GENERO_FEMININO:
            return self.COORDENADOR_GENERO_FEMININO
        return self.COORDENADOR_GENERO_MASCULINO

    @property
    def tem_coordenador_operacional(self) -> bool:
        nome, _cargo = self.coordenador_nome_cargo("op")
        return bool(nome)

    @classmethod
    def proximo_numero(cls) -> tuple[int, int, str]:
        """Reserva o próximo número sequencial via contador na configuração.

        Retorna (numero, ano, sufixo). Usa lock pessimista no singleton para
        evitar números duplicados em requisições concorrentes.
        """
        ano_atual = timezone.localdate().year
        with transaction.atomic():
            config = (
                ConfiguracaoSistema.objects.select_for_update().filter(pk=1).first()
                or ConfiguracaoSistema.get_singleton()
            )
            if config.pt_ano != ano_atual:
                config.pt_ano = ano_atual
                config.pt_ultimo_numero = 0
            config.pt_ultimo_numero += 1
            config.save(update_fields=["pt_ano", "pt_ultimo_numero", "updated_at"])
            sufixo = (getattr(config, "pt_sufixo_numero", "") or "").strip()
            return config.pt_ultimo_numero, ano_atual, sufixo

    def atribuir_numero(self) -> None:
        if self.numero and self.ano:
            return
        numero, ano, sufixo = type(self).proximo_numero()
        self.numero = numero
        self.ano = ano
        self.sufixo_numero = sufixo

    def save(self, *args, **kwargs):
        self.programa_outros = normalize_spaces(self.programa_outros)
        self.horario_atendimento = normalize_spaces(self.horario_atendimento)
        self.coordenador_adm_nome_manual = normalize_spaces(self.coordenador_adm_nome_manual)
        self.coordenador_adm_cargo_manual = normalize_spaces(self.coordenador_adm_cargo_manual)
        self.coordenador_adm_genero = self.coordenador_genero("adm")
        self.coordenador_op_nome_manual = normalize_spaces(self.coordenador_op_nome_manual)
        self.coordenador_op_cargo_manual = normalize_spaces(self.coordenador_op_cargo_manual)
        self.coordenador_op_genero = self.coordenador_genero("op")
        super().save(*args, **kwargs)


class PlanoDestino(TimeStampedModel):
    plano = models.ForeignKey(
        PlanoTrabalho,
        on_delete=models.CASCADE,
        related_name="destinos",
        verbose_name="Plano de trabalho",
    )
    estado = models.ForeignKey(
        Estado,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="UF do destino",
    )
    cidade = models.ForeignKey(
        Cidade,
        on_delete=models.PROTECT,
        related_name="planos_trabalho_destinos",
        verbose_name="Cidade do destino",
    )
    ordem = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["ordem", "pk"]
        verbose_name = "Destino do plano de trabalho"
        verbose_name_plural = "Destinos do plano de trabalho"


class EfetivoPlano(TimeStampedModel):
    """Composição do efetivo do plano por cargo e quantidade."""

    plano = models.ForeignKey(
        PlanoTrabalho,
        on_delete=models.CASCADE,
        related_name="efetivos",
        verbose_name="Plano de trabalho",
    )
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="efetivos_plano_trabalho",
        verbose_name="Unidade",
    )
    cargo = models.ForeignKey(
        Cargo,
        on_delete=models.PROTECT,
        related_name="efetivos_plano_trabalho",
        verbose_name="Cargo",
    )
    quantidade = models.PositiveIntegerField("Quantidade", default=1)

    class Meta:
        ordering = ["plano", "unidade__nome", "cargo__nome"]
        verbose_name = "Efetivo do plano de trabalho"
        verbose_name_plural = "Efetivos do plano de trabalho"
        constraints = [
            models.UniqueConstraint(
                fields=["plano", "unidade", "cargo"],
                name="planos_trabalho_efetivo_plano_unidade_cargo_unique",
            )
        ]

    def __str__(self):
        unidade = f" / {self.unidade}" if self.unidade_id else ""
        return f"{self.plano_id}: {self.quantidade} x {self.cargo}{unidade}"
