"""Consultas de leitura do app de Termos (`P-01`).

Segue `docs/PADRAO_SELECTORS.md`. As consultas foram **movidas** da view, não
reescritas: os mesmos `select_related`/`prefetch_related`, o mesmo recorte por
área e a mesma ordenação. O custo em queries de cada tela está travado em
`termos/tests/test_orcamento_de_queries.py`.
"""

from __future__ import annotations

from django.db.models import Exists
from django.db.models import OuterRef
from django.db.models import Prefetch
from django.db.models import Q
from django.shortcuts import get_object_or_404

from cadastros.models import Servidor
from core.normalizers import remove_accents
from core.tenancy import filter_queryset_by_area

from .models import TermoAutorizacao


def prefetch_servidores_efetivos():
    """Prefetch de `servidores` na forma exata que `servidores_efetivos()` usa.

    O cache do prefetch só dispensa a consulta por linha se trouxer o mesmo
    `select_related` e a mesma ordenação da primeira cascata de
    `TermoAutorizacao.servidores_efetivos()`; com um `prefetch_related("servidores")`
    genérico o model recebe os servidores mas perde cargo e unidade, e cada
    acesso volta a consultar (`NOVO-08`).

    É função e não constante de módulo de propósito: reaproveitar a mesma
    instância de `Prefetch` entre querysets diferentes é fonte conhecida de erro.
    """
    return Prefetch(
        "servidores",
        # `BE-09`: `all_objects` — quem delimita aqui é a própria M2M `servidores` do
        # termo, não a área ativa. Recortado, o termo renderizado fora da sua área
        # perderia os servidores em silêncio, e o `NOVO-08` (que este prefetch existe
        # para resolver) voltaria como lista vazia em vez de N+1.
        queryset=Servidor.all_objects.select_related("cargo", "unidade").order_by("nome"),
    )


def anotar_composicao(termos):
    """Anota se cada fonte de servidores do termo tem conteudo.

    `TermoAutorizacao.servidores_efetivos()` cai em cascata — servidores
    proprios, senao os do oficio, senao os dos oficios do evento — e
    `viatura_efetiva()` faz o mesmo com a viatura. Para dividir a lista no
    banco (em Python quebraria paginacao e contagem) cada fonte vira um
    booleano via Exists, que nega de forma previsivel; `servidores__isnull`
    direto no filtro passaria por join m2m e descartaria linhas nos dois lados.
    """
    from oficios.models import Oficio

    through = TermoAutorizacao.servidores.through
    return termos.annotate(
        _tem_servidor_proprio=Exists(
            through.objects.filter(termoautorizacao_id=OuterRef("pk"))
        ),
        _tem_servidor_oficio=Exists(
            Oficio.objects.filter(
                pk=OuterRef("oficio_id"), servidores_termo_autorizacao__isnull=False
            )
        ),
        _tem_servidor_evento=Exists(
            Oficio.objects.filter(evento_id=OuterRef("evento_id")).filter(
                Q(servidores_termo_autorizacao__isnull=False) | Q(servidores__isnull=False)
            )
        ),
    )


# Termo "simples": nenhuma fonte de servidor e nenhuma viatura efetiva.
Q_SIMPLES = Q(
    _tem_servidor_proprio=False,
    _tem_servidor_oficio=False,
    _tem_servidor_evento=False,
    viatura__isnull=True,
    oficio__viatura__isnull=True,
)


def listar_termos(q=None, q_digits=None, simples=None):
    """Lista de termos da área, com a busca livre da tela.

    `q_digits` são os dígitos extraídos de `q` pela view — número e protocolo do
    ofício aceitam busca só por dígito.
    """
    termos = (
        filter_queryset_by_area(TermoAutorizacao.objects)
        .select_related(
            "oficio",
            "destino_estado",
            "destino_cidade",
            "viatura",
        )
        .prefetch_related(prefetch_servidores_efetivos())
        .order_by("-created_at")
    )
    if simples is not None:
        termos = anotar_composicao(termos)
        termos = termos.filter(Q_SIMPLES) if simples else termos.exclude(Q_SIMPLES)
    if not q:
        return termos

    q_unaccent = remove_accents(q)
    query = (
        Q(destino_cidade__nome__unaccent__icontains=q_unaccent)
        | Q(destino_cidade__uf__unaccent__icontains=q_unaccent)
        | Q(destino_estado__nome__unaccent__icontains=q_unaccent)
        | Q(destino_estado__sigla__unaccent__icontains=q_unaccent)
        | Q(oficio__numero__icontains=q)
        | Q(oficio__protocolo__icontains=q)
        | Q(oficio__servidores__nome__unaccent__icontains=q_unaccent)
        | Q(oficio__servidores_termo_autorizacao__nome__unaccent__icontains=q_unaccent)
        | Q(servidores__nome__unaccent__icontains=q_unaccent)
        | Q(viatura__placa__icontains=q)
        | Q(viatura__modelo__unaccent__icontains=q_unaccent)
        | Q(oficio__viatura__placa__icontains=q)
        | Q(oficio__viatura__modelo__unaccent__icontains=q_unaccent)
    )
    if q_digits:
        query |= Q(oficio__protocolo__icontains=q_digits) | Q(oficio__numero__icontains=q_digits)
    return termos.filter(query).distinct()


def queryset_termo_detalhe():
    return filter_queryset_by_area(TermoAutorizacao.objects).select_related(
        "oficio",
        "oficio__roteiro",
        "destino_estado",
        "destino_cidade",
        "viatura",
    ).prefetch_related(prefetch_servidores_efetivos())


def get_termo_by_id(pk):
    return get_object_or_404(queryset_termo_detalhe(), pk=pk)


def get_servidor_para_termo(pk):
    """Servidor da área, sem `select_related`.

    Existe `cadastros.selectors.get_servidor_by_id`, mas ele traz cargo e
    unidade por junção. Aqui o objeto só serve para conferir vínculo e nomear o
    PDF; trocar um pelo outro seria otimizar, e o `P-01` é mover.
    """
    return get_object_or_404(filter_queryset_by_area(Servidor.objects), pk=pk)


def get_servidor_do_termo_do_oficio(oficio, pk):
    """Servidor entre os marcados para termo naquele ofício — 404 se não estiver."""
    return get_object_or_404(oficio.servidores_termo_autorizacao.all(), pk=pk)
