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


def origem_por_content_type(content_type_id, object_id):
    """Resolve o documento de origem a partir do par content_type/object_id do POST.

    Mora aqui, e não na view, por causa da catraca de ORM em `views.py`
    (`core/tests/test_view_module_boundaries.py`): acesso de manager em view é
    dívida contada, e `ContentType.objects` contaria.
    """
    from django.contrib.contenttypes.models import ContentType

    if not (content_type_id and object_id):
        return None
    try:
        ct = ContentType.objects.get_for_id(int(content_type_id))
        return ct.get_object_for_this_type(pk=int(object_id))
    except (ContentType.DoesNotExist, ValueError, LookupError):
        return None
    except Exception as exc:
        # Entrada forjada num POST não pode virar 500 — mas também não pode
        # sumir sem rastro (BE-18).
        from core.errors import capture

        capture(exc, "protocolos.selectors.origem_por_content_type")
        return None


def content_type_id_de_oficio() -> int:
    """O id do ContentType de `Oficio`, para o form de protocolar montar o POST."""
    from django.contrib.contenttypes.models import ContentType

    from oficios.models import Oficio

    return ContentType.objects.get_for_model(Oficio).pk


def oficios_protocolaveis():
    """Ofícios que ainda não têm protocolo na Central, mais novos primeiro.

    "Protocolável" = tem número reservado e nenhum `Protocolo` aponta para ele
    pela GFK. Não filtra por status: protocolar um rascunho é decisão do
    operador — o eProtocolo real recusaria sem documento, e o modo mock aceita,
    que é o que o treinamento precisa.
    """
    from django.contrib.contenttypes.models import ContentType

    from oficios.models import Oficio

    ct = ContentType.objects.get_for_model(Oficio)
    ja_ligados = Protocolo.objects.filter(
        origem_content_type=ct, origem_object_id__isnull=False
    ).values_list("origem_object_id", flat=True)
    return (
        Oficio.objects.exclude(pk__in=ja_ligados)
        .filter(numero__isnull=False)
        .order_by("-ano", "-numero")
    )
