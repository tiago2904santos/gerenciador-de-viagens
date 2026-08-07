from django.db.models import Case
from django.db.models import Count
from django.db.models import Exists
from django.db.models import IntegerField
from django.db.models import OuterRef
from django.db.models import Prefetch
from django.db.models import Q
from django.db.models import Value
from django.db.models import When
from django.shortcuts import get_object_or_404

from cadastros.models import Cidade, Estado
from core.normalizers import remove_accents
from core.tenancy import filter_queryset_by_area

from .models import Roteiro
from .models import RoteiroDestino
from .models import RoteiroTrecho


def listar_roteiros(q=None, status=None):
    trechos_qs = (
        RoteiroTrecho.objects.select_related(
            "origem_estado",
            "origem_cidade",
            "origem_cidade__estado",
            "destino_estado",
            "destino_cidade",
            "destino_cidade__estado",
        )
        .order_by("ordem", "pk")
    )
    queryset = (
        filter_queryset_by_area(Roteiro.objects)
        .select_related("origem_estado", "origem_cidade", "origem_cidade__estado")
        .prefetch_related(
            "destinos__cidade",
            "destinos__estado",
            Prefetch("trechos", queryset=trechos_qs),
        )
        # `DB-09`: descarta o rascunho **completamente** vazio — sem destino, sem
        # trecho, sem saida e sem origem. A regra e' a mesma de antes; o que mudou
        # e' como o banco a responde.
        #
        # Antes: `Count('trechos')` + `Count('destinos')` e `.exclude(...=0)`. Para
        # contar, o Postgres precisa agrupar tudo primeiro, e o `GroupAggregate`
        # varria as duas tabelas filhas inteiras antes de a pagina existir. Medido
        # com 20.000 roteiros em tres areas: 79,0 ms e 7.817 buffers para entregar
        # 15 cards.
        #
        # `Exists` correlacionado nao conta: pergunta se ha **alguma** linha e para
        # na primeira. 27,0 ms e 659 buffers — e com o indice de ordenacao abaixo,
        # 8,9 ms.
        #
        # **Cuidado com a semantica**: `.exclude()` com quatro argumentos e
        # `NOT (a E b E c E d)`, nao quatro exclusoes. Um roteiro que tenha
        # qualquer um dos quatro fica na lista. O `test_lista_de_roteiros_db09`
        # trava essa tabela-verdade caso a caso.
        .exclude(
            ~Exists(RoteiroDestino.objects.filter(roteiro=OuterRef("pk")))
            & ~Exists(RoteiroTrecho.objects.filter(roteiro=OuterRef("pk")))
            & Q(saida_dt__isnull=True)
            & Q(origem_cidade__isnull=True)
        )
        .order_by("-updated_at")
    )
    if status:
        queryset = queryset.filter(status=status)
    if q:
        q_unaccent = remove_accents(q)
        queryset = queryset.filter(
            Q(origem_cidade__nome__unaccent__icontains=q_unaccent)
            | Q(origem_estado__sigla__unaccent__icontains=q_unaccent)
            | Q(origem_estado__nome__unaccent__icontains=q_unaccent)
            | Q(destinos__cidade__nome__unaccent__icontains=q_unaccent)
            | Q(destinos__estado__sigla__unaccent__icontains=q_unaccent)
            | Q(observacoes__unaccent__icontains=q_unaccent)
            | Q(quantidade_diarias__icontains=q)
        ).distinct()
    return queryset


def get_roteiro_by_id(pk):
    return get_object_or_404(
        filter_queryset_by_area(Roteiro.objects).select_related(
            "origem_estado",
            "origem_cidade",
            "origem_cidade__estado",
        ).prefetch_related(
            "destinos__cidade",
            "destinos__estado",
            "trechos__origem_estado",
            "trechos__origem_cidade",
            "trechos__destino_estado",
            "trechos__destino_cidade",
        ),
        pk=pk,
    )


def listar_trechos_do_roteiro(roteiro):
    return (
        roteiro.trechos.select_related(
            "origem_estado",
            "origem_cidade",
            "destino_estado",
            "destino_cidade",
        )
        .order_by("ordem", "pk")
    )


def get_trecho_by_id(pk):
    return get_object_or_404(
        RoteiroTrecho.objects.select_related(
            "roteiro",
            "origem_estado",
            "origem_cidade",
            "destino_estado",
            "destino_cidade",
        ),
        pk=pk,
    )


def listar_estados_para_select():
    return Estado.objects.order_by("nome")


def listar_cidades_para_select(estado_id=None, q=None):
    if not estado_id:
        return Cidade.objects.none()
    qs = Cidade.objects.filter(estado_id=estado_id).select_related("estado").order_by("nome")
    if q and str(q).strip():
        qs = qs.filter(nome__unaccent__icontains=remove_accents(str(q).strip()))
    return qs


def _anotar_e_filtrar_roteiros_completos(qs):
    """So deixa passar roteiros totalmente preenchidos: sede, destino, pelo menos
    um trecho de ida com saida/chegada e retorno com saida/chegada. Um roteiro
    pela metade nunca deve aparecer como opcao de reuso."""
    return qs.annotate(
        qtd_destinos=Count("destinos", distinct=True),
        qtd_trechos_ida_completos=Count(
            "trechos",
            filter=Q(
                trechos__tipo=RoteiroTrecho.TIPO_IDA,
                trechos__saida_dt__isnull=False,
                trechos__chegada_dt__isnull=False,
            ),
            distinct=True,
        ),
    ).filter(
        origem_cidade__isnull=False,
        origem_estado__isnull=False,
        retorno_saida_dt__isnull=False,
        retorno_chegada_dt__isnull=False,
        qtd_destinos__gt=0,
        qtd_trechos_ida_completos__gt=0,
    )


def queryset_roteiros_avulsos_para_mapa_rotas(limit=50):
    """Roteiros avulsos totalmente preenchidos (esconde rascunhos incompletos criados pelo wizard)."""
    return (
        _anotar_e_filtrar_roteiros_completos(
            filter_queryset_by_area(Roteiro.objects).filter(tipo=Roteiro.TIPO_AVULSO)
        )
        .select_related("origem_cidade", "origem_estado")
        .prefetch_related(
            "destinos",
            "destinos__estado",
            "destinos__cidade",
            "trechos",
            "trechos__origem_estado",
            "trechos__origem_cidade",
            "trechos__destino_estado",
            "trechos__destino_cidade",
        )
        .order_by("-pk")[:limit]
    )


def queryset_roteiros_reutilizaveis_para_evento(evento=None, limit=50, excluir_pk=None):
    """Roteiros avulsos (reuso global) + roteiros do evento atual (Etapa 2 ou ja usados por
    algum oficio do evento), priorizando o roteiro do evento no topo da lista. Em ambos os
    casos, so entram roteiros totalmente preenchidos (ver `_anotar_e_filtrar_roteiros_completos`).

    `excluir_pk` tira da lista o roteiro que ja esta vinculado ao documento em edicao
    (nao faz sentido oferecer "reaproveitar" o proprio roteiro atual).
    """
    condicao = Q(tipo=Roteiro.TIPO_AVULSO)
    if evento is not None:
        condicao |= Q(evento=evento) | Q(oficios__evento=evento)

    qs = (
        _anotar_e_filtrar_roteiros_completos(filter_queryset_by_area(Roteiro.objects).filter(condicao))
        .distinct()
        .select_related("origem_cidade", "origem_estado")
        .prefetch_related(
            "destinos",
            "destinos__estado",
            "destinos__cidade",
            "trechos",
            "trechos__origem_estado",
            "trechos__origem_cidade",
            "trechos__destino_estado",
            "trechos__destino_cidade",
        )
    )
    if excluir_pk:
        qs = qs.exclude(pk=excluir_pk)
    if evento is not None:
        qs = qs.annotate(
            is_do_evento=Case(
                When(Q(evento=evento) | Q(oficios__evento=evento), then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        ).order_by("-is_do_evento", "-pk")
    else:
        qs = qs.order_by("-pk")
    return qs[:limit]


def obter_cidades_origem_destino_estimativa(origem_id, destino_id):
    origem = Cidade.objects.filter(pk=origem_id).select_related("estado").first()
    destino = Cidade.objects.filter(pk=destino_id).select_related("estado").first()
    return origem, destino
