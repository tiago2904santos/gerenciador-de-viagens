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
from roteiros.models import RoteiroTrecho


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


def carregar_opcoes_rotas_avulsas_salvas(evento=None, excluir_pk=None):
    """Lista opções de duplicação de roteiros avulsos e mapa de estado serializável (roteiro).

    Quando `evento` é informado, roteiros já vinculados a esse evento (Etapa 2 ou usados
    por algum ofício do evento) entram na lista e ficam priorizados no topo. `excluir_pk`
    tira da lista o roteiro que já está vinculado ao documento em edição.
    """
    return roteiro_logic._build_roteiro_avulso_route_options(evento=evento, excluir_pk=excluir_pk)


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


def encontrar_roteiro_duplicado(validated, roteiro_state, *, evento=None, excluir_pk=None):
    """Retorna Roteiro idêntico (mesma sede, mesma sequência de destinos e mesma saída) ou None."""
    sede_cidade = validated.get("sede_cidade")
    if not sede_cidade:
        return None

    destino_ids = [
        item.get("cidade_id")
        for item in (roteiro_state.get("destinos_atuais") or [])
        if item.get("cidade_id")
    ]
    if not destino_ids:
        return None

    saida_dt = None
    trechos = validated.get("trechos") or []
    if trechos:
        primeiro = trechos[0]
        saida_data = primeiro.get("saida_data")
        saida_hora = primeiro.get("saida_hora")
        if saida_data and saida_hora:
            naive = datetime.combine(saida_data, saida_hora)
            saida_dt = (
                timezone.make_aware(naive, timezone.get_current_timezone())
                if timezone.is_naive(naive)
                else naive
            )

    qs = Roteiro.objects.filter(origem_cidade_id=sede_cidade.pk).prefetch_related("destinos")
    if excluir_pk:
        qs = qs.exclude(pk=excluir_pk)
    if saida_dt is not None:
        qs = qs.filter(saida_dt=saida_dt)
    if evento is not None:
        qs = qs.filter(evento_id=evento.pk)

    for outro in qs:
        ids_outro = [d.cidade_id for d in outro.destinos.all().order_by("ordem")]
        if ids_outro == destino_ids:
            return outro
    return None


def _limpar_rascunhos_vazios(roteiro_atual_pk):
    """Apaga rascunhos órfãos sem sede, destinos, trechos ou saída — geralmente sobras de race da autosave."""
    Roteiro.objects.filter(
        destinos__isnull=True,
        trechos__isnull=True,
        saida_dt__isnull=True,
        origem_cidade__isnull=True,
    ).exclude(pk=roteiro_atual_pk).delete()


@transaction.atomic
def criar_roteiro(form, roteiro_state, validated, diarias_resultado, *, evento=None):
    roteiro = form.save(commit=False)
    roteiro.evento = evento
    roteiro.tipo = Roteiro.TIPO_EVENTO if evento is not None else Roteiro.TIPO_AVULSO
    roteiro.origem_estado = validated.get("sede_estado")
    roteiro.origem_cidade = validated.get("sede_cidade")
    roteiro.save()
    diarias_para_roteiro = roteiro_logic._calculate_avulso_diarias_from_state(
        roteiro_state, quantidade_servidores=1
    ) if roteiro_state else diarias_resultado
    roteiro_logic._salvar_roteiro_avulso_from_roteiro_state(
        roteiro, roteiro_state, validated, diarias_resultado=diarias_para_roteiro
    )
    _apply_saved_map_route_from_post(roteiro, form.data)
    _limpar_rascunhos_vazios(roteiro.pk)
    return roteiro


def _dt_to_local_tuple(dt):
    if dt is None:
        return None
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return (dt.year, dt.month, dt.day, dt.hour, dt.minute)


def _combine_to_local_tuple(date_obj, time_obj):
    if not date_obj or not time_obj:
        return None
    return (date_obj.year, date_obj.month, date_obj.day, time_obj.hour, time_obj.minute)


def _decimal_equivalente(a, b):
    if a in (None, "") and b in (None, ""):
        return True
    if a in (None, "") or b in (None, ""):
        return False
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except (InvalidOperation, TypeError, ValueError):
        return str(a) == str(b)


def _int_equivalente(a, b):
    def _norm(v):
        if v in (None, ""):
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None
    return _norm(a) == _norm(b)


def roteiro_state_equivalente_ao_roteiro(roteiro, roteiro_state, validated):
    """True se o estado posto equivale ao roteiro persistido (skip save no-op)."""
    if roteiro is None or roteiro.pk is None:
        return False

    sede_estado = validated.get("sede_estado")
    sede_cidade = validated.get("sede_cidade")
    sede_estado_id = sede_estado.pk if sede_estado else None
    sede_cidade_id = sede_cidade.pk if sede_cidade else None
    if (sede_estado_id, sede_cidade_id) != (roteiro.origem_estado_id, roteiro.origem_cidade_id):
        return False

    destinos_post = [
        (item.get("cidade_id"), item.get("estado_id"))
        for item in (roteiro_state.get("destinos_atuais") or [])
        if item.get("cidade_id") and item.get("estado_id")
    ]
    destinos_db = [
        (d.cidade_id, d.estado_id)
        for d in roteiro.destinos.all().order_by("ordem", "id")
    ]
    if destinos_post != destinos_db:
        return False

    trechos_post = list(validated.get("trechos") or [])
    trechos_db = list(
        roteiro.trechos.filter(tipo=RoteiroTrecho.TIPO_IDA).order_by("ordem", "id")
    )
    if len(trechos_post) != len(trechos_db):
        return False
    for posted, db in zip(trechos_post, trechos_db):
        if (
            posted.get("origem_estado_id") != db.origem_estado_id
            or posted.get("origem_cidade_id") != db.origem_cidade_id
            or posted.get("destino_estado_id") != db.destino_estado_id
            or posted.get("destino_cidade_id") != db.destino_cidade_id
        ):
            return False
        if _combine_to_local_tuple(posted.get("saida_data"), posted.get("saida_hora")) != _dt_to_local_tuple(db.saida_dt):
            return False
        if _combine_to_local_tuple(posted.get("chegada_data"), posted.get("chegada_hora")) != _dt_to_local_tuple(db.chegada_dt):
            return False
        if not _decimal_equivalente(posted.get("distancia_km"), db.distancia_km):
            return False
        if not _int_equivalente(posted.get("tempo_cru_estimado_min"), db.tempo_cru_estimado_min):
            return False
        if not _int_equivalente(posted.get("tempo_adicional_min"), db.tempo_adicional_min):
            return False
        if not _int_equivalente(posted.get("duracao_estimada_min"), db.duracao_estimada_min):
            return False

    retorno_db = (
        roteiro.trechos.filter(tipo=RoteiroTrecho.TIPO_RETORNO).order_by("ordem", "id").first()
    )
    ret_saida = _combine_to_local_tuple(validated.get("retorno_saida_data"), validated.get("retorno_saida_hora"))
    ret_chegada = _combine_to_local_tuple(validated.get("retorno_chegada_data"), validated.get("retorno_chegada_hora"))
    if (ret_saida or ret_chegada) and retorno_db is None:
        return False
    if retorno_db is not None:
        if ret_saida != _dt_to_local_tuple(retorno_db.saida_dt):
            return False
        if ret_chegada != _dt_to_local_tuple(retorno_db.chegada_dt):
            return False
        retorno_state = roteiro_state.get("retorno") or {}
        if not _decimal_equivalente(retorno_state.get("distancia_km"), retorno_db.distancia_km):
            return False
        if not _int_equivalente(retorno_state.get("tempo_cru_estimado_min"), retorno_db.tempo_cru_estimado_min):
            return False
        if not _int_equivalente(retorno_state.get("tempo_adicional_min"), retorno_db.tempo_adicional_min):
            return False
        if not _int_equivalente(retorno_state.get("duracao_estimada_min"), retorno_db.duracao_estimada_min):
            return False

    return True


@transaction.atomic
def atualizar_roteiro(instance, form, roteiro_state, validated, diarias_resultado):
    roteiro = form.save(commit=False)
    roteiro.tipo = instance.tipo or Roteiro.TIPO_AVULSO
    roteiro.origem_estado = validated.get("sede_estado")
    roteiro.origem_cidade = validated.get("sede_cidade")
    roteiro.save()
    # O roteiro persiste diárias sempre para 1 servidor; o ofício aplica a multiplicação
    # somente na geração do documento.
    diarias_para_roteiro = roteiro_logic._calculate_avulso_diarias_from_state(
        roteiro_state, quantidade_servidores=1
    ) if roteiro_state else diarias_resultado
    roteiro_logic._salvar_roteiro_avulso_from_roteiro_state(
        roteiro, roteiro_state, validated, diarias_resultado=diarias_para_roteiro
    )
    _apply_saved_map_route_from_post(roteiro, form.data)
    _limpar_rascunhos_vazios(roteiro.pk)
    return roteiro


@transaction.atomic
def excluir_roteiro(instance):
    try:
        instance.delete()
    except ProtectedError:
        return False
    return True
