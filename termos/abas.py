"""Abas de período da lista de Termos de Autorização.

Três abas, pela única pergunta que se faz a um termo na lista: a viagem já foi,
está acontecendo ou ainda vem?

- **Que vão acontecer** (``futuros``): começa depois de hoje. É a aba padrão.
- **Em andamento** (``andamento``): começou e ainda não terminou — e também os
  SEM período, que são justamente os que precisam de atenção. O selo do cartão
  não os chama de "em andamento": diz "Sem período", que é o que eles são.
- **Já realizados** (``realizados``): terminou antes de hoje.

O período de um termo nem sempre é dele: sem datas próprias, ele herda as do
roteiro do ofício vinculado (`TermoAutorizacao.periodo_efetivo`). Filtrar em
Python obrigaria a carregar a tabela inteira para contar as abas, então as duas
datas são resolvidas em SQL por `COALESCE`, na mesma ordem do método.

As abas de composição ("Com equipe" / "Sem equipe") saíram daqui em 2026-08-18.
Elas dividiam a lista por um detalhe interno do documento, e a aba padrão
ESCONDIA os termos sem equipe — para vê-los era preciso um `?aba=simples` que a
tela não oferecia em lugar nenhum.
"""

from urllib.parse import urlencode

from django.db.models import Count
from django.db.models import DateField
from django.db.models import Q
from django.db.models.functions import Cast
from django.db.models.functions import Coalesce
from django.utils import timezone


ABA_FUTUROS = "futuros"
ABA_ANDAMENTO = "andamento"
ABA_REALIZADOS = "realizados"

ABA_LABELS = [
    (ABA_FUTUROS, "Que vão acontecer"),
    (ABA_ANDAMENTO, "Em andamento"),
    (ABA_REALIZADOS, "Já realizados"),
]
ABAS_VALIDAS = {chave for chave, _ in ABA_LABELS}
ABA_PADRAO = ABA_FUTUROS


def normalizar_aba(aba):
    aba = (aba or "").strip()
    return aba if aba in ABAS_VALIDAS else ABA_PADRAO


def anotar_periodo(queryset):
    """Anota ``_inicio`` e ``_fim`` com a MESMA cascata de `periodo_efetivo`.

    `Cast(..., DateField())` porque a saída do roteiro é `DateTimeField`: sem o
    corte, o `COALESCE` misturaria data com data-e-hora e o banco recusaria.
    """
    return queryset.annotate(
        _inicio=Coalesce(
            "data_evento_inicio",
            Cast("oficio__roteiro__saida_dt", DateField()),
        ),
        _fim=Coalesce(
            "data_evento_fim",
            "data_evento_inicio",
            Cast("oficio__roteiro__retorno_chegada_dt", DateField()),
            Cast("oficio__roteiro__retorno_saida_dt", DateField()),
            Cast("oficio__roteiro__saida_dt", DateField()),
        ),
    )


def q_da_aba(aba):
    """Q de cada aba sobre um queryset já anotado por `anotar_periodo`."""
    aba = normalizar_aba(aba)
    hoje = timezone.localdate()
    if aba == ABA_FUTUROS:
        return Q(_inicio__gt=hoje)
    if aba == ABA_REALIZADOS:
        return Q(_fim__lt=hoje)
    # Em andamento: começou e não terminou — mais os sem período nenhum.
    return Q(_inicio__isnull=True) | Q(_inicio__lte=hoje, _fim__gte=hoje)


def contar_por_aba(base_qs):
    """Total de cada aba numa consulta só, respeitando a busca já aplicada."""
    return anotar_periodo(base_qs).aggregate(
        **{
            chave: Count("pk", filter=q_da_aba(chave), distinct=True)
            for chave, _ in ABA_LABELS
        },
    )


def build_abas(index_url, aba_atual, contagem, preservado=None):
    preservado = [(k, v) for k, v in (preservado or {}).items() if v]
    return [
        {
            "key": chave,
            "label": label,
            "count": contagem.get(chave, 0),
            "url": f"{index_url}?{urlencode([('aba', chave), *preservado])}",
            "is_active": chave == aba_atual,
        }
        for chave, label in ABA_LABELS
    ]


def situacao_do_termo(termo):
    """Selo do cartão: o mesmo corte das abas, dito por extenso.

    Fica aqui, e não no presenter, para o cartão e a aba nunca discordarem —
    duas contas separadas do mesmo período divergem no primeiro caso de borda.

    O tom já sai no vocabulário do v2 (`done`, `progress`, `info`), e não no
    antigo com o filtro `tom_v2` no template: filtro dentro de `:attr` do Cotton
    não é avaliado, e o selo chegaria sem cor nenhuma.
    """
    inicio, fim = termo.periodo_efetivo()
    if inicio is None:
        return {"label": "Sem período", "tone": ""}
    hoje = timezone.localdate()
    if inicio > hoje:
        return {"label": "Vai acontecer", "tone": "progress"}
    if (fim or inicio) < hoje:
        return {"label": "Realizado", "tone": "done"}
    return {"label": "Em andamento", "tone": "info"}
