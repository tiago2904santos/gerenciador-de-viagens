from django.db.models import Case
from django.db.models import Count
from django.db.models import IntegerField
from django.db.models import Prefetch
from django.db.models import Q
from django.db.models import Value
from django.db.models import When
from django.shortcuts import get_object_or_404

from cadastros.models import Cidade, Estado
from core.normalizers import remove_accents

from .models import Roteiro
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
        Roteiro.objects.select_related("origem_estado", "origem_cidade", "origem_cidade__estado")
        .prefetch_related(
            "destinos__cidade",
            "destinos__estado",
            Prefetch("trechos", queryset=trechos_qs),
        )
        .annotate(
            trechos_count=Count("trechos", distinct=True),
            destinos_count=Count("destinos", distinct=True),
        )
        .exclude(
            destinos_count=0,
            trechos_count=0,
            saida_dt__isnull=True,
            origem_cidade__isnull=True,
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
        Roteiro.objects.select_related(
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


def queryset_roteiros_avulsos_para_mapa_rotas(limit=50):
    """Roteiros avulsos com destinos ou trechos cadastrados (esconde rascunhos vazios criados pelo wizard)."""
    return (
        Roteiro.objects.filter(tipo=Roteiro.TIPO_AVULSO)
        .annotate(
            qtd_destinos=Count("destinos", distinct=True),
            qtd_trechos=Count("trechos", distinct=True),
        )
        .filter(Q(qtd_destinos__gt=0) | Q(qtd_trechos__gt=0))
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
    algum oficio do evento), priorizando o roteiro do evento no topo da lista.

    `excluir_pk` tira da lista o roteiro que ja esta vinculado ao documento em edicao
    (nao faz sentido oferecer "reaproveitar" o proprio roteiro atual).
    """
    condicao = Q(tipo=Roteiro.TIPO_AVULSO)
    if evento is not None:
        condicao |= Q(evento=evento) | Q(oficios__evento=evento)

    qs = (
        Roteiro.objects.filter(condicao)
        .annotate(
            qtd_destinos=Count("destinos", distinct=True),
            qtd_trechos=Count("trechos", distinct=True),
        )
        .filter(Q(qtd_destinos__gt=0) | Q(qtd_trechos__gt=0))
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
