from decimal import Decimal, InvalidOperation

from django.db import models

from core.constraints import nao_negativo
from core.constraints import periodo_ordenado
from core.managers import AreaScopedManager

from core.models import CancelavelModel
from cadastros.models import Cidade
from cadastros.models import Estado


class Roteiro(CancelavelModel):
    """
    Roteiro avulso (e futuramente vinculado a evento), alinhado ao legacy `RoteiroEvento`.
    """

    STATUS_RASCUNHO = "RASCUNHO"
    STATUS_FINALIZADO = "FINALIZADO"
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, "Rascunho"),
        (STATUS_FINALIZADO, "Finalizado"),
    ]

    ROTA_STATUS_PENDENTE = "pendente"
    ROTA_STATUS_CALCULADA = "calculada"
    ROTA_STATUS_MANUAL = "manual"
    ROTA_STATUS_ERRO = "erro"
    ROTA_STATUS_DESATUALIZADA = "desatualizada"
    ROTA_STATUS_CHOICES = [
        (ROTA_STATUS_PENDENTE, "Pendente"),
        (ROTA_STATUS_CALCULADA, "Calculada"),
        (ROTA_STATUS_MANUAL, "Manual"),
        (ROTA_STATUS_ERRO, "Erro"),
        (ROTA_STATUS_DESATUALIZADA, "Desatualizada"),
    ]

    ROTA_FONTE_OPENROUTESERVICE = "openrouteservice"
    ROTA_FONTE_MANUAL = "manual"
    ROTA_FONTE_CACHE = "cache"

    TIPO_EVENTO = "EVENTO"
    TIPO_AVULSO = "AVULSO"
    TIPO_CHOICES = [
        (TIPO_EVENTO, "Vinculado a evento"),
        (TIPO_AVULSO, "Avulso"),
    ]

    area = models.ForeignKey(
        "usuarios.AreaTrabalho",
        null=False,
        blank=True,
        on_delete=models.PROTECT,
        related_name="roteiros",
        verbose_name="Area de trabalho",
    )
    origem_estado = models.ForeignKey(
        Estado,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Estado sede",
    )
    origem_cidade = models.ForeignKey(
        Cidade,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Cidade sede",
    )
    saida_dt = models.DateTimeField("Data/hora saída", null=True, blank=True)
    duracao_min = models.PositiveIntegerField("Duração (min)", null=True, blank=True)
    chegada_dt = models.DateTimeField("Data/hora chegada", null=True, blank=True)
    retorno_saida_dt = models.DateTimeField("Retorno - saída", null=True, blank=True)
    retorno_duracao_min = models.PositiveIntegerField("Retorno - duração (min)", null=True, blank=True)
    retorno_chegada_dt = models.DateTimeField("Retorno - chegada", null=True, blank=True)
    quantidade_diarias = models.CharField("Quantidade de diárias", max_length=120, blank=True, default="")
    valor_diarias = models.DecimalField(
        "Valor das diárias", max_digits=12, decimal_places=2, null=True, blank=True
    )
    valor_diarias_extenso = models.TextField("Valor das diárias por extenso", blank=True, default="")
    observacoes = models.TextField("Observações", blank=True, default="")
    rota_geojson = models.JSONField("Geometria da rota (GeoJSON)", null=True, blank=True)
    rota_distancia_calculada_km = models.DecimalField(
        "Distância calculada (km)",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    rota_duracao_calculada_min = models.PositiveIntegerField(
        "Duração calculada (min)", null=True, blank=True
    )
    rota_fonte = models.CharField(
        "Fonte do cálculo da rota",
        max_length=40,
        blank=True,
        default="",
    )
    rota_status = models.CharField(
        "Status da rota no mapa",
        max_length=20,
        choices=ROTA_STATUS_CHOICES,
        default=ROTA_STATUS_PENDENTE,
    )
    rota_assinatura = models.CharField(
        "Assinatura para cache da rota", max_length=128, blank=True, default=""
    )
    rota_calculada_em = models.DateTimeField(
        "Rota consolidada calculada em", null=True, blank=True
    )
    rota_distancia_manual_km = models.DecimalField(
        "Distância ajustada manualmente (km)",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    rota_duracao_manual_min = models.PositiveIntegerField(
        "Duração ajustada manualmente (min)", null=True, blank=True
    )
    rota_ajuste_justificativa = models.TextField(
        "Justificativa do ajuste manual da rota", blank=True, default=""
    )
    status = models.CharField(
        "Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO
    )
    tipo = models.CharField(
        "Tipo de roteiro",
        max_length=20,
        choices=TIPO_CHOICES,
        default=TIPO_AVULSO,
    )
    evento = models.ForeignKey(
        "eventos.Evento",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="roteiros",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # `BE-09`: `objects` recorta pela área ativa; `all_objects` é a saída explícita
    # para código que precisa enxergar todas. `default_manager_name` mantém o admin,
    # as relações reversas e `validate_unique` irrestritos — ver `core/managers.py`.
    all_objects = models.Manager()
    objects = AreaScopedManager()

    class Meta:
        default_manager_name = "all_objects"
        ordering = ["-created_at"]
        verbose_name = "Roteiro"
        verbose_name_plural = "Roteiros"
        constraints = [
            # `DB-07`. A cadeia real e' saida -> chegada -> retorno_saida ->
            # retorno_chegada. Os tres elos consecutivos, mais o limite externo:
            # com nulo no meio a transitividade se perde, e o par externo e'
            # justamente o que o motor de diarias usa para contar dia.
            #
            # `NOVO-36`: este elo ficou de fora do `DB-07` porque reprovava codigo
            # de producao — a derivacao posicional do cabecalho gravava chegada
            # antes da saida ao reordenar destinos. O produtor foi corrigido para
            # derivar cronologicamente, e a constraint entra junto com ele.
            periodo_ordenado("saida_dt", "chegada_dt", name="roteiro_ida_ordenada"),
            periodo_ordenado(
                "chegada_dt", "retorno_saida_dt", name="roteiro_permanencia_ordenada",
            ),
            periodo_ordenado(
                "retorno_saida_dt", "retorno_chegada_dt", name="roteiro_volta_ordenada",
            ),
            periodo_ordenado(
                "saida_dt", "retorno_chegada_dt", name="roteiro_periodo_ordenado",
            ),
            # Zero e' legitimo (viagem sem diaria); negativo so sai de conta
            # errada, e daqui vai para o oficio e para a prestacao assinada.
            nao_negativo("valor_diarias", name="roteiro_valor_diarias_nao_negativo"),
            nao_negativo(
                "rota_distancia_calculada_km", name="roteiro_distancia_calc_nao_negativa",
            ),
            nao_negativo(
                "rota_distancia_manual_km", name="roteiro_distancia_manual_nao_negativa",
            ),
        ]

    def __str__(self):
        orig = self.origem_cidade or self.origem_estado
        return str(orig) if orig else f"Roteiro #{self.pk or ''}"

    def save(self, *args, **kwargs):
        if self.area_id is None:
            if self.evento_id and self.evento and self.evento.area_id:
                self.area = self.evento.area
            else:
                from core.tenancy import get_current_area

                self.area = get_current_area()
        super().save(*args, **kwargs)

    def aplicar_diarias_calculadas(self, resultado):
        totais = (resultado or {}).get("totais") or {}
        self.quantidade_diarias = totais.get("total_diarias") or ""

        valor_decimal = totais.get("total_valor_decimal")
        if valor_decimal is None:
            valor_texto = (totais.get("total_valor") or "").strip()
            if valor_texto:
                try:
                    valor_decimal = Decimal(valor_texto.replace(".", "").replace(",", "."))
                except (InvalidOperation, TypeError, ValueError):
                    valor_decimal = None
        self.valor_diarias = valor_decimal
        self.valor_diarias_extenso = totais.get("valor_extenso") or ""


class RoteiroDestino(models.Model):
    roteiro = models.ForeignKey(
        Roteiro,
        on_delete=models.CASCADE,
        related_name="destinos",
        verbose_name="Roteiro",
    )
    estado = models.ForeignKey(
        Estado,
        on_delete=models.PROTECT,
        related_name="roteiro_destinos",
        verbose_name="Estado",
    )
    cidade = models.ForeignKey(
        Cidade,
        on_delete=models.PROTECT,
        related_name="roteiro_destinos",
        verbose_name="Cidade",
    )
    ordem = models.PositiveIntegerField("Ordem", default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Mesmo caso dos trechos: sempre lidos por roteiro e em ordem (P-03).
        indexes = [
            models.Index(fields=["roteiro", "ordem"], name="roteiro_destino_ordem_idx"),
        ]
        # `DB-08`: dois destinos na mesma posição eram aceitos, e o destino
        # duplicado é contado **duas vezes pelo motor de diárias** — sai no ofício
        # e no termo. Constraint simples (não adiada) porque o único escritor
        # apaga tudo antes de recriar: `roteiro_logic.py:1581`
        # (`roteiro.destinos.all().delete()`), depois `create` com `enumerate`.
        # Reordenação por troca de posição não existe neste caminho.
        constraints = [
            models.UniqueConstraint(
                fields=["roteiro", "ordem"], name="roteiro_destino_ordem_unique",
            ),
        ]
        ordering = ["roteiro", "ordem"]
        verbose_name = "Destino do roteiro"
        verbose_name_plural = "Destinos do roteiro"

    def __str__(self):
        return f"{self.cidade} ({self.estado.sigla})"


class RoteiroTrecho(models.Model):
    TIPO_IDA = "IDA"
    TIPO_RETORNO = "RETORNO"
    TIPO_CHOICES = [
        (TIPO_IDA, "Ida"),
        (TIPO_RETORNO, "Retorno"),
    ]

    roteiro = models.ForeignKey(
        Roteiro,
        on_delete=models.CASCADE,
        related_name="trechos",
        verbose_name="Roteiro",
    )
    ordem = models.PositiveIntegerField("Ordem", default=0)
    tipo = models.CharField("Tipo", max_length=10, choices=TIPO_CHOICES, default=TIPO_IDA)
    origem_estado = models.ForeignKey(
        Estado,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Estado origem",
    )
    origem_cidade = models.ForeignKey(
        Cidade,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Cidade origem",
    )
    destino_estado = models.ForeignKey(
        Estado,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Estado destino",
    )
    destino_cidade = models.ForeignKey(
        Cidade,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Cidade destino",
    )
    saida_dt = models.DateTimeField("Saída", null=True, blank=True)
    chegada_dt = models.DateTimeField("Chegada", null=True, blank=True)
    distancia_km = models.DecimalField(
        "Distância (km)",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    duracao_estimada_min = models.PositiveIntegerField(
        "Duração estimada (min)", null=True, blank=True
    )
    tempo_cru_estimado_min = models.PositiveIntegerField(
        "Tempo cru estimado (min)", null=True, blank=True
    )
    tempo_adicional_min = models.IntegerField(
        "Tempo adicional (min)", null=True, blank=True, default=0
    )
    rota_fonte = models.CharField("Fonte da rota", max_length=30, blank=True, default="")
    rota_calculada_em = models.DateTimeField("Rota calculada em", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # O carregamento quente do sistema: todo card de lista puxa os trechos
        # de um roteiro em ordem. Sem o composto, o banco usa o indice da FK e
        # ordena depois; com ele, e' uma varredura so (P-03).
        indexes = [
            models.Index(fields=["roteiro", "ordem"], name="roteiro_trecho_ordem_idx"),
        ]
        ordering = ["roteiro", "ordem"]
        constraints = [
            # `DB-08` fatia 2: a posição é a sequência do itinerário impresso, e
            # duas linhas na mesma posição tornam o documento não determinístico —
            # a mesma tela gera dois PDFs diferentes conforme o desempate de `pk`.
            # O retorno não disputa posição com a ida: `roteiro_logic.py` dá a ele
            # `len(trechos_validated)`, uma casa acima de todas as de ida.
            #
            # Ao contrário do `RoteiroDestino`, aqui o escritor **não** apaga antes
            # de recriar: ele reaproveita a linha por `id` para preservar campo
            # manual (KM, tempo adicional). Por isso a constraint só é segura junto
            # com o escritor em dois passos — ver
            # `_salvar_roteiro_avulso_from_roteiro_state`.
            models.UniqueConstraint(
                fields=["roteiro", "ordem"], name="roteiro_trecho_ordem_unique",
            ),
            # `DB-07`: cada trecho tem o proprio par, e a soma deles e' o
            # itinerario impresso. Um trecho invertido nao aparece na tela.
            periodo_ordenado("saida_dt", "chegada_dt", name="roteiro_trecho_ordenado"),
            nao_negativo("distancia_km", name="roteiro_trecho_distancia_nao_negativa"),
        ]
        verbose_name = "Trecho do roteiro"
        verbose_name_plural = "Trechos do roteiro"

    def __str__(self):
        orig = self.origem_cidade or self.origem_estado
        dest = self.destino_cidade or self.destino_estado
        return f"{orig} -> {dest} ({self.get_tipo_display()})"
