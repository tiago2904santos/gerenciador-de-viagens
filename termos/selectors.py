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




def listar_termos(q=None, q_digits=None):
    """Lista de termos da área, com a busca livre da tela.

    `q_digits` são os dígitos extraídos de `q` pela view — número e protocolo do
    ofício aceitam busca só por dígito.
    """
    termos = (
        filter_queryset_by_area(TermoAutorizacao.objects)
        .select_related(
            "oficio",
            # O roteiro do ofício entra junto porque o PERÍODO do termo pode ser
            # dele (`periodo_efetivo`): sem isto, todo termo sem datas próprias
            # custava uma consulta a mais só para o selo de situação saber se a
            # viagem já foi.
            "oficio__roteiro",
            "destino_estado",
            "destino_cidade",
            "viatura",
        )
        .prefetch_related(prefetch_servidores_efetivos())
        .order_by("-created_at")
    )
    if not q:
        return termos

    q_unaccent = remove_accents(q)
    # `DB-11`: as tres M2M abaixo estavam no mesmo `OR` das colunas escalares.
    # O PostgreSQL precisava expandir cada termo pelos tres relacionamentos antes
    # de filtrar e aplicar `DISTINCT` (20 mil termos viravam ~60 mil linhas na
    # medicao do catálogo). `Exists` preserva a semantica sem multiplicar a linha
    # externa; cada origem pode ser planejada de forma independente.
    from oficios.models import Oficio

    servidores_do_termo = TermoAutorizacao.servidores.through.objects.filter(
        termoautorizacao_id=OuterRef("pk"),
        servidor__nome__unaccent__icontains=q_unaccent,
    )
    servidores_do_oficio = Oficio.servidores.through.objects.filter(
        oficio_id=OuterRef("oficio_id"),
        servidor__nome__unaccent__icontains=q_unaccent,
    )
    servidores_do_termo_do_oficio = Oficio.servidores_termo_autorizacao.through.objects.filter(
        oficio_id=OuterRef("oficio_id"),
        servidor__nome__unaccent__icontains=q_unaccent,
    )
    termos = termos.annotate(
        _busca_servidor_do_termo=Exists(servidores_do_termo),
        _busca_servidor_do_oficio=Exists(servidores_do_oficio),
        _busca_servidor_do_termo_do_oficio=Exists(servidores_do_termo_do_oficio),
    )
    query = (
        Q(destino_cidade__nome__unaccent__icontains=q_unaccent)
        | Q(destino_cidade__uf__unaccent__icontains=q_unaccent)
        | Q(destino_estado__nome__unaccent__icontains=q_unaccent)
        | Q(destino_estado__sigla__unaccent__icontains=q_unaccent)
        | Q(oficio__numero__icontains=q)
        | Q(oficio__protocolo__icontains=q)
        | Q(_busca_servidor_do_termo=True)
        | Q(_busca_servidor_do_oficio=True)
        | Q(_busca_servidor_do_termo_do_oficio=True)
        | Q(viatura__placa__icontains=q)
        | Q(viatura__modelo__unaccent__icontains=q_unaccent)
        | Q(oficio__viatura__placa__icontains=q)
        | Q(oficio__viatura__modelo__unaccent__icontains=q_unaccent)
    )
    if q_digits:
        query |= Q(oficio__protocolo__icontains=q_digits) | Q(oficio__numero__icontains=q_digits)
    return termos.filter(query)


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
