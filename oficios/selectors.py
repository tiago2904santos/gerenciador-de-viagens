from django.db.models import Prefetch
from django.db.models import Q
from django.shortcuts import get_object_or_404

from core.normalizers import normalize_plate

from cadastros.models import Servidor
from cadastros.models import Unidade
from cadastros.models import Viatura
from roteiros.models import Roteiro

from .models import ModeloMotivoOficio
from .models import Oficio


def map_assinatura_pdf_oficio_por_ids(oficio_ids: list[int]) -> dict[int, str]:
    """
    Para cada ofício, devolve a situação do PDF de ofício mais recente: ``assinado`` ou ``aguardando``.
    Usado na listagem para complementar ofícios finalizados (sem N+1 por cartão).
    """
    from django.conf import settings

    if not oficio_ids or not getattr(settings, "DOCUMENTOS_PERSIST_ARTEFATOS", False):
        return {}

    from documentos.models import DocumentoArtefato
    from documentos.services.types import DocumentoTipo

    ids = sorted({int(pk) for pk in oficio_ids})
    qs = DocumentoArtefato.objects.filter(
        oficio_id__in=ids,
        tipo=DocumentoTipo.OFICIO.value,
        formato="pdf",
    ).order_by("oficio_id", "-criado_em")
    out: dict[int, str] = {}
    for art in qs:
        oid = int(art.oficio_id)
        if oid in out:
            continue
        signed = bool(art.assinado_em) or bool(getattr(art, "arquivo_assinado", None) and art.arquivo_assinado.name)
        out[oid] = "assinado" if signed else "aguardando"
    return out


def listar_oficios(q: str | None = None, status: str | None = None):
    queryset = (
        Oficio.objects.select_related("roteiro", "viatura", "motorista", "solicitante")
        .prefetch_related("servidores")
        .order_by("-data_criacao", "-created_at")
    )
    if status:
        queryset = queryset.filter(status=status)
    if q:
        query = q.strip()
        filters = (
            Q(protocolo__icontains=query)
            | Q(assunto__icontains=query)
            | Q(motivo__icontains=query)
            | Q(roteiro__observacoes__icontains=query)
            | Q(roteiro__origem_cidade__nome__icontains=query)
            | Q(roteiro__origem_estado__nome__icontains=query)
        )
        if query.isdigit():
            filters |= Q(numero=int(query)) | Q(ano=int(query))
        queryset = queryset.filter(filters).distinct()
    return queryset


def get_oficio_by_id(pk: int):
    queryset = Oficio.objects.select_related(
        "roteiro",
        "viatura",
        "viatura__combustivel",
        "transporte_combustivel_manual",
        "motorista",
        "solicitante",
    ).prefetch_related(
        "servidores",
    )
    return get_object_or_404(queryset, pk=pk)


def listar_roteiros_para_oficio():
    return Roteiro.objects.order_by("-created_at")


def listar_servidores_para_oficio():
    return Servidor.objects.select_related("cargo", "unidade").order_by("nome")


def listar_viaturas_para_oficio():
    return (
        Viatura.objects.select_related("combustivel", "unidade")
        .prefetch_related("motoristas")
        .order_by("placa")
    )


def get_viatura_por_placa_normalizada(placa_bruta: str):
    placa = normalize_plate(placa_bruta or "")
    if len(placa) != 7:
        return None
    try:
        return Viatura.objects.select_related("combustivel", "unidade").get(placa=placa)
    except Viatura.DoesNotExist:
        return None


def _filtro_viaturas_equipe_oficio(equipe_servidor_ids: list[int] | None):
    if not equipe_servidor_ids:
        return Q()
    unidade_ids = list(
        Servidor.objects.filter(pk__in=equipe_servidor_ids, unidade_id__isnull=False)
        .values_list("unidade_id", flat=True)
        .distinct()
    )
    filtro = Q(motoristas__in=equipe_servidor_ids)
    if unidade_ids:
        filtro |= Q(unidade_id__in=unidade_ids) | Q(motoristas__unidade_id__in=unidade_ids)
    return filtro


def _unidade_ids_dos_servidores(servidor_ids: list[int] | None) -> list[int]:
    """IDs únicos das unidades vinculadas a um conjunto de servidores."""
    if not servidor_ids:
        return []
    return list(
        Servidor.objects.filter(pk__in=servidor_ids, unidade_id__isnull=False)
        .values_list("unidade_id", flat=True)
        .distinct()
    )


def buscar_viaturas_para_oficio(
    termo: str,
    *,
    limit: int = 25,
    equipe_servidor_ids: list[int] | None = None,
    motorista_id: int | None = None,
):
    """Busca viaturas por placa, modelo, unidade vinculada ou nome de motorista cadastrado.

    Quando ``motorista_id`` é informado, as viaturas vinculadas a ele são retornadas
    primeiro (prioridade máxima). Em seguida vêm as viaturas das unidades dos servidores
    da equipe. O resultado final é ordenado por placa dentro de cada grupo.
    """
    termo = (termo or "").strip()

    if len(termo) < 2:
        equipe_filter = _filtro_viaturas_equipe_oficio(equipe_servidor_ids)
        if not equipe_filter and not motorista_id:
            return Viatura.objects.none()
        combined = equipe_filter
        if motorista_id:
            combined = combined | Q(motoristas=motorista_id) if combined else Q(motoristas=motorista_id)
        return (
            Viatura.objects.filter(combined)
            .distinct()
            .select_related("combustivel", "unidade")
            .prefetch_related(
                Prefetch(
                    "motoristas",
                    queryset=Servidor.objects.select_related("unidade", "cargo").order_by("nome"),
                ),
            )
            .order_by("placa")[:limit]
        )

    plate_key = normalize_plate(termo)
    filters = (
        Q(modelo__icontains=termo)
        | Q(unidade__nome__icontains=termo)
        | Q(unidade__sigla__icontains=termo)
        | Q(motoristas__nome__icontains=termo)
        | Q(motoristas__unidade__nome__icontains=termo)
        | Q(motoristas__unidade__sigla__icontains=termo)
    )
    if plate_key:
        filters |= Q(placa__icontains=plate_key)

    return (
        Viatura.objects.filter(filters)
        .select_related("combustivel", "unidade")
        .prefetch_related(
            Prefetch(
                "motoristas",
                queryset=Servidor.objects.select_related("unidade", "cargo").order_by("nome"),
            ),
        )
        .distinct()
        .order_by("placa")[:limit]
    )


def viatura_para_resultado_busca(
    v: Viatura,
    *,
    motorista_id: int | None = None,
    unidade_match_ids: list[int] | None = None,
) -> dict:
    """Resultado serializado de uma viatura para o picker do ofício.

    Os parâmetros ``motorista_id`` e ``unidade_match_ids`` são opcionais e usados
    apenas para definir o ``suggestion_reason`` (chip de motivo) e ordenação no
    cliente. Quando ausentes, ``suggestion_reason`` fica vazio.
    """
    from django.urls import reverse

    motoristas = list(v.motoristas.all())
    nomes = ", ".join(m.nome for m in motoristas[:5])
    if len(motoristas) > 5:
        nomes += "…"
    if v.unidade_id:
        unidade_txt = str(v.unidade)
    else:
        unidade_txt = "—"
        for m in motoristas:
            if m.unidade_id:
                unidade_txt = str(m.unidade)
                break

    combustivel_label = str(v.combustivel) if v.combustivel_id and v.combustivel else ""

    suggestion_reason = ""
    if motorista_id and any(m.pk == int(motorista_id) for m in motoristas):
        suggestion_reason = "motorista"
    elif unidade_match_ids:
        if v.unidade_id and v.unidade_id in unidade_match_ids:
            suggestion_reason = "unidade"
        elif any(m.unidade_id in unidade_match_ids for m in motoristas if m.unidade_id):
            suggestion_reason = "unidade"

    try:
        edit_url = reverse("cadastros:viatura_update", args=[v.pk])
    except Exception:
        edit_url = ""

    return {
        "id": v.pk,
        "placa": v.placa,
        "placa_formatada": v.placa_formatada,
        "modelo": v.modelo or "",
        "combustivel_id": v.combustivel_id,
        "combustivel": combustivel_label,
        "tipo": v.tipo or "",
        "unidade_id": v.unidade_id,
        "unidade_resumo": unidade_txt,
        "motoristas_resumo": nomes or "—",
        "edit_url": edit_url,
        "suggestion_reason": suggestion_reason,
    }


def listar_unidades_para_oficio():
    return Unidade.objects.order_by("nome")


def listar_modelos_motivo(q: str | None = None, incluir_inativos: bool = True):
    _ = incluir_inativos
    queryset = ModeloMotivoOficio.objects.order_by("nome")
    if q:
        query = q.strip()
        queryset = queryset.filter(Q(nome__icontains=query) | Q(texto__icontains=query))
    return queryset


def listar_modelos_motivo_ativos():
    return ModeloMotivoOficio.objects.order_by("nome")


def get_modelo_motivo_by_id(pk: int):
    return get_object_or_404(ModeloMotivoOficio, pk=pk)
