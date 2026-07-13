from datetime import timedelta

from django.db.models import Prefetch
from django.db.models import Q
from django.utils import timezone

from core.normalizers import remove_accents
from roteiros.models import RoteiroTrecho

from .models import PrestacaoContas
from .models import PrestacaoServidor


# Espelha a ordenação da lista de ofícios, adaptando os campos para a
# prestação (criação própria e viagem via roteiro do ofício).
_SORT_MAP = {
    "criacao_desc": ["-criado_em"],
    "criacao_asc":  ["criado_em"],
    "viagem_asc":   ["oficio__roteiro__saida_dt",  "-criado_em"],
    "viagem_desc":  ["-oficio__roteiro__saida_dt", "-criado_em"],
    "oficio_asc":   ["oficio__ano", "oficio__numero"],
    "oficio_desc":  ["-oficio__ano", "-oficio__numero"],
}


# ── Abas da lista de prestações ──
# A viagem só aparece em "Pendentes" quando já está acontecendo/aconteceu ou
# começa em até 1 dia; se ainda faltar mais de um dia, vai para "Que vai
# acontecer". "Arquivados" e "Finalizados" independem do tempo da viagem.
ABA_PENDENTES = "pendentes"
ABA_FUTURAS = "futuras"
ABA_ARQUIVADOS = "arquivados"
ABA_FINALIZADOS = "finalizados"
ABA_PADRAO = ABA_PENDENTES
ABAS_VALIDAS = {ABA_PENDENTES, ABA_FUTURAS, ABA_ARQUIVADOS, ABA_FINALIZADOS}


def normalizar_aba(aba: str | None) -> str:
    aba = (aba or "").strip()
    return aba if aba in ABAS_VALIDAS else ABA_PADRAO


def _q_da_aba(aba: str) -> Q:
    """Filtro que define quais prestações pertencem a cada aba (mutuamente exclusivas)."""
    if aba == ABA_FINALIZADOS:
        return Q(finalizada=True)
    if aba == ABA_ARQUIVADOS:
        return Q(arquivada=True, finalizada=False)

    # Pendentes e Futuras são "ativas" (nem arquivadas, nem finalizadas).
    ativa = Q(arquivada=False, finalizada=False)
    # Visível a partir de 1 dia antes da saída: saída <= amanhã.
    limite_visivel = timezone.localdate() + timedelta(days=1)
    if aba == ABA_FUTURAS:
        return ativa & Q(oficio__roteiro__saida_dt__date__gt=limite_visivel)
    # Pendentes: já acontecendo/aconteceu, começa em até 1 dia, ou sem data de
    # viagem definida (precisa de atenção mesmo sem roteiro).
    visivel = (
        Q(oficio__roteiro__saida_dt__date__lte=limite_visivel)
        | Q(oficio__roteiro__isnull=True)
        | Q(oficio__roteiro__saida_dt__isnull=True)
    )
    return ativa & visivel


def _base_prestacoes(
    q: str | None = None,
    status: str | None = None,
    viagem_de: str | None = None,
    viagem_ate: str | None = None,
    sort: str | None = None,
):
    """Queryset com os filtros de busca/ordenação, mas sem o recorte por aba."""
    order_fields = _SORT_MAP.get(sort or "criacao_desc", ["-criado_em"])
    queryset = (
        PrestacaoContas.objects.select_related(
            "oficio",
            "oficio__roteiro",
            "oficio__roteiro__origem_cidade",
            "oficio__roteiro__origem_estado",
            "oficio__viatura",
        )
        .prefetch_related(
            Prefetch(
                "oficio__roteiro__trechos",
                queryset=RoteiroTrecho.objects.select_related(
                    "origem_cidade", "origem_estado", "destino_cidade", "destino_estado"
                ).order_by("ordem"),
            ),
            Prefetch(
                "servidores_prestacao",
                queryset=PrestacaoServidor.objects.select_related(
                    "servidor", "servidor__cargo", "servidor__unidade"
                ).prefetch_related("documentos_anexos").order_by("pk"),
            ),
            "relatorio_tecnico",
            "diario_bordo",
        )
        .filter(oficio__cancelado=False)
        .order_by(*order_fields)
    )

    if status:
        queryset = queryset.filter(status=status)

    if q:
        query = q.strip()
        query_unaccent = remove_accents(query)
        filters = (
            Q(servidores_prestacao__servidor__nome__unaccent__icontains=query_unaccent)
            | Q(oficio__protocolo__unaccent__icontains=query_unaccent)
            | Q(servidores_prestacao__numero_solicitacao__unaccent__icontains=query_unaccent)
            | Q(servidores_prestacao__servidor__cargo__nome__unaccent__icontains=query_unaccent)
        )
        if query.isdigit():
            filters |= Q(oficio__numero=int(query)) | Q(oficio__ano=int(query))
        queryset = queryset.filter(filters).distinct()

    if viagem_de:
        try:
            queryset = queryset.filter(
                oficio__roteiro__isnull=False,
                oficio__roteiro__saida_dt__date__gte=viagem_de,
            )
        except Exception:
            pass
    if viagem_ate:
        try:
            queryset = queryset.filter(
                oficio__roteiro__isnull=False,
                oficio__roteiro__saida_dt__date__lte=viagem_ate,
            )
        except Exception:
            pass

    return queryset


def listar_prestacoes(
    q: str | None = None,
    status: str | None = None,
    aba: str | None = None,
    viagem_de: str | None = None,
    viagem_ate: str | None = None,
    sort: str | None = None,
):
    """Prestações da aba pedida já com os filtros de busca/ordenação aplicados."""
    base = _base_prestacoes(
        q=q, status=status, viagem_de=viagem_de, viagem_ate=viagem_ate, sort=sort
    )
    return base.filter(_q_da_aba(normalizar_aba(aba)))


def contar_por_aba(
    q: str | None = None,
    status: str | None = None,
    viagem_de: str | None = None,
    viagem_ate: str | None = None,
) -> dict:
    """Total de prestações em cada aba, respeitando os filtros de busca ativos."""
    base = _base_prestacoes(q=q, status=status, viagem_de=viagem_de, viagem_ate=viagem_ate)
    return {
        aba: base.filter(_q_da_aba(aba)).values("pk").distinct().count()
        for aba in (ABA_PENDENTES, ABA_FUTURAS, ABA_ARQUIVADOS, ABA_FINALIZADOS)
    }
