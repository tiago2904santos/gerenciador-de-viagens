from django.db.models import Exists
from django.db.models import OuterRef
from django.db.models import Prefetch
from django.db.models import Q

from core.normalizers import remove_accents
from core.tenancy import filter_queryset_by_area
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
# "Liberadas" = todo servidor do ofício já tem a Data de liberação das
# diárias preenchida (o aviso de liberação já pode ser enviado a todos);
# basta um servidor sem essa data para a prestação ficar em "Não liberadas".
# "Arquivados" e "Finalizados" independem disso e têm precedência (uma
# prestação finalizada some das outras abas mesmo se ainda não liberada).
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
    """Filtro que define quais prestações pertencem a cada aba (mutuamente exclusivas)."""
    if aba == ABA_FINALIZADOS:
        return Q(finalizada=True)
    if aba == ABA_ARQUIVADOS:
        return Q(arquivada=True, finalizada=False)

    # Liberadas e Não liberadas são "ativas" (nem arquivadas, nem finalizadas).
    ativa = Q(arquivada=False, finalizada=False)
    tem_servidor = Q(Exists(PrestacaoServidor.objects.filter(prestacao=OuterRef("pk"))))
    tem_pendente = Q(Exists(
        PrestacaoServidor.objects.filter(
            prestacao=OuterRef("pk"), data_liberacao_diarias__isnull=True
        )
    ))
    if aba == ABA_LIBERADAS:
        return ativa & tem_servidor & ~tem_pendente
    # Não liberadas: ainda sem nenhum servidor cadastrado, ou algum servidor
    # sem a data de liberação preenchida.
    return ativa & (~tem_servidor | tem_pendente)


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
        filter_queryset_by_area(PrestacaoContas.objects)
        .select_related(
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
            "documentos_anexos",
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
        for aba in (ABA_NAO_LIBERADAS, ABA_LIBERADAS, ABA_ARQUIVADOS, ABA_FINALIZADOS)
    }
