"""Selectors — consultas de leitura da Central de Protocolos.

Mantém a lógica de querysets/filtragem fora das views.
"""

from __future__ import annotations

from django.db.models import Count, Q

from core.normalizers import remove_accents

from .models import Protocolo


def listar_protocolos(*, busca: str = "", status: str = "", apenas_ativos: bool = True):
    qs = (
        Protocolo.objects.all()
        .select_related("origem_content_type")
        .annotate(
            pendencias_abertas_count=Count(
                "pendencias",
                filter=~Q(pendencias__status__in=["concluida", "cancelada"]),
            )
        )
    )
    if apenas_ativos:
        qs = qs.filter(ativo=True)
    if status:
        qs = qs.filter(status_local=status)
    if busca:
        termo = remove_accents(busca.strip())
        qs = qs.filter(
            Q(numero__unaccent__icontains=termo)
            | Q(assunto_resumo__unaccent__icontains=termo)
            | Q(nome_local_atual__unaccent__icontains=termo)
            | Q(nome_responsavel_atual__unaccent__icontains=termo)
        )
    return qs.order_by("-criado_no_sistema_em")


def obter_protocolo_detalhado(pk: int) -> Protocolo:
    return (
        Protocolo.objects.select_related("origem_content_type")
        .prefetch_related("documentos", "assinaturas", "pendencias",
                          "tramitacoes", "movimentacoes")
        .get(pk=pk)
    )


def status_local_options():
    return [{"value": value, "label": label} for value, label in Protocolo.STATUS_LOCAL_CHOICES]
