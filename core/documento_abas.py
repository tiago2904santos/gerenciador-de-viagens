"""Abas temporais compartilhadas das listas de documentos.

Usado por Ofícios, Eventos, Ordens de Serviço e Planos de Trabalho para
organizar a lista em quatro abas, nesta ordem de prioridade:

- **Que vão acontecer** (``futuras``): data de início > hoje. É a aba padrão.
- **Em andamento e realizados** (``atuais``): acontecendo agora ou já
  aconteceram (início <= hoje) — e também os sem data definida.
- **Finalizados** (``finalizados``): todas as prestações de contas relacionadas
  ao documento já foram finalizadas (derivado; ver ``anotar_finalizacao``).
- **Cancelados** (``cancelados``): documento cancelado.

Precedência ao classificar um documento: Cancelado > Finalizado > temporal.
As abas são mutuamente exclusivas.
"""
from urllib.parse import urlencode

from django.db.models import Count
from django.db.models import Exists
from django.db.models import Q
from django.utils import timezone


ABA_FUTURAS = "futuras"
ABA_ATUAIS = "atuais"
ABA_FINALIZADOS = "finalizados"
ABA_CANCELADOS = "cancelados"

ABA_LABELS = [
    (ABA_FUTURAS, "Que vão acontecer"),
    (ABA_ATUAIS, "Em andamento e realizados"),
    (ABA_FINALIZADOS, "Finalizados"),
    (ABA_CANCELADOS, "Cancelados"),
]
ABAS_VALIDAS = {chave for chave, _ in ABA_LABELS}
ABA_PADRAO = ABA_FUTURAS

# Finalizado = existe ao menos uma prestação relacionada e nenhuma está pendente.
# Depende das anotações criadas por ``anotar_finalizacao``.
FINALIZADO_Q = Q(_tem_prestacao=True, _tem_prestacao_pendente=False)


def normalizar_aba(aba):
    aba = (aba or "").strip()
    return aba if aba in ABAS_VALIDAS else ABA_PADRAO


def normalizar_abas(valores):
    """Normaliza uma seleção múltipla preservando a ordem visual canônica."""
    if isinstance(valores, str):
        valores = [valores]
    escolhidas = {(valor or "").strip() for valor in (valores or [])}
    normalizadas = [chave for chave, _label in ABA_LABELS if chave in escolhidas]
    return normalizadas or [ABA_PADRAO]


def anotar_finalizacao(queryset, prestacoes_todas, prestacoes_pendentes):
    """Anota ``_tem_prestacao`` e ``_tem_prestacao_pendente`` (booleanos via EXISTS).

    ``prestacoes_todas`` e ``prestacoes_pendentes`` são subconsultas de
    ``PrestacaoServidor`` (ou equivalente) já ligadas ao documento por
    ``OuterRef`` — a segunda restrita a ``finalizada=False``. Mantê-las como
    EXISTS (em vez de contagens) evita GROUP BY e torna a negação (~) trivial
    e correta.
    """
    return queryset.annotate(
        _tem_prestacao=Exists(prestacoes_todas),
        _tem_prestacao_pendente=Exists(prestacoes_pendentes),
    )


def q_da_aba(aba, *, date_field, cancelado_q):
    """Q que define quais documentos pertencem a cada aba (mutuamente exclusivas).

    Requer queryset anotado por ``anotar_finalizacao``. ``date_field`` é o lookup
    da data de início do evento (ex.: ``"data_inicio"`` ou
    ``"roteiro__saida_dt__date"``); ``cancelado_q`` identifica os cancelados
    (ex.: ``Q(cancelado=True)`` ou ``Q(status="cancelado")``).
    """
    aba = normalizar_aba(aba)
    if aba == ABA_CANCELADOS:
        return cancelado_q
    ativo = ~cancelado_q
    if aba == ABA_FINALIZADOS:
        return ativo & FINALIZADO_Q
    ativo_pendente = ativo & ~FINALIZADO_Q
    hoje = timezone.localdate()
    if aba == ABA_FUTURAS:
        return ativo_pendente & Q(**{f"{date_field}__gt": hoje})
    # Atuais: início <= hoje, ou sem data definida (precisa de atenção).
    return ativo_pendente & (
        Q(**{f"{date_field}__lte": hoje}) | Q(**{f"{date_field}__isnull": True})
    )


def q_das_abas(abas, *, date_field, cancelado_q):
    """Combina por OR os recortes exclusivos escolhidos no multiselect."""
    filtros = [
        q_da_aba(aba, date_field=date_field, cancelado_q=cancelado_q)
        for aba in normalizar_abas(abas)
    ]
    combinado = filtros[0]
    for filtro in filtros[1:]:
        combinado |= filtro
    return combinado


def contar_por_aba(base_qs, *, date_field, cancelado_q):
    """Total de documentos em cada aba, respeitando os filtros do ``base_qs``."""
    filtros = {
        chave: q_da_aba(chave, date_field=date_field, cancelado_q=cancelado_q)
        for chave, _ in ABA_LABELS
    }
    return base_qs.aggregate(
        **{
            chave: Count("pk", filter=filtro, distinct=True)
            for chave, filtro in filtros.items()
        },
    )


def build_abas(index_url, aba_atual, contagem, preserved=None):
    """Monta as abas para o template (cada uma como link que preserva os filtros)."""
    preserved = [(k, v) for k, v in (preserved or {}).items() if v]
    abas = []
    for chave, label in ABA_LABELS:
        query = urlencode([("aba", chave), *preserved])
        abas.append(
            {
                "key": chave,
                "label": label,
                "count": contagem.get(chave, 0),
                "url": f"{index_url}?{query}",
                "is_active": chave == aba_atual,
            }
        )
    return abas
