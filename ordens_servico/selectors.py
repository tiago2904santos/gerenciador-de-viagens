"""Consultas de leitura do app de Ordens de Serviço (`P-01`).

Segue `docs/PADRAO_SELECTORS.md`. Consultas **movidas** da view, não reescritas:
mesmos `select_related`/`prefetch_related`, mesmo recorte por área, mesma
ordenação. O custo em queries está travado em
`ordens_servico/tests/test_orcamento_de_queries.py`.
"""

from __future__ import annotations

from django.db.models import OuterRef
from django.db.models import Q
from django.shortcuts import get_object_or_404

from core import documento_abas as tabs
from core.normalizers import remove_accents
from core.tenancy import filter_queryset_by_area
from prestacoes_contas.models import PrestacaoServidor

from .models import OrdemServico


_SORT_MAP = {
    "numero_desc": ("-ano", "-numero"),
    "numero_asc": ("ano", "numero"),
    "criacao_desc": ("-created_at",),
    "criacao_asc": ("created_at",),
    "viagem_asc": ("data_evento_inicio", "-ano", "-numero"),
    "viagem_desc": ("-data_evento_inicio", "-ano", "-numero"),
}


def listar_ordens_servico(q=None, viagem_de=None, viagem_ate=None, sort=None):
    """Lista de OS já anotada com a finalização das prestações.

    A anotação vem junto porque é a subconsulta que decide em qual aba cada OS
    cai; a view continua dona de *qual* aba mostrar.
    """
    ordens = filter_queryset_by_area(OrdemServico.objects).prefetch_related(
        "destinos__estado",
        "servidores__cargo",
        "servidores__unidade",
        "oficios",
    )
    if q:
        q_unaccent = remove_accents(q)
        filters = (
            Q(motivo__unaccent__icontains=q_unaccent)
            | Q(destinos__nome__unaccent__icontains=q_unaccent)
            | Q(servidores__nome__unaccent__icontains=q_unaccent)
        )
        if q.isdigit():
            filters |= Q(numero=int(q)) | Q(ano=int(q)) | Q(oficios__numero=int(q))
        ordens = ordens.filter(filters).distinct()

    if viagem_de:
        ordens = ordens.filter(
            Q(data_evento_fim__gte=viagem_de) | Q(data_evento_fim__isnull=True)
        )
    if viagem_ate:
        ordens = ordens.filter(data_evento_inicio__lte=viagem_ate)

    ordens = ordens.order_by(*_SORT_MAP.get(sort or "numero_desc", _SORT_MAP["numero_desc"]))

    # Finalizado = todas as prestações dos ofícios (não cancelados) vinculados
    # à OS já finalizadas.
    sub = PrestacaoServidor.objects.filter(
        prestacao__oficio__ordens_servico=OuterRef("pk"),
        prestacao__oficio__cancelado=False,
    )
    return tabs.anotar_finalizacao(ordens, sub, sub.filter(finalizada=False))


def queryset_ordem_servico_detalhe():
    return (
        filter_queryset_by_area(OrdemServico.objects)
        .select_related(
            "motorista_equipe",
            "tecnico_equipe",
            "apoio_montagem",
            "apoio_escolta",
            "coordenador_cerimonial",
            "apoio_cerimonial",
            "apoio_preparacao",
        )
        .prefetch_related("destinos__estado", "servidores", "oficios")
    )


def get_ordem_servico_by_id(pk):
    return get_object_or_404(queryset_ordem_servico_detalhe(), pk=pk)
