from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.managers import AreaScopedManager
from core.tenancy import get_current_area
from core.models import CancelavelModel
from cadastros.models import Combustivel
from cadastros.models import Servidor
from core.models import TimeStampedModel
from cadastros.models import Unidade
from cadastros.models import Viatura
from core.normalizers import normalize_spaces
from core.normalizers import normalize_upper
from core.utils.masks import normalize_protocolo
from roteiros.models import Roteiro


#: Nome da `UniqueConstraint` que guarda (área, ano, número). Vive aqui, e não solto no
#: `Meta`, porque `core.numeracao` compara o metadado da exceção contra ele: nome duplicado
#: em dois lugares é nome que diverge no dia do rename, e a divergência seria silenciosa.
CONSTRAINT_NUMERO_OFICIO = "oficios_oficio_area_ano_numero_unique"


class Oficio(TimeStampedModel, CancelavelModel):
    STATUS_RASCUNHO = "RASCUNHO"
    STATUS_GERADO = "GERADO"
    STATUS_FINALIZADO = "FINALIZADO"
    STATUS_ARQUIVADO = "ARQUIVADO"
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, "Rascunho"),
        (STATUS_GERADO, "Gerado"),
        (STATUS_FINALIZADO, "Finalizado (legado)"),
        (STATUS_ARQUIVADO, "Arquivado"),
    ]

    CUSTEIO_UNIDADE_DPC = "UNIDADE_DPC"
    CUSTEIO_OUTRA_INSTITUICAO = "OUTRA_INSTITUICAO"
    CUSTEIO_ONUS_LIMITADO = "ONUS_LIMITADO"
    CUSTEIO_CHOICES = [
        (CUSTEIO_UNIDADE_DPC, "Unidade DPC"),
        (CUSTEIO_OUTRA_INSTITUICAO, "Outra instituição"),
        (CUSTEIO_ONUS_LIMITADO, "Ônus limitado"),
    ]

    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.PROTECT,
        null=False,
        blank=True,
        related_name="oficios",
        verbose_name="Area de trabalho",
    )
    numero = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    ano = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    data_criacao = models.DateField(default=timezone.localdate, db_index=True)
    protocolo = models.CharField(max_length=30, blank=True, default="", db_index=True)
    assunto = models.CharField(max_length=255, blank=True, default="")
    motivo = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO)
    evento = models.ForeignKey(
        "eventos.Evento",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="oficios",
    )
    roteiro = models.ForeignKey(
        Roteiro,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="oficios",
    )
    solicitante = models.ForeignKey(
        Unidade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    custeio = models.CharField(
        max_length=30,
        choices=CUSTEIO_CHOICES,
        default=CUSTEIO_UNIDADE_DPC,
    )
    custeio_observacao = models.CharField(max_length=255, blank=True, default="")
    servidores = models.ManyToManyField(Servidor, blank=True, related_name="oficios")
    diarias_quantidade_servidores = models.PositiveIntegerField(
        "Quantidade de servidores considerada nas diárias",
        null=True,
        blank=True,
        editable=False,
        help_text=(
            "Snapshot do efetivo usado no total de diárias; não muda quando um "
            "servidor é excluído posteriormente do cadastro."
        ),
    )
    servidores_termo_autorizacao = models.ManyToManyField(
        Servidor,
        blank=True,
        related_name="oficios_termo_autorizacao",
        verbose_name="Servidores com Termo de Autorização",
    )
    viatura = models.ForeignKey(
        Viatura,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="oficios",
    )
    motorista = models.ForeignKey(
        Servidor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="oficios_motorista",
    )

    porte_transporte_armas = models.BooleanField(
        default=True,
        verbose_name="Porte/transporte de armas",
    )
    transporte_placa_manual = models.CharField(max_length=7, blank=True, default="")
    transporte_modelo_manual = models.CharField(max_length=120, blank=True, default="")
    transporte_combustivel_manual = models.ForeignKey(
        Combustivel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    transporte_tipo_manual = models.CharField(
        max_length=20,
        choices=Viatura.TIPO_CHOICES,
        blank=True,
        default="",
    )

    MOTORISTA_MODO_SERVIDOR = "SERVIDOR"
    MOTORISTA_MODO_MANUAL = "MANUAL"
    MOTORISTA_MODO_CHOICES = [
        (MOTORISTA_MODO_SERVIDOR, "Servidor"),
        (MOTORISTA_MODO_MANUAL, "Manual"),
    ]
    motorista_modo = models.CharField(
        max_length=10,
        choices=MOTORISTA_MODO_CHOICES,
        default=MOTORISTA_MODO_SERVIDOR,
    )
    motorista_manual_nome = models.CharField(max_length=255, blank=True, default="")
    motorista_manual_rg = models.CharField(max_length=30, blank=True, default="")
    motorista_manual_cpf = models.CharField(max_length=11, blank=True, default="")
    motorista_manual_cargo = models.CharField(max_length=120, blank=True, default="")
    motorista_manual_unidade = models.CharField(max_length=255, blank=True, default="")
    motorista_manual_observacao = models.TextField(blank=True, default="")
    motorista_oficio_referencia = models.CharField(
        max_length=16,
        blank=True,
        default="",
        verbose_name="Ofício do motorista",
        help_text="Referência no formato número/ano (ex.: 15/2026).",
    )
    motorista_protocolo_ref = models.CharField(
        max_length=30,
        blank=True,
        default="",
        verbose_name="Protocolo do motorista",
    )
    retificado_documento = models.BooleanField(
        default=False,
        verbose_name="Emitir como retificado",
        help_text="Quando verdadeiro e o ofício seria Autorização por datas, o documento usa o rótulo Retificado.",
    )
    complementar_documento = models.BooleanField(
        default=False,
        verbose_name="Emitir como complementar",
        help_text="Quando verdadeiro, o documento usa o rótulo Complementar ao lado do número do ofício.",
    )

    # `BE-09`: `objects` recorta pela área ativa; `all_objects` é a saída explícita
    # para código que precisa enxergar todas. `default_manager_name` mantém o admin,
    # as relações reversas e `validate_unique` irrestritos — ver `core/managers.py`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["-data_criacao", "-created_at"]
        verbose_name = "Ofício"
        verbose_name_plural = "Ofícios"
        constraints = [
            models.UniqueConstraint(
                fields=["area", "ano", "numero"],
                condition=Q(ano__isnull=False, numero__isnull=False),
                name=CONSTRAINT_NUMERO_OFICIO,
            )
        ]

    def __str__(self):
        return f"Ofício {self.numero_formatado}"

    @property
    def numero_formatado(self) -> str:
        if self.numero and self.ano:
            return f"{self.numero:02d}/{self.ano}"
        return "—"

    @property
    def protocolo_confirmado(self) -> bool:
        """O eProtocolo completo é o gate para emitir o ofício."""
        return bool(normalize_protocolo(self.protocolo or ""))

    @classmethod
    def get_next_available_numero(cls, ano: int | None = None, area=None) -> int:
        """Sugere o próximo número: reaproveita a menor lacuna liberada por exclusão
        (ver ``OficioNumeroLacuna``); caso não haja lacuna, segue para o maior número
        usado + 1. Números apenas pulados manualmente (nunca ocupados) não são
        oferecidos como sugestão — só voltam a ficar disponíveis se o ofício que os
        usou for excluído.
        """
        from django.conf import settings

        resolved_year = ano or timezone.localdate().year
        area = get_current_area() if area is None else area
        configuracao = None
        if getattr(settings, "OFICIO_NUMERACAO_USAR_CONFIGURACAO", True):
            # `BE-09`: `all_objects` é obrigatório aqui, e este é o site mais
            # perigoso do ID. A união com `area IS NULL` busca o **padrão global**
            # de propósito, para servir de piso a quem não tem configuração
            # própria. Com `objects`, dentro de um request na área A a consulta
            # vira `area=A AND (area=A OR area IS NULL)` = `area=A`: a linha
            # global some, `piso` cai para 1 e a numeração de ofício reinicia.
            configuracao = ConfiguracaoNumeracaoOficio.all_objects.filter(
                Q(area=area) | Q(area__isnull=True),
                ano=resolved_year,
            ).order_by(models.F("area_id").desc(nulls_last=True)).first()
        piso = max(configuracao.numero_inicial if configuracao else 1, 1)
        # `BE-09`: idem — o escopo destas duas é o `area` recebido no argumento, e
        # as quatro linhas abaixo o aplicam. Recortar de novo pela área ativa
        # esvaziaria a consulta sempre que as duas divergissem.
        qs = cls.all_objects.filter(ano=resolved_year)
        lacunas_qs = OficioNumeroLacuna.all_objects.filter(ano=resolved_year, numero__gte=piso)
        if area is not None:
            qs = qs.filter(area=area)
            lacunas_qs = lacunas_qs.filter(area=area)
        else:
            qs = qs.filter(area__isnull=True)
            lacunas_qs = lacunas_qs.filter(area__isnull=True)
        numeros_usados = set(
            qs
            .exclude(numero__isnull=True)
            .values_list("numero", flat=True)
        )
        lacuna = (
            lacunas_qs.exclude(numero__in=numeros_usados)
            .order_by("numero")
            .first()
        )
        if lacuna is not None:
            return lacuna.numero
        maior_usado = max(numeros_usados, default=piso - 1)
        return max(maior_usado + 1, piso)

    def save(self, *args, **kwargs):
        if self.area_id is None:
            if self.evento_id and self.evento and self.evento.area_id:
                self.area = self.evento.area
            else:
                self.area = get_current_area()
        self.protocolo = normalize_protocolo(self.protocolo)
        status_forcado = not self.protocolo_confirmado and self.status != self.STATUS_RASCUNHO
        if status_forcado:
            self.status = self.STATUS_RASCUNHO
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"status"}
        self.assunto = normalize_spaces(self.assunto)
        self.motivo = normalize_spaces(self.motivo)
        self.custeio_observacao = normalize_spaces(self.custeio_observacao)
        super().save(*args, **kwargs)
        if self.numero and self.ano:
            # `BE-09`: `all_objects` — a lacuna consumida é a da área deste ofício,
            # já no filtro. Recortada pela área ativa, ela sobreviveria e o número
            # voltaria a ser oferecido como disponível estando em uso.
            OficioNumeroLacuna.all_objects.filter(
                area=self.area, ano=self.ano, numero=self.numero,
            ).delete()

    def diarias_para_servidores(self):
        """Diárias deste ofício = valor por servidor (persistido no roteiro) × nº de servidores.

        O roteiro guarda sempre o valor para 1 servidor. O ofício aplica o snapshot
        do efetivo aceito no passo de viajantes, para que uma exclusão posterior no
        cadastro não reescreva o valor de documento já emitido.
        """
        from decimal import Decimal

        from roteiros.services.valor_extenso import valor_por_extenso_ptbr

        roteiro = self.roteiro
        if not roteiro or roteiro.valor_diarias is None:
            return None

        # Registros anteriores à migração, instâncias ainda não salvas e fixtures
        # montadas diretamente continuam com fallback seguro para o efetivo vivo.
        qtd_servidores = self.diarias_quantidade_servidores
        if qtd_servidores is None:
            qtd_servidores = (self.servidores.count() if self.pk else 0) or 1
        por_servidor = roteiro.valor_diarias
        if not isinstance(por_servidor, Decimal):
            por_servidor = Decimal(str(por_servidor))

        if qtd_servidores == 1:
            # Multiplicador 1: preserva exatamente o que está persistido no roteiro
            # (inclusive o "por extenso" original, que pode diferir do recalculado).
            return {
                "quantidade": roteiro.quantidade_diarias or "",
                "valor_decimal": por_servidor,
                "valor_extenso": roteiro.valor_diarias_extenso or "",
                "quantidade_servidores": 1,
            }

        total = por_servidor * qtd_servidores
        return {
            "quantidade": roteiro.quantidade_diarias or "",
            "valor_decimal": total,
            "valor_extenso": valor_por_extenso_ptbr(total),
            "quantidade_servidores": qtd_servidores,
        }


class ConfiguracaoNumeracaoOficio(models.Model):
    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="configuracoes_numeracao_oficio",
    )
    ano = models.PositiveIntegerField()
    numero_inicial = models.PositiveIntegerField(default=1)
    atualizado_em = models.DateTimeField(auto_now=True)

    # `BE-09`: ver `core/managers.py`. Atenção especial neste modelo — a linha com
    # `area IS NULL` é o **padrão global**, e `get_next_available_numero` a busca de
    # propósito junto com a da área. Toda consulta a ele aqui usa `all_objects`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["-ano", "area_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["ano"],
                condition=Q(area__isnull=True),
                name="oficios_numeracao_global_ano_unique",
            ),
            models.UniqueConstraint(
                fields=["area", "ano"],
                condition=Q(area__isnull=False),
                name="oficios_numeracao_area_ano_unique",
            ),
        ]

    def __str__(self):
        escopo = self.area.sigla if self.area_id else "Global"
        return f"{escopo} · {self.ano}: inicia em {self.numero_inicial}"


class OficioNumeroLacuna(models.Model):
    """Número de ofício liberado para reaproveitamento (exclusão de um ofício numerado).

    Números pulados manualmente (ex.: ir direto de 10 para 15) nunca entram aqui —
    só a exclusão de um ofício já numerado registra a lacuna, via ``excluir_oficio``.
    """

    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="oficio_lacunas",
        verbose_name="Area de trabalho",
    )
    ano = models.PositiveIntegerField(db_index=True)
    numero = models.PositiveIntegerField()
    liberado_em = models.DateTimeField(auto_now_add=True)

    # `BE-09`: ver `core/managers.py`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["ano", "numero"]
        verbose_name = "Número de ofício liberado"
        verbose_name_plural = "Números de ofício liberados"
        constraints = [
            models.UniqueConstraint(fields=["area", "ano", "numero"], name="oficios_lacuna_area_ano_numero_unique"),
        ]

    def __str__(self):
        return f"{self.numero:02d}/{self.ano}"


class ModeloMotivoOficio(TimeStampedModel):
    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="modelos_motivo_oficio",
        verbose_name="Area de trabalho",
    )
    nome = models.CharField(max_length=120)
    texto = models.TextField()
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=100)
    is_padrao = models.BooleanField(default=False)

    # `BE-09`: ver `core/managers.py`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["ordem", "nome"]
        verbose_name = "Modelo de motivo de ofício"
        verbose_name_plural = "Modelos de motivo de ofício"
        indexes = [
            models.Index(fields=["area", "ordem", "nome"], name="oficios_motivo_area_ordem_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["nome"], condition=Q(area__isnull=True), name="oficios_motivo_nome_global_unique"),
            models.UniqueConstraint(fields=["area", "nome"], condition=Q(area__isnull=False), name="oficios_motivo_area_nome_unique"),
            models.UniqueConstraint(fields=["area"], condition=Q(area__isnull=False) & Q(is_padrao=True), name="oficios_motivo_area_padrao_unique"),
            models.UniqueConstraint(fields=["is_padrao"], condition=Q(area__isnull=True) & Q(is_padrao=True), name="oficios_motivo_global_padrao_unique"),
        ]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.nome = normalize_upper(self.nome)
        self.texto = normalize_spaces(self.texto)
        if self.is_padrao:
            # `BE-09`: `all_objects` porque o escopo é o `self.area` deste modelo,
            # não o do request. Com `objects` e área explícita diferente da ativa,
            # o padrão anterior não seria desmarcado e a gravação estouraria em
            # `oficios_motivo_area_padrao_unique`.
            ModeloMotivoOficio.all_objects.exclude(pk=self.pk).filter(area=self.area).update(
                is_padrao=False,
            )
        super().save(*args, **kwargs)
