from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from roteiros.services import editor_persistence
from roteiros import roteiro_logic
from roteiros.models import Roteiro
from roteiros.services.editor_state import dedupe_roteiro_loop_retorno_final
from roteiros.services.roteiro_editor import _apply_saved_map_route_from_post


def pk_de_autosave(post):
    """`autosave_obj_id` do POST como int, ou `None`.

    `BE-11`: o parse estava copiado em `roteiros/views.py` e `oficios/route_views.py`.
    Só o parse é comum — o queryset é de quem chama, porque os escopos divergem de
    propósito: o fluxo avulso recorta pela área ativa, o do ofício pela área do ofício.
    """
    raw = (post.get("autosave_obj_id") or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


ROTEIRO_AUTOSAVE_FIELDS = {
    "origem_estado",
    "origem_cidade",
    "observacoes",
    "roteiro_modo",
    "roteiro_id",
    "bate_volta_diario_ativo",
}


def has_minimum_roteiro_content(fields, snapshots):
    observacoes = str((fields or {}).get("observacoes") or "").strip()
    origem_cidade = str((fields or {}).get("origem_cidade") or "").strip()
    origem_estado = str((fields or {}).get("origem_estado") or "").strip()
    state = (snapshots or {}).get("roteiro_editor_state") or {}
    destinos = (state.get("destinos_atuais") or []) if isinstance(state, dict) else []
    trechos = (state.get("trechos") or []) if isinstance(state, dict) else []
    return bool(observacoes or origem_cidade or origem_estado or destinos or trechos)


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _persist_simple_fields(roteiro, clean_fields):
    update_fields = []
    if "origem_estado" in clean_fields:
        roteiro.origem_estado_id = _to_int(clean_fields.get("origem_estado"))
        update_fields.append("origem_estado")
    if "origem_cidade" in clean_fields:
        roteiro.origem_cidade_id = _to_int(clean_fields.get("origem_cidade"))
        update_fields.append("origem_cidade")
    if "observacoes" in clean_fields:
        roteiro.observacoes = str(clean_fields.get("observacoes") or "").strip().upper()
        update_fields.append("observacoes")
    if update_fields:
        roteiro.save(update_fields=[*update_fields, "updated_at"])


def _apply_map_snapshot(roteiro, snapshots):
    mapa = (snapshots or {}).get("roteiro_mapa") or {}
    if not isinstance(mapa, dict):
        return
    payload = {
        "map_route_geometry_json": mapa.get("geometry_json") or "",
        "map_route_points_json": mapa.get("points_json") or "",
        "map_route_distance_km": mapa.get("distance_km") or "",
        "map_route_duration_minutes": mapa.get("duration_minutes") or "",
        "map_route_provider": mapa.get("provider") or "",
        "map_route_calculated_at": mapa.get("calculated_at") or "",
    }
    _apply_saved_map_route_from_post(roteiro, payload)


def _apply_diarias_snapshot(roteiro, snapshots):
    diarias = (snapshots or {}).get("roteiro_diarias") or {}
    if not isinstance(diarias, dict):
        return
    qtd = str(diarias.get("quantidade_diarias") or "").strip()
    valor = str(diarias.get("valor_diarias") or "").strip()
    extenso = str(diarias.get("valor_diarias_extenso") or "").strip()
    if not qtd and not valor and not extenso:
        return
    roteiro.quantidade_diarias = qtd
    roteiro.valor_diarias_extenso = extenso
    if valor:
        try:
            roteiro.valor_diarias = Decimal(valor.replace(".", "").replace(",", "."))
        except (InvalidOperation, TypeError, ValueError):
            pass
    roteiro.save(update_fields=["quantidade_diarias", "valor_diarias", "valor_diarias_extenso", "updated_at"])


def _apply_roteiro_snapshot(roteiro, snapshots):
    state = (snapshots or {}).get("roteiro_editor_state")
    if not isinstance(state, dict):
        return
    state = dedupe_roteiro_loop_retorno_final(state)
    validated = roteiro_logic._validate_roteiro_state(state)
    # Mesmo incompleto: persiste trechos/destinos parseados (datas podem ser null).
    editor_persistence.salvar_roteiro_avulso_from_roteiro_state(
        roteiro, state, validated, diarias_resultado=None
    )


def apply_roteiro_autosave(roteiro, clean_fields, snapshots):
    _persist_simple_fields(roteiro, clean_fields)
    _apply_roteiro_snapshot(roteiro, snapshots)
    _apply_map_snapshot(roteiro, snapshots)
    _apply_diarias_snapshot(roteiro, snapshots)
    roteiro.refresh_from_db()
    version = int(datetime.timestamp(timezone.localtime(roteiro.updated_at)))
    return version


def build_roteiro_draft(*, area):
    if area is None:
        raise ValueError("Selecione uma área de trabalho antes de criar o roteiro.")
    roteiro = Roteiro.objects.create(
        area=area,
        tipo=Roteiro.TIPO_AVULSO,
        status=Roteiro.STATUS_RASCUNHO,
    )
    return roteiro
