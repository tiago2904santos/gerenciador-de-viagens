from __future__ import annotations

from django.db import models
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from core.constraints import nao_negativo
from core.constraints import periodo_ordenado
from core.managers import AreaScopedManager

from cadastros.models import Cargo
from core.models import CancelavelModel
from cadastros.models import Cidade
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Estado
from cadastros.models import Servidor
from core.models import TimeStampedModel
from cadastros.models import Unidade
from core.normalizers import normalize_spaces
from core.normalizers import normalize_upper
from core.tenancy import get_current_area


class ProgramaSolicitante(TimeStampedModel):
    """Programa/iniciativa que solicita a ação (ex.: Justiça no Bairro)."""

    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="programas_solicitantes",
        verbose_name="Area de trabalho",
    )
    nome = models.CharField(max_length=200)
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=100)

    # `BE-09`: `objects` recorta pela área ativa; `all_objects` é a saída explícita
    # para código que precisa enxergar todas. `default_manager_name` mantém o admin,
    # as relações reversas e `validate_unique` irrestritos — ver `core/managers.py`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["ordem", "nome"]
        verbose_name = "Programa solicitante"
        verbose_name_plural = "Programas solicitantes"
        indexes = [
            models.Index(fields=["area", "ordem", "nome"], name="planos_prog_area_ordem_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["nome"], condition=Q(area__isnull=True), name="planos_programa_nome_global_unique"),
            models.UniqueConstraint(fields=["area", "nome"], condition=Q(area__isnull=False), name="planos_programa_area_nome_unique"),
        ]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.nome = normalize_upper(self.nome)
        super().save(*args, **kwargs)


class HorarioAtendimento(TimeStampedModel):
    """Faixa de horário disponível para seleção nos planos de trabalho."""

    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="horarios_atendimento",
        verbose_name="Area de trabalho",
    )
    faixa = models.CharField(max_length=60)
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=100)

    # `BE-09`: ver `core/managers.py`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["ordem", "faixa"]
        indexes = [
            models.Index(fields=["area", "ordem", "faixa"], name="planos_horario_area_ordem_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["faixa"], condition=Q(area__isnull=True), name="planos_horario_faixa_global_unique"),
            models.UniqueConstraint(fields=["area", "faixa"], condition=Q(area__isnull=False), name="planos_horario_area_faixa_unique"),
        ]
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

    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="atividades_plano_trabalho",
        verbose_name="Area de trabalho",
    )
    codigo = models.CharField("Código", max_length=40)
    nome = models.CharField("Nome", max_length=255)
    meta = models.TextField("Meta")
    recurso_necessario = models.TextField("Recurso necessário", blank=True, default="")
    ordem = models.PositiveIntegerField("Ordem", default=100)
    ativo = models.BooleanField("Ativo", default=True)

    # `BE-09`: ver `core/managers.py`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["ordem", "nome"]
        indexes = [
            models.Index(fields=["area", "ordem", "nome"], name="planos_ativ_area_ordem_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["codigo"], condition=Q(area__isnull=True), name="planos_atividade_codigo_global_unique"),
            models.UniqueConstraint(fields=["area", "codigo"], condition=Q(area__isnull=False), name="planos_atividade_area_codigo_unique"),
        ]
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


class PresetAtividadesPlanoTrabalho(TimeStampedModel):
    """Conjunto reutilizável de atividades para aplicar na etapa 3 do wizard.

    Presets são globais por área (não ligados a programa). Ao aplicar no wizard,
    a seleção atual é substituída pelos códigos do preset; o usuário pode
    ajustar livremente depois. Planos não guardam vínculo com o preset.
    """

    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="presets_atividades_plano_trabalho",
        verbose_name="Area de trabalho",
    )
    nome = models.CharField("Nome", max_length=200)
    descricao = models.CharField("Descrição", max_length=255, blank=True, default="")
    ordem = models.PositiveIntegerField("Ordem", default=100)
    ativo = models.BooleanField("Ativo", default=True)
    is_padrao = models.BooleanField("Padrão", default=False)
    atividades = models.ManyToManyField(
        AtividadePlanoTrabalho,
        blank=True,
        related_name="presets",
        verbose_name="Atividades",
    )

    # `BE-09`: ver `core/managers.py`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["ordem", "nome"]
        verbose_name = "Preset de atividades"
        verbose_name_plural = "Presets de atividades"
        indexes = [
            models.Index(fields=["area", "ordem", "nome"], name="planos_preset_area_ordem_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["nome"],
                condition=Q(area__isnull=True),
                name="planos_preset_nome_global_unique",
            ),
            models.UniqueConstraint(
                fields=["area", "nome"],
                condition=Q(area__isnull=False),
                name="planos_preset_area_nome_unique",
            ),
            models.UniqueConstraint(
                fields=["area"],
                condition=Q(area__isnull=False) & Q(is_padrao=True),
                name="planos_preset_area_padrao_unique",
            ),
            models.UniqueConstraint(
                fields=["is_padrao"],
                condition=Q(area__isnull=True) & Q(is_padrao=True),
                name="planos_preset_global_padrao_unique",
            ),
        ]

    def __str__(self):
        return self.nome

    @transaction.atomic
    def save(self, *args, **kwargs):
        self.nome = normalize_upper(self.nome)
        self.descricao = normalize_spaces(self.descricao)
        if self.is_padrao:
            # `BE-09`: `all_objects` — o escopo é o `self.area` deste registro, na
            # linha de baixo, e não o do request. Recortado, o padrão anterior não
            # seria rebaixado e a gravação estouraria na `UniqueConstraint` de padrão
            # único por área.
            PresetAtividadesPlanoTrabalho.all_objects.select_for_update().exclude(
                pk=self.pk,
            ).filter(
                area=self.area,
                is_padrao=True,
            ).update(is_padrao=False)
        super().save(*args, **kwargs)


class PlanoTrabalho(TimeStampedModel, CancelavelModel):
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

    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="planos_trabalho",
        verbose_name="Area de trabalho",
    )
    numero = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    ano = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    sufixo_numero = models.CharField(max_length=20, blank=True, default="")
    data_criacao = models.DateField(default=timezone.localdate, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO)
    evento = models.ForeignKey(
        "eventos.Evento",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="planos_trabalho",
    )

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

    # Multi-evento (modelo "scratchpad"): as etapas 1–3 sempre editam os campos
    # plano-level acima (o "rascunho do evento atual"). Ao "Adicionar evento ao
    # plano" na etapa 4, esse rascunho é commitado para um ``EventoPlano`` e os
    # campos de evento são limpos para o próximo. ``is_multi_evento`` vira True no
    # primeiro commit. Default False mantém o fluxo single-event sem regressão.
    is_multi_evento = models.BooleanField(default=False)
    # Quando setado, o rascunho atual representa a edição de um evento já commitado
    # (clicou "Editar" no card). Em branco = rascunho de um evento novo.
    evento_em_edicao = models.ForeignKey(
        "EventoPlano",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
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
    # Multi-evento: cálculo do trajeto sede → todos eventos → sede.
    diarias_combinada_composicao = models.CharField(max_length=120, blank=True, default="")
    diarias_combinada_valor_unitario = models.DecimalField(
        "Valor por servidor (combinado)",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    diarias_combinada_valor_total = models.DecimalField(
        "Valor total do plano (combinado)",
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

    # `BE-09`: ver `core/managers.py`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["-ano", "-numero", "-created_at"]
        verbose_name = "Plano de Trabalho"
        verbose_name_plural = "Planos de Trabalho"
        indexes = [
            models.Index(fields=["area", "-ano", "-numero"], name="planos_area_numero_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["ano", "numero"],
                condition=Q(area__isnull=True, ano__isnull=False, numero__isnull=False),
                name="planos_trabalho_ano_numero_global_unique",
            ),
            models.UniqueConstraint(
                fields=["area", "ano", "numero"],
                condition=Q(area__isnull=False, ano__isnull=False, numero__isnull=False),
                name="planos_trabalho_area_ano_numero_unique",
            ),
            # `DB-07`. Os quatro valores abaixo são **calculados** e gravados —
            # unitário × quantidade, e a variante combinada. Zero é legítimo
            # (plano sem diária); negativo só sai de conta errada, e daqui viaja
            # direto para o documento do plano.
            periodo_ordenado(
                "data_evento_inicio", "data_evento_fim", name="plano_periodo_ordenado",
            ),
            nao_negativo("diarias_valor_unitario", name="plano_diaria_unitaria_nao_negativa"),
            nao_negativo("diarias_valor_total", name="plano_diaria_total_nao_negativa"),
            nao_negativo(
                "diarias_combinada_valor_unitario",
                name="plano_diaria_comb_unitaria_nao_negativa",
            ),
            nao_negativo(
                "diarias_combinada_valor_total", name="plano_diaria_comb_total_nao_negativa",
            ),
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
        prefetched = getattr(self, "_prefetched_objects_cache", {}).get("destinos")
        if prefetched is not None:
            destinos = sorted(
                (destino for destino in prefetched if destino.evento_id is None),
                key=lambda destino: (destino.ordem, destino.pk),
            )
        else:
            destinos = (
                list(
                    self.destinos.filter(evento__isnull=True)
                    .select_related("cidade", "estado")
                    .order_by("ordem", "pk")
                )
                if self.pk
                else []
            )
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
        """Efetivo do rascunho atual (linhas EfetivoPlano). Em multi, é o evento em edição."""
        if not self.pk:
            return 0
        prefetched = getattr(self, "_prefetched_objects_cache", {}).get("efetivos")
        if prefetched is not None:
            return sum(int(item.quantidade or 0) for item in prefetched)
        agregado = self.efetivos.aggregate(total=models.Sum("quantidade"))
        return int(agregado["total"] or 0)

    @property
    def total_efetivo_combinado(self) -> int:
        """Maior efetivo entre eventos commitados (divisor da diária combinada).

        A mesma equipe viaja para todos os eventos — premissa do cálculo combinado.
        """
        if not self.pk or not self.is_multi_evento:
            return self.total_efetivo
        totais = [e.total_efetivo for e in self.eventos.all()]
        return max(totais) if totais else 0

    @property
    def eventos_ordenados(self):
        if not self.pk:
            return []
        return list(self.eventos.order_by("ordem", "data_evento_inicio", "pk"))

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
    def proximo_numero(cls, area=None) -> tuple[int, int, str]:
        """Reserva o próximo número sequencial via contador na configuração.

        Retorna (numero, ano, sufixo). Usa lock pessimista no singleton para
        evitar números duplicados em requisições concorrentes.
        """
        ano_atual = timezone.localdate().year
        area = get_current_area() if area is None else area
        with transaction.atomic():
            config = (
                # `BE-09`: `all_objects` nos dois ramos. O escopo é a `area` recebida no
                # argumento — `proximo_numero(self.area)`, a área do **plano**, não a
                # ativa. Recortado, o `SELECT ... FOR UPDATE` não acha a linha, cai no
                # `get_for_area` abaixo e emite número a partir de outro contador:
                # plano de trabalho duplicado, sem erro nenhum.
                ConfiguracaoSistema.all_objects.select_for_update().filter(area=area).order_by("pk").first()
                if area is not None
                else ConfiguracaoSistema.all_objects.select_for_update()
                .filter(area__isnull=True)
                .order_by("pk")
                .first()
            )
            if config is None:
                config = ConfiguracaoSistema.get_for_area(area)
            if config.pt_ano != ano_atual:
                config.pt_ano = ano_atual
                config.pt_ultimo_numero = 0
            # `BE-09`: `all_objects` — o escopo é a `area` do argumento, aplicado nas
            # quatro linhas abaixo. Recortar de novo pela área ativa esvaziaria a
            # agregação e o `max(contador, banco)` perderia o piso real, podendo
            # reemitir número já usado.
            planos = cls.all_objects.filter(ano=ano_atual)
            if area is None:
                planos = planos.filter(area__isnull=True)
            else:
                planos = planos.filter(area=area)
            ultimo_numero_banco = planos.aggregate(ultimo=models.Max("numero")).get("ultimo") or 0
            config.pt_ultimo_numero = max(config.pt_ultimo_numero, ultimo_numero_banco) + 1
            config.save(update_fields=["pt_ano", "pt_ultimo_numero", "updated_at"])
            sufixo = (getattr(config, "pt_sufixo_numero", "") or "").strip()
            return config.pt_ultimo_numero, ano_atual, sufixo

    def atribuir_numero(self) -> None:
        if self.numero and self.ano:
            return
        numero, ano, sufixo = type(self).proximo_numero(self.area)
        self.numero = numero
        self.ano = ano
        self.sufixo_numero = sufixo

    def save(self, *args, **kwargs):
        if self.area_id is None:
            if self.evento_id and self.evento and self.evento.area_id:
                self.area = self.evento.area
            else:
                self.area = get_current_area()
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
    # Quando setado, o destino pertence a um evento específico (modo multi).
    # Quando null, o destino é do plano (modo single — comportamento atual).
    evento = models.ForeignKey(
        "EventoPlano",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="destinos",
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


class EventoPlano(TimeStampedModel):
    """Evento que compõe um plano de trabalho.

    No modo single-event (``PlanoTrabalho.is_multi_evento=False``) este modelo não é usado —
    todos os dados ficam diretamente no plano. No modo multi-evento, cada evento carrega seu
    próprio programa, datas, horário, atividades e efetivo; metas/recursos/atividades-texto
    são re-sincronizados a partir de ``atividades_selecionadas``.
    """

    plano = models.ForeignKey(
        PlanoTrabalho,
        on_delete=models.CASCADE,
        related_name="eventos",
        verbose_name="Plano de trabalho",
    )
    ordem = models.PositiveIntegerField(default=1)

    programa = models.ForeignKey(
        ProgramaSolicitante,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eventos_plano_trabalho",
        verbose_name="Programa solicitante",
    )
    programa_outros = models.CharField("Programa (outros)", max_length=200, blank=True, default="")

    data_evento_inicio = models.DateField("Data inicial do evento", null=True, blank=True)
    data_evento_fim = models.DateField("Data final do evento", null=True, blank=True)
    horario_atendimento = models.CharField(
        "Horário de atendimento",
        max_length=60,
        blank=True,
        default="09:00 até 17:00",
    )

    # Coordenador operacional — varia por evento (o administrativo é plano-level).
    coordenador_op_modo = models.CharField(
        max_length=10,
        choices=PlanoTrabalho.COORDENADOR_MODO_CHOICES,
        default=PlanoTrabalho.COORDENADOR_MODO_SERVIDOR,
    )
    coordenador_op = models.ForeignKey(
        Servidor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eventos_plano_coordenador_op",
        verbose_name="Coordenador operacional",
    )
    coordenador_op_nome_manual = models.CharField(max_length=255, blank=True, default="")
    coordenador_op_cargo_manual = models.CharField(max_length=120, blank=True, default="")
    coordenador_op_genero = models.CharField(
        max_length=10,
        choices=PlanoTrabalho.COORDENADOR_GENERO_CHOICES,
        blank=True,
        default=PlanoTrabalho.COORDENADOR_GENERO_MASCULINO,
    )

    atividades_selecionadas = models.ManyToManyField(
        AtividadePlanoTrabalho,
        blank=True,
        related_name="eventos",
        verbose_name="Atividades previstas",
    )
    metas = models.TextField(blank=True, default="")
    atividades_texto = models.TextField(blank=True, default="")
    recursos_necessarios = models.TextField(blank=True, default="")
    unidade_movel_texto = models.TextField(blank=True, default="")

    # Snapshot da diária individual (sede → este evento → sede).
    diarias_composicao = models.CharField(max_length=120, blank=True, default="")
    diarias_valor_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    diarias_valor_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["ordem", "data_evento_inicio", "pk"]
        verbose_name = "Evento do plano de trabalho"
        verbose_name_plural = "Eventos do plano de trabalho"
        constraints = [
            # `DB-07`: no modo multi-evento é **aqui** que mora o período de cada
            # evento, e a `Meta.ordering` ordena por `data_evento_inicio` — data
            # invertida embaralha a sequência impressa no plano.
            periodo_ordenado(
                "data_evento_inicio", "data_evento_fim", name="evento_plano_periodo_ordenado",
            ),
            nao_negativo(
                "diarias_valor_unitario", name="evento_plano_diaria_unitaria_nao_negativa",
            ),
            nao_negativo("diarias_valor_total", name="evento_plano_diaria_total_nao_negativa"),
        ]

    def __str__(self):
        if self.data_evento_inicio:
            return f"Evento {self.ordem} ({self.data_evento_inicio:%d/%m/%Y})"
        return f"Evento {self.ordem}"

    @property
    def total_efetivo(self) -> int:
        if not self.pk:
            return 0
        prefetched = getattr(self, "_prefetched_objects_cache", {}).get("efetivos")
        if prefetched is not None:
            return sum(int(item.quantidade or 0) for item in prefetched)
        agregado = self.efetivos.aggregate(total=models.Sum("quantidade"))
        return int(agregado["total"] or 0)

    @property
    def destino_principal(self):
        if not self.pk:
            return None
        return self.destinos.select_related("cidade").order_by("ordem", "pk").first()

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
    def destino_display(self) -> str:
        destinos = list(self.destinos.select_related("cidade").order_by("ordem", "pk")) if self.pk else []
        labels = [f"{d.cidade.nome}/{d.cidade.uf}" for d in destinos if d.cidade_id]
        return ", ".join(labels) if labels else "Destino não informado"

    def coordenador_nome_cargo(self) -> tuple[str, str]:
        """Resolve (nome, cargo) do coordenador operacional do evento."""
        if self.coordenador_op_id:
            servidor = self.coordenador_op
            cargo = servidor.cargo.nome if servidor.cargo_id else ""
            return (servidor.nome or "").strip(), (cargo or "").strip()
        return (self.coordenador_op_nome_manual or "").strip(), (self.coordenador_op_cargo_manual or "").strip()

    def coordenador_genero(self) -> str:
        if self.coordenador_op_genero == PlanoTrabalho.COORDENADOR_GENERO_FEMININO:
            return PlanoTrabalho.COORDENADOR_GENERO_FEMININO
        return PlanoTrabalho.COORDENADOR_GENERO_MASCULINO

    def save(self, *args, **kwargs):
        self.programa_outros = normalize_spaces(self.programa_outros)
        self.horario_atendimento = normalize_spaces(self.horario_atendimento)
        self.coordenador_op_nome_manual = normalize_spaces(self.coordenador_op_nome_manual)
        self.coordenador_op_cargo_manual = normalize_spaces(self.coordenador_op_cargo_manual)
        self.coordenador_op_genero = self.coordenador_genero()
        super().save(*args, **kwargs)


class EfetivoEvento(TimeStampedModel):
    """Composição do efetivo de um evento (modo multi-evento)."""

    evento = models.ForeignKey(
        EventoPlano,
        on_delete=models.CASCADE,
        related_name="efetivos",
        verbose_name="Evento",
    )
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="efetivos_evento_plano_trabalho",
        verbose_name="Unidade",
    )
    cargo = models.ForeignKey(
        Cargo,
        on_delete=models.PROTECT,
        related_name="efetivos_evento_plano_trabalho",
        verbose_name="Cargo",
    )
    quantidade = models.PositiveIntegerField("Quantidade", default=1)

    class Meta:
        ordering = ["evento", "unidade__nome", "cargo__nome"]
        verbose_name = "Efetivo do evento"
        verbose_name_plural = "Efetivos do evento"
        constraints = [
            models.UniqueConstraint(
                fields=["evento", "unidade", "cargo"],
                name="planos_trabalho_efetivo_evento_unidade_cargo_unique",
            )
        ]

    def __str__(self):
        unidade = f" / {self.unidade}" if self.unidade_id else ""
        return f"{self.evento_id}: {self.quantidade} x {self.cargo}{unidade}"
