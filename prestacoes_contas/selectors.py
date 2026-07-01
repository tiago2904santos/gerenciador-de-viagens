from django.db.models import Prefetch
from django.db.models import Q
from django.utils import timezone

from cadastros.models import Servidor
from core.normalizers import remove_accents
from roteiros.models import RoteiroTrecho

from .models import PrestacaoContas


# Espelha a ordenação da lista de ofícios, adaptando os campos para a
# prestação (criação própria e viagem via roteiro do ofício).
_SORT_MAP = {
    "criacao_desc": ["-criado_em"],
    "criacao_asc":  ["criado_em"],
    "viagem_asc":   ["oficio__roteiro__saida_dt",  "-criado_em"],
    "viagem_desc":  ["-oficio__roteiro__saida_dt", "-criado_em"],
    "servidor_asc":  ["servidor__nome"],
    "servidor_desc": ["-servidor__nome"],
}


def listar_prestacoes(
    q: str | None = None,
    status: str | None = None,
    temporal: str | None = None,
    viagem_de: str | None = None,
    viagem_ate: str | None = None,
    sort: str | None = None,
):
    order_fields = _SORT_MAP.get(sort or "criacao_desc", ["-criado_em"])
    queryset = (
        PrestacaoContas.objects.select_related(
            "oficio",
            "oficio__roteiro",
            "oficio__roteiro__origem_cidade",
            "oficio__roteiro__origem_estado",
            "oficio__viatura",
            "servidor",
            "servidor__cargo",
            "servidor__unidade",
        )
        .prefetch_related(
            Prefetch(
                "oficio__roteiro__trechos",
                queryset=RoteiroTrecho.objects.select_related(
                    "origem_cidade", "origem_estado", "destino_cidade", "destino_estado"
                ).order_by("ordem"),
            ),
            "relatorio_tecnico",
            "diario_bordo",
        )
        .order_by(*order_fields)
    )

    if status:
        queryset = queryset.filter(status=status)

    if q:
        query = q.strip()
        query_unaccent = remove_accents(query)
        filters = (
            Q(servidor__nome__unaccent__icontains=query_unaccent)
            | Q(oficio__protocolo__unaccent__icontains=query_unaccent)
            | Q(numero_solicitacao__unaccent__icontains=query_unaccent)
            | Q(servidor__cargo__nome__unaccent__icontains=query_unaccent)
        )
        if query.isdigit():
            filters |= Q(oficio__numero=int(query)) | Q(oficio__ano=int(query))
        queryset = queryset.filter(filters).distinct()

    if temporal:
        today = timezone.localdate()
        if temporal == "futuro":
            queryset = queryset.filter(
                oficio__roteiro__isnull=False,
                oficio__roteiro__saida_dt__date__gt=today,
            )
        elif temporal == "andamento":
            queryset = queryset.filter(
                oficio__roteiro__isnull=False,
                oficio__roteiro__saida_dt__date__lte=today,
            ).filter(
                Q(oficio__roteiro__retorno_chegada_dt__date__gte=today)
                | Q(oficio__roteiro__retorno_chegada_dt__isnull=True, oficio__roteiro__chegada_dt__date__gte=today)
                | Q(oficio__roteiro__retorno_chegada_dt__isnull=True, oficio__roteiro__chegada_dt__isnull=True)
            )
        elif temporal == "passado":
            queryset = queryset.filter(oficio__roteiro__isnull=False).filter(
                Q(oficio__roteiro__retorno_chegada_dt__date__lt=today)
                | Q(oficio__roteiro__retorno_chegada_dt__isnull=True, oficio__roteiro__chegada_dt__date__lt=today)
            )

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
