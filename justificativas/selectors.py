from django.db.models import Q
from django.shortcuts import get_object_or_404

from core.normalizers import remove_accents
from core.tenancy import filter_queryset_by_area

from .models import Justificativa
from .models import ModeloJustificativa


def get_justificativa_by_oficio(oficio):
    return get_object_or_404(Justificativa, oficio=oficio)


def get_or_none_justificativa_by_oficio(oficio):
    if not getattr(oficio, "pk", None):
        return None
    return Justificativa.objects.filter(oficio=oficio).first()


# `Justificativa` não tem coluna `area`: a fronteira vem do ofício, que é
# obrigatório e um-para-um. Ver a nota em `core.tenancy.filter_queryset_by_area`
# sobre por que o caminho é preferível a denormalizar a coluna (`NOVO-06`).
POR_AREA_DO_OFICIO = "oficio__area"


def listar_justificativas():
    return (
        filter_queryset_by_area(Justificativa.objects, campo=POR_AREA_DO_OFICIO)
        .select_related("oficio", "modelo")
        .order_by("-updated_at", "-created_at")
    )


def listar_modelos_justificativa(*, incluir_inativos=False):
    qs = ModeloJustificativa.objects.all()
    if not incluir_inativos:
        qs = qs.filter(ativo=True)
    return qs.order_by("ordem", "nome")


def listar_modelos_justificativa_busca(q: str | None = None, *, incluir_inativos: bool = True):
    """Lista para tela de gerenciamento (mesmo critério que modelos de motivo)."""
    _ = incluir_inativos
    queryset = ModeloJustificativa.objects.order_by("nome")
    if q:
        query = remove_accents(q.strip())
        queryset = queryset.filter(Q(nome__unaccent__icontains=query) | Q(texto__unaccent__icontains=query))
    return queryset


def get_modelo_justificativa_by_id(pk):
    return get_object_or_404(ModeloJustificativa, pk=pk)


def get_justificativa_by_id(pk):
    """Recortado por área: é o que `justificativa_excluir` usa, e sem o recorte
    dava para apagar justificativa de outra área informando o `pk` (`NOVO-06`)."""
    return get_object_or_404(
        filter_queryset_by_area(Justificativa.objects, campo=POR_AREA_DO_OFICIO), pk=pk
    )
