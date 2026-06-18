import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from cadastros.models import ConfiguracaoSistema

from roteiros import roteiro_logic
from roteiros.models import Roteiro


def _apply_saved_map_route_from_post(roteiro, post):
    raw_geometry = (post.get("map_route_geometry_json") or "").strip()
    if not raw_geometry:
        return
    try:
        geometry = json.loads(raw_geometry)
    except (TypeError, ValueError, json.JSONDecodeError):
        return
    if not isinstance(geometry, dict) or geometry.get("type") != "LineString":
        return
    if not isinstance(geometry.get("coordinates"), list) or not geometry.get("coordinates"):
        return

    distance_raw = (post.get("map_route_distance_km") or "").strip()
    duration_raw = (post.get("map_route_duration_minutes") or "").strip()
    provider = (post.get("map_route_provider") or "").strip()
    calculated_at_raw = (post.get("map_route_calculated_at") or "").strip()

    distance = None
    if distance_raw:
        try:
            distance = Decimal(distance_raw)
        except (InvalidOperation, ValueError, TypeError):
            distance = None
    duration = None
    if duration_raw:
        try:
            duration = int(duration_raw)
        except (TypeError, ValueError):
            duration = None
    calculated_at = None
    if calculated_at_raw:
        try:
            calculated_at = datetime.fromisoformat(calculated_at_raw)
            if timezone.is_naive(calculated_at):
                calculated_at = timezone.make_aware(
                    calculated_at, timezone.get_current_timezone()
                )
        except (TypeError, ValueError):
            calculated_at = None

    roteiro.rota_geojson = geometry
    roteiro.rota_distancia_calculada_km = distance
    roteiro.rota_duracao_calculada_min = duration
    roteiro.rota_fonte = provider or Roteiro.ROTA_FONTE_OPENROUTESERVICE
    roteiro.rota_status = Roteiro.ROTA_STATUS_CALCULADA
    roteiro.rota_calculada_em = calculated_at or timezone.now()
    roteiro.save(
        update_fields=[
            "rota_geojson",
            "rota_distancia_calculada_km",
            "rota_duracao_calculada_min",
            "rota_fonte",
            "rota_status",
            "rota_calculada_em",
            "updated_at",
        ]
    )


def obter_initial_roteiro():
    initial = {}
    config = ConfiguracaoSistema.get_singleton()
    if getattr(config, "cidade_sede_padrao", None):
        initial["origem_cidade"] = config.cidade_sede_padrao_id
        if config.cidade_sede_padrao.estado_id:
            initial["origem_estado"] = config.cidade_sede_padrao.estado_id
    return initial


def preparar_querysets_formulario_roteiro(form, *, method, post, instance=None):
    """Limita-se a preencher querysets do form (sede); não monta contexto de template."""
    fake_request = SimpleNamespace(method=method.upper(), POST=post)
    roteiro_logic._setup_roteiro_querysets(form, fake_request, instance)


def carregar_opcoes_rotas_avulsas_salvas():
    """Lista opções de duplicação de roteiros avulsos e mapa de estado serializável (roteiro)."""
    return roteiro_logic._build_roteiro_avulso_route_options()


def preparar_estado_editor_roteiro_para_get(initial=None, roteiro=None):
    if roteiro:
        destinos_atuais = roteiro_logic._destinos_roteiro_para_template(roteiro) or [
            {"estado_id": None, "cidade_id": None, "cidade": None, "estado": None}
        ]
        destinos_list = [
            (d.get("estado_id"), d.get("cidade_id"))
            for d in destinos_atuais
            if d.get("estado_id") and d.get("cidade_id")
        ]
        trechos_list = roteiro_logic._estrutura_trechos(roteiro, destinos_list) if destinos_list else []
        roteiro_state = roteiro_logic._build_roteiro_state_from_roteiro_evento(roteiro)
        roteiro_state["roteiro_modo"] = "ROTEIRO_PROPRIO"
        return destinos_atuais, trechos_list, roteiro_state

    initial = initial or {}
    destino_estado = initial.get("destino_estado") or initial.get("destino_estado_id")
    destino_cidade = initial.get("destino_cidade") or initial.get("destino_cidade_id")
    destinos_atuais = [
        {
            "estado_id": destino_estado,
            "cidade_id": destino_cidade,
            "cidade": None,
            "estado": None,
        }
    ]
    trechos_list = []
    roteiro_state = roteiro_logic._build_roteiro_state_from_estrutura(
        trechos_list,
        [{"estado_id": destino_estado, "cidade_id": destino_cidade}],
        initial.get("origem_estado"),
        initial.get("origem_cidade"),
        initial.get("seed_source_label", ""),
    )
    if initial.get("saida_data"):
        roteiro_state["bate_volta_diario"]["data_inicio"] = initial.get("saida_data")
    if initial.get("retorno_data"):
        roteiro_state["bate_volta_diario"]["data_fim"] = initial.get("retorno_data")
    roteiro_state["roteiro_modo"] = "ROTEIRO_PROPRIO"
    return destinos_atuais, trechos_list, roteiro_state


def normalizar_destinos_e_trechos_apos_erro_post(roteiro_state):
    """Após POST inválido, reconstrói listas exibidas no form a partir do roteiro parseado."""
    destinos_atuais = [
        {
            "estado_id": item.get("estado_id"),
            "cidade_id": item.get("cidade_id"),
            "cidade": None,
            "estado": None,
        }
        for item in (roteiro_state.get("destinos_atuais") or [])
    ]
    if not destinos_atuais:
        destinos_atuais = [
            {"estado_id": None, "cidade_id": None, "cidade": None, "estado": None}
        ]
    trechos_list = roteiro_state.get("trechos", [])
    return destinos_atuais, trechos_list


def validar_submissao_editor_roteiro(post, route_state_map, roteiro=None):
    """Validação e cálculo de diárias a partir do POST; sem render nem redirect."""
    fake_request = SimpleNamespace(method="POST", POST=post)
    roteiro_state = roteiro_logic._build_avulso_roteiro_state_from_post(
        fake_request, route_state_map=route_state_map
    )
    fake_oficio = SimpleNamespace(evento_id=None, roteiro_evento_id=None, evento=None)
    validated = roteiro_logic._validate_roteiro_state(roteiro_state, oficio=fake_oficio)
    try:
        _, _, _, diarias_resultado = roteiro_logic._build_roteiro_diarias_from_request(
            fake_request, roteiro=roteiro
        )
    except ValueError as exc:
        mensagem = str(exc) or "Revise os dados de datas e horas para calcular as diárias."
        errors = list(validated.get("errors") or [])
        if mensagem not in errors:
            errors.append(mensagem)
        validated["ok"] = False
        validated["errors"] = errors
        diarias_resultado = None
    return roteiro_state, validated, diarias_resultado


def calcular_diarias_roteiro_request(request, *, roteiro=None, evento=None):
    return roteiro_logic._build_roteiro_diarias_from_request(
        request,
        roteiro=roteiro,
        evento=evento,
    )


def montar_contexto_editor_roteiro(
    *,
    evento,
    form,
    obj,
    destinos_atuais,
    trechos_list,
    is_avulso,
    roteiro_state,
    route_options,
    diarias_quantidade_servidores=1,
):
    return roteiro_logic._build_roteiro_form_context(
        evento=evento,
        form=form,
        obj=obj,
        destinos_atuais=destinos_atuais,
        trechos_list=trechos_list,
        is_avulso=is_avulso,
        roteiro_state=roteiro_state,
        route_options=route_options,
        diarias_quantidade_servidores=diarias_quantidade_servidores,
    )


@transaction.atomic
def criar_roteiro(form, roteiro_state, validated, diarias_resultado, *, evento=None):
    roteiro = form.save(commit=False)
    roteiro.evento = evento
    roteiro.tipo = Roteiro.TIPO_EVENTO if evento is not None else Roteiro.TIPO_AVULSO
    roteiro.origem_estado = validated.get("sede_estado")
    roteiro.origem_cidade = validated.get("sede_cidade")
    roteiro.save()
    roteiro_logic._salvar_roteiro_avulso_from_roteiro_state(
        roteiro, roteiro_state, validated, diarias_resultado=diarias_resultado
    )
    _apply_saved_map_route_from_post(roteiro, form.data)
    return roteiro


@transaction.atomic
def atualizar_roteiro(instance, form, roteiro_state, validated, diarias_resultado):
    roteiro = form.save(commit=False)
    roteiro.tipo = instance.tipo or Roteiro.TIPO_AVULSO
    roteiro.origem_estado = validated.get("sede_estado")
    roteiro.origem_cidade = validated.get("sede_cidade")
    roteiro.save()
    roteiro_logic._salvar_roteiro_avulso_from_roteiro_state(
        roteiro, roteiro_state, validated, diarias_resultado=diarias_resultado
    )
    _apply_saved_map_route_from_post(roteiro, form.data)
    return roteiro


@transaction.atomic
def excluir_roteiro(instance):
    try:
        instance.delete()
    except ProtectedError:
        return False
    return True
