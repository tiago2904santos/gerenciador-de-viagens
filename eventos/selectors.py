"""Consultas de leitura do app de Eventos (`P-01`).

Segue `docs/PADRAO_SELECTORS.md` e o que já é praticado em `oficios/selectors.py`
e `roteiros/selectors.py`: a view recebe queryset pronto, com `select_related` /
`prefetch_related` e ordenação já decididos aqui.

As consultas foram **movidas**, não reescritas. O isolamento por área
(`filter_queryset_by_area`) acompanhou cada uma; onde a consulta original não
filtrava por área — os termos e roteiros ligados a um evento, que já herdam o
recorte do próprio evento — ela continua sem filtrar, porque acrescentar o filtro
mudaria o que a tela mostra.
"""

from __future__ import annotations

from django.db.models import OuterRef
from django.db.models import Q
from django.shortcuts import get_object_or_404

from core import documento_abas as tabs
from core.normalizers import remove_accents
from core.tenancy import filter_queryset_by_area
from prestacoes_contas.models import PrestacaoServidor
from roteiros.models import Roteiro
from termos.models import TermoAutorizacao

from .models import Evento
from .models import EventoAnexo
from .models import EventoDocumentoSolicitacao
from .models import TipoEvento


_SORT_MAP = {
    "numero_desc": ("-data_inicio", "-criado_em"),
    "numero_asc": ("data_inicio", "criado_em"),
    "criacao_desc": ("-criado_em",),
    "criacao_asc": ("criado_em",),
    "viagem_asc": ("data_inicio", "-criado_em"),
    "viagem_desc": ("-data_inicio", "-criado_em"),
}


def _queryset_eventos_lista():
    return filter_queryset_by_area(Evento.objects).select_related(
        "unidade_responsavel", "responsavel"
    ).prefetch_related(
        "anexos",
        "oficios",
        "oficios__servidores",
        "oficios__servidores__cargo",
        "oficios__servidores__unidade",
        "oficios__servidores_termo_autorizacao",
        "oficios__viatura",
        "oficios__motorista",
        "oficios__roteiro",
        "oficios__roteiro__origem_cidade",
        "oficios__roteiro__destinos__cidade__estado",
        "oficios__roteiro__trechos",
        "roteiros",
        "roteiros__origem_cidade",
        "planos_trabalho",
        "planos_trabalho__programa",
        "planos_trabalho__destino_cidade__estado",
        "ordens_servico",
        "ordens_servico__destinos__estado",
        "documentos_solicitacao",
    )


def listar_eventos(q=None, viagem_de=None, viagem_ate=None, sort=None):
    """Lista de eventos já anotada com a finalização das prestações.

    A anotação entra aqui, e não na view, porque é a subconsulta que decide em
    qual aba cada evento cai — e era a última consulta do app a montar ORM na
    camada de apresentação. A view continua dona de qual aba mostrar.
    """
    eventos = _queryset_eventos_lista()
    if q:
        q_unaccent = remove_accents(q)
        eventos = eventos.filter(
            Q(titulo__unaccent__icontains=q_unaccent)
            | Q(descricao__unaccent__icontains=q_unaccent)
            | Q(motivo__unaccent__icontains=q_unaccent)
            | Q(destino_cidade__unaccent__icontains=q_unaccent)
            | Q(destino_uf__unaccent__icontains=q_unaccent)
            | Q(responsavel__nome__unaccent__icontains=q_unaccent)
            | Q(unidade_responsavel__nome__unaccent__icontains=q_unaccent)
        )
    if viagem_de:
        eventos = eventos.filter(Q(data_fim__gte=viagem_de) | Q(data_fim__isnull=True))
    if viagem_ate:
        eventos = eventos.filter(data_inicio__lte=viagem_ate)

    eventos = eventos.order_by(*_SORT_MAP.get(sort or "criacao_desc", _SORT_MAP["criacao_desc"]))

    # Finalizado = todas as prestações dos ofícios (não cancelados) do evento
    # já finalizadas.
    sub = PrestacaoServidor.objects.filter(
        prestacao__oficio__evento=OuterRef("pk"), prestacao__oficio__cancelado=False
    )
    return tabs.anotar_finalizacao(eventos, sub, sub.filter(finalizada=False))


def queryset_evento_detalhe():
    return filter_queryset_by_area(Evento.objects).select_related(
        "unidade_responsavel", "responsavel"
    ).prefetch_related(
        "oficios",
        "oficios__servidores",
        "oficios__servidores_termo_autorizacao",
        "oficios__roteiro__destinos__cidade__estado",
        "oficios__roteiro__trechos",
        "oficios__viatura",
        "oficios__motorista",
        "roteiros",
        "roteiros__destinos__cidade__estado",
        "roteiros__trechos",
        "planos_trabalho",
        "planos_trabalho__programa",
        "planos_trabalho__destino_cidade__estado",
        "planos_trabalho__coordenador_adm__cargo",
        "ordens_servico",
        "ordens_servico__destinos__estado",
        "ordens_servico__servidores",
        "ordens_servico__oficios",
        "termos_autorizacao",
        "termos_autorizacao__oficio",
        "termos_autorizacao__destino_cidade__estado",
        "termos_autorizacao__viatura",
        "termos_autorizacao__servidores",
    )


def get_evento_by_id(pk):
    return get_object_or_404(queryset_evento_detalhe(), pk=pk)


def listar_tipos_evento(q=None):
    tipos = filter_queryset_by_area(TipoEvento.objects).all()
    if q:
        tipos = tipos.filter(nome__unaccent__icontains=remove_accents(q))
    return tipos


def get_tipo_evento_by_id(pk):
    return get_object_or_404(filter_queryset_by_area(TipoEvento.objects), pk=pk)


def listar_roteiros_do_evento(evento):
    """Roteiros ligados ao evento: direto (`roteiro.evento`) ou por um ofício dele."""
    return (
        Roteiro.objects.filter(Q(evento=evento) | Q(oficios__evento=evento))
        .distinct()
        .order_by("-created_at")
        .prefetch_related("destinos__cidade__estado", "trechos")
    )


def listar_termos_genericos_do_evento(evento):
    """Termo(s) do evento sem ofício — os que a tela mostra no topo."""
    return (
        TermoAutorizacao.objects.filter(evento=evento, oficio__isnull=True)
        .select_related("destino_cidade__estado", "destino_estado", "viatura")
        .prefetch_related("servidores")
        .order_by("-created_at")
    )


def listar_termos_do_evento(evento):
    """Todos os termos do evento, diretos ou via ofício."""
    return (
        TermoAutorizacao.objects.filter(Q(evento=evento) | Q(oficio__evento=evento))
        .select_related("destino_cidade__estado", "destino_estado", "viatura", "oficio")
        .prefetch_related("servidores")
        .order_by("-created_at")
    )


def existe_termo_do_evento(evento) -> bool:
    return TermoAutorizacao.objects.filter(Q(evento=evento) | Q(oficio__evento=evento)).exists()


def buscar_documento_solicitacao(evento, pk):
    """Devolve `None` quando não existe — quem chama decide a mensagem."""
    return EventoDocumentoSolicitacao.objects.filter(pk=pk, evento=evento).first()


def get_documento_solicitacao_by_id(evento, pk):
    return get_object_or_404(EventoDocumentoSolicitacao, pk=pk, evento=evento)


def get_evento_anexo_by_id(evento, pk):
    return get_object_or_404(EventoAnexo, pk=pk, evento=evento)
