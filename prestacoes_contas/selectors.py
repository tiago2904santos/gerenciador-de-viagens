from django.db.models import Prefetch
from django.db.models import Q

from core.normalizers import remove_accents
from core.tenancy import get_current_area
from roteiros.models import RoteiroTrecho

from .models import PrestacaoServidor


# Ordenação primaria por ofício (agrupa cards do mesmo ofício), com
# desempate por criação do ofício/prestação e pk do servidor.
_SORT_MAP = {
    "criacao_desc": ["-prestacao__criado_em", "prestacao_id", "pk"],
    "criacao_asc": ["prestacao__criado_em", "prestacao_id", "pk"],
    "viagem_asc": ["prestacao__oficio__roteiro__saida_dt", "-prestacao__criado_em", "prestacao_id", "pk"],
    "viagem_desc": ["-prestacao__oficio__roteiro__saida_dt", "-prestacao__criado_em", "prestacao_id", "pk"],
    "oficio_asc": ["prestacao__oficio__ano", "prestacao__oficio__numero", "prestacao_id", "pk"],
    "oficio_desc": ["-prestacao__oficio__ano", "-prestacao__oficio__numero", "prestacao_id", "pk"],
}


# ── Abas da lista de prestações (por servidor) ──
ABA_NAO_LIBERADAS = "nao_liberadas"
ABA_LIBERADAS = "liberadas"
ABA_ARQUIVADOS = "arquivados"
ABA_FINALIZADOS = "finalizados"
ABA_PADRAO = ABA_NAO_LIBERADAS
ABAS_VALIDAS = {ABA_NAO_LIBERADAS, ABA_LIBERADAS, ABA_ARQUIVADOS, ABA_FINALIZADOS}


def normalizar_aba(aba: str | None) -> str:
    aba = (aba or "").strip()
    return aba if aba in ABAS_VALIDAS else ABA_PADRAO


def _q_da_aba(aba: str) -> Q:
    """Filtro que define quais servidores pertencem a cada aba (mutuamente exclusivas)."""
    if aba == ABA_FINALIZADOS:
        return Q(finalizada=True)
    if aba == ABA_ARQUIVADOS:
        return Q(arquivada=True, finalizada=False)

    ativa = Q(arquivada=False, finalizada=False)
    if aba == ABA_LIBERADAS:
        return ativa & Q(data_liberacao_diarias__isnull=False)
    return ativa & Q(data_liberacao_diarias__isnull=True)


def _filter_servidores_by_area(queryset):
    area = get_current_area()
    if area is None:
        return queryset.filter(prestacao__area__isnull=True)
    return queryset.filter(prestacao__area=area)


def _base_servidores(
    q: str | None = None,
    status: str | None = None,
    viagem_de: str | None = None,
    viagem_ate: str | None = None,
    sort: str | None = None,
):
    """Queryset com filtros de busca/ordenação, sem o recorte por aba."""
    order_fields = _SORT_MAP.get(sort or "criacao_desc", _SORT_MAP["criacao_desc"])
    queryset = (
        _filter_servidores_by_area(PrestacaoServidor.objects)
        .select_related(
            "servidor",
            "servidor__cargo",
            "servidor__unidade",
            "prestacao",
            "prestacao__oficio",
            "prestacao__oficio__roteiro",
            "prestacao__oficio__roteiro__origem_cidade",
            "prestacao__oficio__roteiro__origem_estado",
            "prestacao__oficio__viatura",
            "prestacao__oficio__motorista",
        )
        .prefetch_related(
            Prefetch(
                "prestacao__oficio__roteiro__trechos",
                queryset=RoteiroTrecho.objects.select_related(
                    "origem_cidade", "origem_estado", "destino_cidade", "destino_estado"
                ).order_by("ordem"),
            ),
            Prefetch(
                "prestacao__servidores_prestacao",
                queryset=PrestacaoServidor.objects.select_related(
                    "servidor", "servidor__cargo", "servidor__unidade"
                ).order_by("pk"),
            ),
            "documentos_anexos",
            "prestacao__documentos_anexos",
            "prestacao__relatorio_tecnico",
            "prestacao__diario_bordo",
        )
        .filter(prestacao__oficio__cancelado=False)
        .order_by(*order_fields)
    )

    if status:
        queryset = queryset.filter(status=status)

    if q:
        query = q.strip()
        query_unaccent = remove_accents(query)
        filters = (
            Q(servidor__nome__unaccent__icontains=query_unaccent)
            | Q(prestacao__oficio__protocolo__unaccent__icontains=query_unaccent)
            | Q(numero_solicitacao__unaccent__icontains=query_unaccent)
            | Q(servidor__cargo__nome__unaccent__icontains=query_unaccent)
        )
        if query.isdigit():
            filters |= Q(prestacao__oficio__numero=int(query)) | Q(prestacao__oficio__ano=int(query))
        queryset = queryset.filter(filters).distinct()

    if viagem_de:
        try:
            queryset = queryset.filter(
                prestacao__oficio__roteiro__isnull=False,
                prestacao__oficio__roteiro__saida_dt__date__gte=viagem_de,
            )
        except Exception:
            pass
    if viagem_ate:
        try:
            queryset = queryset.filter(
                prestacao__oficio__roteiro__isnull=False,
                prestacao__oficio__roteiro__saida_dt__date__lte=viagem_ate,
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
    """Servidores da aba pedida (um card por servidor), com filtros aplicados."""
    base = _base_servidores(
        q=q, status=status, viagem_de=viagem_de, viagem_ate=viagem_ate, sort=sort
    )
    return base.filter(_q_da_aba(normalizar_aba(aba)))


def contar_por_aba(
    q: str | None = None,
    status: str | None = None,
    viagem_de: str | None = None,
    viagem_ate: str | None = None,
) -> dict:
    """Total de servidores em cada aba, respeitando os filtros de busca ativos."""
    base = _base_servidores(q=q, status=status, viagem_de=viagem_de, viagem_ate=viagem_ate)
    return {
        aba: base.filter(_q_da_aba(aba)).count()
        for aba in (ABA_NAO_LIBERADAS, ABA_LIBERADAS, ABA_ARQUIVADOS, ABA_FINALIZADOS)
    }
