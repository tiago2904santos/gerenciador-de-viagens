"""Consultas de leitura do app de Plano de Trabalho (`P-01`).

Segue `docs/PADRAO_SELECTORS.md`. Consultas **movidas** da view, não reescritas:
mesmos `select_related`/`prefetch_related`, mesmo recorte por área, mesma
ordenação. O custo em queries está travado em
`planos_trabalho/tests/test_orcamento_de_queries.py`.

Fora daqui, de propósito: `catalog_views.py`. As 13 consultas de lá são de
catálogo — território do `P-02` (`core/catalog.py`), que vai apagar o arquivo
inteiro. Movê-las agora seria trabalho jogado fora.
"""

from __future__ import annotations

from django.db.models import OuterRef
from django.db.models import Q
from django.shortcuts import get_object_or_404

from cadastros.models import Cargo
from cadastros.models import Unidade
from core import documento_abas as tabs
from core.normalizers import remove_accents
from core.tenancy import filter_queryset_by_area
from core.tenancy import get_current_area
from prestacoes_contas.models import PrestacaoServidor

from .models import AtividadePlanoTrabalho
from .models import EventoPlano
from .models import HorarioAtendimento
from .models import PlanoTrabalho
from .models import PresetAtividadesPlanoTrabalho
from .models import ProgramaSolicitante


_SORT_MAP = {
    "numero_desc": ("-ano", "-numero", "-created_at"),
    "numero_asc": ("ano", "numero", "created_at"),
    "criacao_desc": ("-created_at",),
    "criacao_asc": ("created_at",),
    "viagem_asc": ("data_evento_inicio", "-ano", "-numero"),
    "viagem_desc": ("-data_evento_inicio", "-ano", "-numero"),
}


def listar_planos_trabalho(q=None, status=None, viagem_de=None, viagem_ate=None, sort=None):
    """Lista de planos já anotada com a finalização das prestações.

    A subconsulta de finalização depende da área corrente — inclusive do caso
    `area is None`, que casa com prestações sem área. Esse detalhe vinha da
    view e continua idêntico aqui.
    """
    planos = filter_queryset_by_area(PlanoTrabalho.objects).select_related(
        "programa",
        "destino_cidade__estado",
        "coordenador_adm__cargo",
        "coordenador_op__cargo",
    ).prefetch_related(
        "atividades_selecionadas",
        "efetivos",
        "destinos__cidade__estado",
        "eventos__programa",
        "eventos__efetivos",
    )
    if status:
        planos = planos.filter(status=status)
    if q:
        q_unaccent = remove_accents(q)
        filtro = (
            Q(destino_cidade__nome__unaccent__icontains=q_unaccent)
            | Q(programa__nome__unaccent__icontains=q_unaccent)
            | Q(programa_outros__unaccent__icontains=q_unaccent)
            | Q(contextualizacao__unaccent__icontains=q_unaccent)
        )
        if q.isdigit():
            filtro = filtro | Q(numero=int(q)) | Q(ano=int(q))
        planos = planos.filter(filtro)

    if viagem_de:
        planos = planos.filter(data_evento_fim__gte=viagem_de)
    if viagem_ate:
        planos = planos.filter(data_evento_inicio__lte=viagem_ate)

    planos = planos.order_by(*_SORT_MAP.get(sort or "numero_desc", _SORT_MAP["numero_desc"]))

    # Finalizado = todas as prestações dos ofícios (não cancelados) do evento
    # vinculado ao plano já finalizadas.
    area = get_current_area()
    sub = PrestacaoServidor.objects.filter(
        prestacao__oficio__evento=OuterRef("evento_id"),
        prestacao__oficio__cancelado=False,
    )
    if area is None:
        sub = sub.filter(prestacao__area__isnull=True)
    else:
        sub = sub.filter(prestacao__area=area)
    return tabs.anotar_finalizacao(planos, sub, sub.filter(finalizada=False))


def queryset_plano_detalhe():
    return filter_queryset_by_area(PlanoTrabalho.objects).select_related(
        "evento",
        "programa",
        "destino_estado",
        "destino_cidade__estado",
        "coordenador_adm__cargo",
        "coordenador_op__cargo",
    ).prefetch_related("destinos__cidade", "destinos__estado")


def get_plano_by_id(pk) -> PlanoTrabalho:
    return get_object_or_404(queryset_plano_detalhe(), pk=pk)


def get_evento_do_plano_by_id(plano, pk):
    return get_object_or_404(EventoPlano, pk=pk, plano=plano)


def cargo_pertence_a_area(pk) -> bool:
    """Validação de vínculo do autosave de efetivo.

    É escrita quem chama, mas isto aqui é consulta — e consulta com recorte por
    área, que é o ponto: sem ela, o autosave aceitaria o id de um cargo de outra
    área trabalho.
    """
    return filter_queryset_by_area(Cargo.objects).filter(pk=pk).exists()


def unidade_pertence_a_area(pk) -> bool:
    return filter_queryset_by_area(Unidade.objects).filter(pk=pk).exists()


# ── catálogos administráveis (`P-02`) ────────────────────────────────────────


def listar_atividades(q=None):
    atividades = filter_queryset_by_area(AtividadePlanoTrabalho.objects).order_by(
        "ordem", "nome"
    )
    if q:
        q_unaccent = remove_accents(q)
        atividades = atividades.filter(
            Q(nome__unaccent__icontains=q_unaccent)
            | Q(codigo__unaccent__icontains=q_unaccent)
            | Q(meta__unaccent__icontains=q_unaccent)
        )
    return atividades


def get_atividade_by_id(pk):
    return get_object_or_404(filter_queryset_by_area(AtividadePlanoTrabalho.objects), pk=pk)


def listar_presets(q=None):
    presets = (
        filter_queryset_by_area(PresetAtividadesPlanoTrabalho.objects)
        .prefetch_related("atividades")
        .order_by("ordem", "nome")
    )
    if q:
        q_unaccent = remove_accents(q)
        presets = presets.filter(
            Q(nome__unaccent__icontains=q_unaccent)
            | Q(descricao__unaccent__icontains=q_unaccent)
        )
    return presets


def get_preset_by_id(pk):
    return get_object_or_404(
        filter_queryset_by_area(PresetAtividadesPlanoTrabalho.objects), pk=pk
    )


def listar_programas():
    return filter_queryset_by_area(ProgramaSolicitante.objects).order_by("ordem", "nome")


def get_programa_by_id(pk):
    return get_object_or_404(filter_queryset_by_area(ProgramaSolicitante.objects), pk=pk)


def listar_horarios():
    return filter_queryset_by_area(HorarioAtendimento.objects).order_by("ordem", "faixa")


def get_horario_by_id(pk):
    return get_object_or_404(filter_queryset_by_area(HorarioAtendimento.objects), pk=pk)
