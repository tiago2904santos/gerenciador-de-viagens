import re
from decimal import ROUND_HALF_UP, Decimal

from django.db import models, transaction
from django.db.models import Q, UniqueConstraint

from core.managers import AreaScopedManager
from core.normalizers import normalize_digits
from core.normalizers import normalize_plate
from core.normalizers import normalize_upper
from core.models import TimeStampedModel
from core.utils.masks import RG_NAO_POSSUI_CANONICAL, format_masked_display, format_placa


class Unidade(TimeStampedModel):
    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="unidades",
        verbose_name="Area de trabalho",
    )
    nome = models.CharField(max_length=255)
    sigla = models.CharField(max_length=50, blank=True)

    # `BE-09`: `objects` recorta pela área ativa; `all_objects` é a saída explícita
    # para código que precisa enxergar todas. `default_manager_name` mantém o admin,
    # as relações reversas e `validate_unique` irrestritos — ver `core/managers.py`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["nome"]
        verbose_name = "Unidade"
        verbose_name_plural = "Unidades"
        indexes = [
            models.Index(fields=["area", "nome"], name="cadastros_unid_area_nome_idx"),
        ]
        constraints = [
            UniqueConstraint(
                fields=["nome"],
                condition=Q(area__isnull=True),
                name="cadastros_unidade_nome_global_unique",
            ),
            UniqueConstraint(
                fields=["area", "nome"],
                condition=Q(area__isnull=False),
                name="cadastros_unidade_area_nome_unique",
            ),
        ]

    def __str__(self):
        return self.sigla or self.nome

    def save(self, *args, **kwargs):
        self.nome = normalize_upper(self.nome)
        self.sigla = normalize_upper(self.sigla)
        super().save(*args, **kwargs)


class Estado(TimeStampedModel):
    nome = models.CharField(max_length=128)
    sigla = models.CharField(max_length=2, unique=True)
    codigo_ibge = models.PositiveSmallIntegerField(null=True, blank=True, unique=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Estado"
        verbose_name_plural = "Estados"
        constraints = [
            models.UniqueConstraint(fields=["nome"], name="unique_estado_nome"),
        ]

    def __str__(self):
        return f"{self.nome} ({self.sigla})"

    def save(self, *args, **kwargs):
        self.nome = normalize_upper(self.nome)
        self.sigla = (self.sigla or "").strip().upper()[:2]
        super().save(*args, **kwargs)


class Cidade(TimeStampedModel):
    estado = models.ForeignKey(Estado, on_delete=models.PROTECT, related_name="cidades")
    nome = models.CharField(max_length=255)
    uf = models.CharField(max_length=2)
    codigo_ibge = models.PositiveIntegerField(null=True, blank=True)
    capital = models.BooleanField(default=False)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    class Meta:
        ordering = ["estado__sigla", "nome"]
        verbose_name = "Cidade"
        verbose_name_plural = "Cidades"
        constraints = [
            models.UniqueConstraint(fields=["nome", "estado"], name="unique_cidade_nome_estado"),
            models.UniqueConstraint(
                fields=["codigo_ibge"],
                name="unique_cidade_codigo_ibge_nn",
                condition=models.Q(codigo_ibge__isnull=False),
            ),
        ]

    def __str__(self):
        return f"{self.nome}/{self.uf}"

    def save(self, *args, **kwargs):
        self.nome = normalize_upper(self.nome)
        if self.estado_id:
            self.uf = self.estado.sigla
        else:
            self.uf = (self.uf or "").strip().upper()[:2]
        super().save(*args, **kwargs)


class Cargo(TimeStampedModel):
    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cargos",
        verbose_name="Area de trabalho",
    )
    nome = models.CharField(max_length=120)
    is_padrao = models.BooleanField(default=False)

    # `BE-09`: ver `core/managers.py`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["nome"]
        verbose_name = "Cargo"
        verbose_name_plural = "Cargos"
        indexes = [
            models.Index(fields=["area", "nome"], name="cadastros_cargo_area_nome_idx"),
        ]
        constraints = [
            UniqueConstraint(
                fields=["nome"],
                condition=Q(area__isnull=True),
                name="cadastros_cargo_nome_global_unique",
            ),
            UniqueConstraint(
                fields=["area", "nome"],
                condition=Q(area__isnull=False),
                name="cadastros_cargo_area_nome_unique",
            ),
            UniqueConstraint(
                fields=["area"],
                condition=Q(area__isnull=False) & Q(is_padrao=True),
                name="cadastros_cargo_area_padrao_unique",
            ),
            UniqueConstraint(
                fields=["is_padrao"],
                condition=Q(area__isnull=True) & Q(is_padrao=True),
                name="cadastros_cargo_global_padrao_unique",
            ),
        ]

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.nome:
            self.nome = normalize_upper(self.nome)
        if self.is_padrao:
            # `BE-09`: `all_objects` porque o escopo é o `self.area` deste registro,
            # na linha de baixo, e não o do request. `save()` roda também fora de
            # request e com área diferente da ativa; recortado, o padrão anterior
            # não seria rebaixado e a gravação estouraria em
            # `cadastros_cargo_area_padrao_unique`.
            Cargo.all_objects.select_for_update().exclude(pk=self.pk).filter(
                area=self.area,
                is_padrao=True,
            ).update(is_padrao=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class Combustivel(TimeStampedModel):
    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="combustiveis",
        verbose_name="Area de trabalho",
    )
    nome = models.CharField(max_length=120)
    is_padrao = models.BooleanField(default=False)

    # `BE-09`: ver `core/managers.py`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["nome"]
        verbose_name = "Combustível"
        verbose_name_plural = "Combustíveis"
        indexes = [
            models.Index(fields=["area", "nome"], name="cadastros_comb_area_nome_idx"),
        ]
        constraints = [
            UniqueConstraint(
                fields=["nome"],
                condition=Q(area__isnull=True),
                name="cadastros_combustivel_nome_global_unique",
            ),
            UniqueConstraint(
                fields=["area", "nome"],
                condition=Q(area__isnull=False),
                name="cadastros_combustivel_area_nome_unique",
            ),
            UniqueConstraint(
                fields=["area"],
                condition=Q(area__isnull=False) & Q(is_padrao=True),
                name="cadastros_combustivel_area_padrao_unique",
            ),
            UniqueConstraint(
                fields=["is_padrao"],
                condition=Q(area__isnull=True) & Q(is_padrao=True),
                name="cadastros_combustivel_global_padrao_unique",
            ),
        ]

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.nome:
            self.nome = normalize_upper(self.nome)
        if self.is_padrao:
            # `BE-09`: `all_objects` porque o escopo é o `self.area` deste registro,
            # na linha de baixo, e não o do request. `save()` roda também fora de
            # request e com área diferente da ativa; recortado, o padrão anterior
            # não seria rebaixado e a gravação estouraria em
            # `cadastros_combustivel_area_padrao_unique`.
            Combustivel.all_objects.select_for_update().exclude(pk=self.pk).filter(
                area=self.area,
                is_padrao=True,
            ).update(is_padrao=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class Servidor(TimeStampedModel):
    STATUS_RASCUNHO = "RASCUNHO"
    STATUS_COMPLETO = "COMPLETO"
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, "Rascunho"),
        (STATUS_COMPLETO, "Completo"),
    ]

    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="servidores",
        verbose_name="Area de trabalho",
    )
    nome = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO)
    cargo = models.ForeignKey(
        Cargo,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="servidores",
    )
    cpf = models.CharField(max_length=11, blank=True, default="")
    rg = models.CharField(max_length=30, blank=True, default="")
    sem_rg = models.BooleanField(default=False)
    telefone = models.CharField(max_length=11, blank=True, default="")
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="servidores",
    )

    # `BE-09`: ver `core/managers.py`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["nome"]
        verbose_name = "Servidor"
        verbose_name_plural = "Servidores"
        indexes = [
            models.Index(fields=["area", "nome"], name="cadastros_srv_area_nome_idx"),
        ]
        constraints = [
            UniqueConstraint(
                fields=["nome"],
                condition=Q(area__isnull=True),
                name="cadastros_servidor_nome_global_unique",
            ),
            UniqueConstraint(
                fields=["area", "nome"],
                condition=Q(area__isnull=False),
                name="cadastros_servidor_area_nome_unique",
            ),
            UniqueConstraint(
                fields=["cpf"],
                condition=Q(area__isnull=True) & Q(cpf__gt=""),
                name="cadastros_servidor_cpf_global_unique",
            ),
            UniqueConstraint(
                fields=["area", "cpf"],
                condition=Q(area__isnull=False) & Q(cpf__gt=""),
                name="cadastros_servidor_area_cpf_unique",
            ),
            UniqueConstraint(
                fields=["rg"],
                condition=Q(area__isnull=True) & Q(rg__gt="") & ~Q(rg=RG_NAO_POSSUI_CANONICAL),
                name="cadastros_servidor_rg_global_unique",
            ),
            UniqueConstraint(
                fields=["area", "rg"],
                condition=Q(area__isnull=False) & Q(rg__gt="") & ~Q(rg=RG_NAO_POSSUI_CANONICAL),
                name="cadastros_servidor_area_rg_unique",
            ),
            UniqueConstraint(
                fields=["telefone"],
                condition=Q(area__isnull=True) & Q(telefone__gt=""),
                name="cadastros_servidor_telefone_global_unique",
            ),
            UniqueConstraint(
                fields=["area", "telefone"],
                condition=Q(area__isnull=False) & Q(telefone__gt=""),
                name="cadastros_servidor_area_telefone_unique",
            ),
        ]

    def __str__(self):
        return self.nome

    @property
    def cpf_formatado(self):
        return format_masked_display("cpf", self.cpf)

    @property
    def rg_formatado(self):
        if self.sem_rg:
            return format_masked_display("rg", RG_NAO_POSSUI_CANONICAL)
        return format_masked_display("rg", self.rg)

    @property
    def telefone_formatado(self):
        return format_masked_display("telefone", self.telefone)

    def esta_completo(self) -> bool:
        """Útil para fluxos futuros; não bloqueia CRUD."""
        if not (self.nome or "").strip():
            return False
        if not self.cargo_id:
            return False
        cpf = (self.cpf or "").strip()
        if len(cpf) != 11 or not cpf.isdigit():
            return False
        if self.sem_rg:
            return True
        rg = (self.rg or "").strip()
        return bool(rg and rg != RG_NAO_POSSUI_CANONICAL)

    def save(self, *args, **kwargs):
        self.nome = normalize_upper(self.nome)
        self.cpf = normalize_digits(self.cpf)
        self.sem_rg = not (self.rg or "").strip() or (self.rg or "").strip().upper() == RG_NAO_POSSUI_CANONICAL
        if self.sem_rg:
            self.rg = RG_NAO_POSSUI_CANONICAL
        else:
            self.rg = "".join(c for c in (self.rg or "").upper() if c.isalnum())
        self.telefone = normalize_digits(self.telefone)
        self.status = self.STATUS_COMPLETO if self.esta_completo() else self.STATUS_RASCUNHO
        super().save(*args, **kwargs)


class Viatura(TimeStampedModel):
    STATUS_RASCUNHO = "RASCUNHO"
    STATUS_COMPLETO = "COMPLETO"
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, "Rascunho"),
        (STATUS_COMPLETO, "Completo"),
    ]

    TIPO_CARACTERIZADA = "CARACTERIZADA"
    TIPO_DESCARACTERIZADA = "DESCARACTERIZADA"
    TIPO_CHOICES = [
        (TIPO_CARACTERIZADA, "Caracterizada"),
        (TIPO_DESCARACTERIZADA, "Descaracterizada"),
    ]

    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="viaturas",
        verbose_name="Area de trabalho",
    )
    # `DB-05`: era `unique=True` — placa unica no sistema inteiro. A area B nao
    # conseguia cadastrar viatura cuja placa a area A ja tivesse, sem enxergar
    # nem poder usar a viatura dela. A unicidade agora e por area, nas
    # constraints do `Meta`.
    placa = models.CharField(max_length=7)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO)
    modelo = models.CharField(max_length=120, blank=True)
    combustivel = models.ForeignKey(
        Combustivel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="viaturas",
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, blank=True, default="")
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="viaturas",
        verbose_name="Unidade",
    )
    motoristas = models.ManyToManyField(
        Servidor,
        blank=True,
        related_name="viaturas_que_dirige",
        verbose_name="Motoristas",
    )

    # `BE-09`: ver `core/managers.py`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["placa"]
        verbose_name = "Viatura"
        verbose_name_plural = "Viaturas"
        indexes = [
            models.Index(fields=["area", "placa"], name="cadastros_viat_area_placa_idx"),
        ]
        # `DB-05`, espelhando `justificativas/models.py:47-57` (`NOVO-09`).
        #
        # Sao **duas** constraints e nao um `unique_together`, porque `area` e
        # anulavel e em SQL `NULL != NULL`: um `unique(area, placa)` puro
        # deixaria passar duas linhas globais com a mesma placa, sem erro
        # nenhum. A condicional cobre os dois casos separadamente.
        constraints = [
            models.UniqueConstraint(
                fields=["placa"],
                condition=Q(area__isnull=True),
                name="viatura_placa_global_unique",
            ),
            models.UniqueConstraint(
                fields=["area", "placa"],
                condition=Q(area__isnull=False),
                name="viatura_area_placa_unique",
            ),
        ]

    def __str__(self):
        return self.placa

    @property
    def placa_formatada(self):
        return format_placa(self.placa)

    def _placa_valida(self) -> bool:
        p = (self.placa or "").strip()
        if not p or len(p) != 7:
            return False
        return bool(
            re.match(r"^[A-Z]{3}[0-9]{4}$", p) or re.match(r"^[A-Z]{3}[0-9][A-Z][0-9]{2}$", p)
        )

    def esta_completo(self) -> bool:
        if not self._placa_valida():
            return False
        if not (self.modelo or "").strip():
            return False
        if not self.combustivel_id:
            return False
        return bool((self.tipo or "").strip())

    def save(self, *args, **kwargs):
        self.placa = normalize_plate(self.placa)
        self.modelo = normalize_upper(self.modelo)
        self.tipo = (self.tipo or "").strip().upper()
        self.status = self.STATUS_COMPLETO if self.esta_completo() else self.STATUS_RASCUNHO
        super().save(*args, **kwargs)


class ConfiguracaoSistema(TimeStampedModel):
    """Dados institucionais para documentos e regras da area atual."""

    area = models.OneToOneField(
        "usuarios.AreaTrabalho",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="configuracao_sistema",
        verbose_name="Area de trabalho",
    )
    cidade_sede_padrao = models.ForeignKey(
        Cidade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Cidade sede padrão",
    )
    prazo_justificativa_dias = models.PositiveIntegerField(default=10)
    nome_orgao = models.CharField(max_length=200, blank=True)
    sigla_orgao = models.CharField(max_length=20, blank=True)
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Unidade",
    )
    cep = models.CharField(max_length=9, blank=True, default="")
    logradouro = models.CharField(max_length=160, blank=True, default="")
    bairro = models.CharField(max_length=120, blank=True, default="")
    cidade_endereco = models.CharField(max_length=120, blank=True, default="")
    uf = models.CharField(max_length=2, blank=True, default="")
    numero = models.CharField(max_length=20, blank=True, default="")
    telefone = models.CharField(max_length=20, blank=True, default="")
    ramal = models.CharField(max_length=20, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    sede = models.CharField(max_length=200, blank=True, default="")
    nome_chefia = models.CharField(max_length=120, blank=True, default="")
    cargo_chefia = models.CharField(max_length=120, blank=True, default="")
    coordenador_adm_plano_trabalho = models.ForeignKey(
        Servidor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Coordenador administrativo padrão (Plano de Trabalho)",
    )
    destinatario_oficio = models.ForeignKey(
        Servidor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Destinatário padrão do Ofício",
        help_text="A unidade lotada deste servidor vira o DESTINO do cabeçalho do Ofício.",
    )
    destinatario_oficio_nome = models.CharField(max_length=255, blank=True, default="")
    destinatario_oficio_cargo = models.CharField(max_length=120, blank=True, default="")
    destinatario_oficio_unidade = models.CharField(max_length=255, blank=True, default="")
    pt_ultimo_numero = models.PositiveIntegerField(default=0)
    pt_ano = models.PositiveIntegerField(default=0)
    pt_sufixo_numero = models.CharField(
        max_length=20,
        blank=True,
        default="ASCOM",
        verbose_name="Sufixo do número (Plano de Trabalho)",
        help_text="Sufixo aplicado à numeração do plano (ex.: 20/2026/ASCOM).",
    )

    class Meta:
        verbose_name = "Configuração do sistema"
        verbose_name_plural = "Configurações do sistema"

    def __str__(self):
        return "Configurações do sistema"

    @property
    def cep_formatado(self):
        return format_masked_display("cep", self.cep)

    @property
    def telefone_formatado(self):
        return format_masked_display("telefone", self.telefone)

    @classmethod
    def get_singleton(cls):
        """Compatibilidade para chamadas antigas sem criar configuração sem área.

        Em uma requisição normal, o middleware mantém a área corrente no
        contexto e a configuração correta é resolvida por ela. Sem esse
        contexto, uma configuração legada ainda pode ser lida durante a
        migração. Depois do saneamento, instalações de área única usam essa
        área e instalações sem contexto inequívoco usam uma área técnica
        inativa; ``area=NULL`` nunca é recriado.
        """
        from core.tenancy import get_current_area

        current_area = get_current_area()
        if current_area is not None:
            return cls.get_for_area(current_area)
        obj = cls.objects.filter(area__isnull=True).order_by("pk").first()
        if obj is not None:
            return obj

        from usuarios.models import AreaTrabalho

        active_areas = AreaTrabalho.objects.filter(ativa=True)
        if active_areas.count() == 1:
            fallback_area = active_areas.first()
        else:
            fallback_area, _ = AreaTrabalho.objects.get_or_create(
                sigla="__SISTEMA__",
                defaults={
                    "nome": "Configuração técnica sem contexto de área",
                    "ativa": False,
                },
            )
        return cls.get_for_area(fallback_area)

    @classmethod
    def get_for_area(cls, area):
        if area is None:
            return cls.get_singleton()
        obj, _ = cls.objects.get_or_create(area=area, defaults={"prazo_justificativa_dias": 10})
        return obj

    def save(self, *args, **kwargs):
        def norm_upper_words(val):
            return normalize_upper(val)

        self.nome_orgao = norm_upper_words(self.nome_orgao)
        self.sigla_orgao = norm_upper_words(self.sigla_orgao)
        self.sede = norm_upper_words(self.sede)
        self.nome_chefia = norm_upper_words(self.nome_chefia)
        self.cargo_chefia = norm_upper_words(self.cargo_chefia)
        self.cidade_endereco = norm_upper_words(self.cidade_endereco)
        self.logradouro = norm_upper_words(self.logradouro)
        self.bairro = norm_upper_words(self.bairro)
        self.numero = norm_upper_words(self.numero)
        self.uf = (self.uf or "").strip().upper()[:2]
        self.pt_sufixo_numero = norm_upper_words(self.pt_sufixo_numero)
        self.cep = normalize_digits(self.cep)
        self.telefone = normalize_digits(self.telefone)
        # Mantém compatível com código que ainda lê `sede`: mesmo valor que cidade_endereco.
        self.sede = self.cidade_endereco
        # Destinatário do Ofício: se um servidor cadastrado foi selecionado e os
        # campos de texto não foram preenchidos manualmente, herda nome/cargo/unidade dele.
        if self.destinatario_oficio_id:
            servidor = self.destinatario_oficio
            if not self.destinatario_oficio_nome:
                self.destinatario_oficio_nome = servidor.nome
            if not self.destinatario_oficio_cargo and servidor.cargo_id:
                self.destinatario_oficio_cargo = servidor.cargo.nome
            if not self.destinatario_oficio_unidade and servidor.unidade_id:
                self.destinatario_oficio_unidade = servidor.unidade.nome
        self.destinatario_oficio_nome = norm_upper_words(self.destinatario_oficio_nome)
        self.destinatario_oficio_cargo = norm_upper_words(self.destinatario_oficio_cargo)
        self.destinatario_oficio_unidade = norm_upper_words(self.destinatario_oficio_unidade)
        super().save(*args, **kwargs)


class AssinaturaConfiguracao(TimeStampedModel):
    """Assinante padrão por tipo de documento (Ofício, Justificativa, etc.)."""

    OFICIO = "OFICIO"
    JUSTIFICATIVA = "JUSTIFICATIVA"
    PLANO_TRABALHO = "PLANO_TRABALHO"
    ORDEM_SERVICO = "ORDEM_SERVICO"

    TIPO_CHOICES = [
        (OFICIO, "Ofício"),
        (JUSTIFICATIVA, "Justificativa"),
        (PLANO_TRABALHO, "Plano de Trabalho"),
        (ORDEM_SERVICO, "Ordem de Serviço"),
    ]

    configuracao = models.ForeignKey(
        ConfiguracaoSistema,
        on_delete=models.CASCADE,
        related_name="assinaturas",
    )
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    servidor = models.ForeignKey(
        Servidor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Servidor",
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Assinatura (configuração)"
        verbose_name_plural = "Assinaturas (configuração)"
        constraints = [
            models.UniqueConstraint(
                fields=("configuracao", "tipo", "ordem"),
                name="uniq_assinatura_cfg_tipo_ordem_v2",
            )
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} – {self.servidor or '—'}"



class TabelaDiaria(TimeStampedModel):
    """Valores de diária vigentes a partir de uma data.

    Substitui a tabela que estava fixada em ``roteiros/services/diarias.py``
    (defeito ``N-01``): mudar valor exigia deploy, e o histórico era recalculado
    retroativamente porque não havia noção de vigência.

    O operador informa **apenas o valor de 24 horas**; os percentuais de 15% e
    30% são derivados dele. Guardar os três calculados evita que uma mudança
    futura na regra de arredondamento altere documento já emitido — o valor
    gravado é o que valeu.

    Arredondamento: ``ROUND_HALF_UP`` em duas casas. A tabela anterior seguia
    essa regra em 8 dos 9 valores; a exceção (Brasília 30%, R$ 140,43 em vez de
    R$ 140,44) era inconsistência isolada, corrigida com a adoção da regra única.
    """

    PERCENTUAL_15 = Decimal("0.15")
    PERCENTUAL_30 = Decimal("0.30")
    CENTAVOS = Decimal("0.01")

    FAIXA_INTERIOR = "INTERIOR"
    FAIXA_CAPITAL = "CAPITAL"
    FAIXA_BRASILIA = "BRASILIA"
    FAIXA_CHOICES = [
        (FAIXA_INTERIOR, "Interior"),
        (FAIXA_CAPITAL, "Capital"),
        (FAIXA_BRASILIA, "Brasília"),
    ]

    faixa = models.CharField("Faixa", max_length=20, choices=FAIXA_CHOICES)
    vigencia_inicio = models.DateField(
        "Vigente a partir de",
        help_text="Roteiros com saída a partir desta data usam estes valores.",
    )
    valor_24h = models.DecimalField(
        "Diária de 24 horas",
        max_digits=10,
        decimal_places=2,
    )
    # Derivados de valor_24h, gravados para congelar o valor que valeu.
    valor_15 = models.DecimalField("15%", max_digits=10, decimal_places=2, editable=False)
    valor_30 = models.DecimalField("30%", max_digits=10, decimal_places=2, editable=False)

    class Meta:
        ordering = ["-vigencia_inicio", "faixa"]
        verbose_name = "Tabela de diárias"
        verbose_name_plural = "Tabelas de diárias"
        constraints = [
            UniqueConstraint(
                fields=("faixa", "vigencia_inicio"),
                name="uniq_tabela_diaria_faixa_vigencia",
            ),
            models.CheckConstraint(
                condition=Q(valor_24h__gt=0),
                name="tabela_diaria_valor_24h_positivo",
            ),
        ]
        indexes = [
            models.Index(
                fields=["faixa", "-vigencia_inicio"],
                name="cadastros_tabdiaria_busca_idx",
            ),
        ]

    def __str__(self):
        return f"{self.get_faixa_display()} — a partir de {self.vigencia_inicio:%d/%m/%Y}"

    @classmethod
    def derivar(cls, valor_24h):
        """Devolve (15%, 30%) de ``valor_24h``, em centavos, ROUND_HALF_UP."""
        base = Decimal(valor_24h)
        return (
            (base * cls.PERCENTUAL_15).quantize(cls.CENTAVOS, rounding=ROUND_HALF_UP),
            (base * cls.PERCENTUAL_30).quantize(cls.CENTAVOS, rounding=ROUND_HALF_UP),
        )

    def save(self, *args, **kwargs):
        self.valor_15, self.valor_30 = self.derivar(self.valor_24h)
        return super().save(*args, **kwargs)

    @classmethod
    def vigente_em(cls, faixa, data):
        """Tabela da faixa vigente na data — a mais recente que já começou.

        Devolve ``None`` quando não há vigência iniciada até a data, em vez de
        cair num valor padrão: cobrar com valor inventado é pior que falhar.
        """
        return (
            cls.objects.filter(faixa=faixa, vigencia_inicio__lte=data)
            .order_by("-vigencia_inicio")
            .first()
        )
