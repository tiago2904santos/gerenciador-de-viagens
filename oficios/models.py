from django.db import models
from django.db.models import Q
from django.utils import timezone

from cadastros.models import CancelavelModel
from cadastros.models import Combustivel
from cadastros.models import Servidor
from cadastros.models import TimeStampedModel
from cadastros.models import Unidade
from cadastros.models import Viatura
from core.normalizers import normalize_spaces
from core.normalizers import normalize_upper
from core.utils.masks import normalize_protocolo
from roteiros.models import Roteiro


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
        on_delete=models.SET_NULL,
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

    class Meta:
        ordering = ["-data_criacao", "-created_at"]
        verbose_name = "Ofício"
        verbose_name_plural = "Ofícios"
        constraints = [
            models.UniqueConstraint(
                fields=["ano", "numero"],
                condition=Q(ano__isnull=False, numero__isnull=False),
                name="oficios_oficio_ano_numero_unique",
            )
        ]

    def __str__(self):
        return f"Ofício {self.numero_formatado}"

    @property
    def numero_formatado(self) -> str:
        if self.numero and self.ano:
            return f"{self.numero:02d}/{self.ano}"
        return "—"

    @classmethod
    def get_next_available_numero(cls, ano: int | None = None) -> int:
        from django.conf import settings

        resolved_year = ano or timezone.localdate().year
        piso = getattr(settings, "OFICIO_NUMERO_INICIAL", {}).get(resolved_year, 0)
        numeros_usados = set(
            cls.objects.filter(ano=resolved_year)
            .exclude(numero__isnull=True)
            .values_list("numero", flat=True)
        )
        candidato = max(piso, 1)
        while candidato in numeros_usados:
            candidato += 1
        return candidato

    def save(self, *args, **kwargs):
        self.protocolo = normalize_protocolo(self.protocolo)
        self.assunto = normalize_spaces(self.assunto)
        self.motivo = normalize_spaces(self.motivo)
        self.custeio_observacao = normalize_spaces(self.custeio_observacao)
        super().save(*args, **kwargs)

    def diarias_para_servidores(self):
        """Diárias deste ofício = valor por servidor (persistido no roteiro) × nº de servidores.

        O roteiro guarda sempre o valor para 1 servidor; cada ofício aplica aqui a
        multiplicação pelo seu próprio efetivo, de modo que adicionar/remover servidores
        atualize o resumo e o documento final.
        """
        from decimal import Decimal

        from roteiros.services.valor_extenso import valor_por_extenso_ptbr

        roteiro = self.roteiro
        if not roteiro or roteiro.valor_diarias is None:
            return None

        # Sem servidores ainda (rascunho): mantém o valor base de 1 servidor.
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


class ModeloMotivoOficio(TimeStampedModel):
    nome = models.CharField(max_length=120, unique=True)
    texto = models.TextField()
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=100)
    is_padrao = models.BooleanField(default=False)

    class Meta:
        ordering = ["ordem", "nome"]
        verbose_name = "Modelo de motivo de ofício"
        verbose_name_plural = "Modelos de motivo de ofício"

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.nome = normalize_upper(self.nome)
        self.texto = normalize_spaces(self.texto)
        if self.is_padrao:
            ModeloMotivoOficio.objects.exclude(pk=self.pk).update(is_padrao=False)
        super().save(*args, **kwargs)
