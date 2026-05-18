import re

from django.db import transaction
from django.urls import reverse
from django.db.models import ProtectedError
from django.utils import timezone

from core.normalizers import normalize_spaces
from core.normalizers import normalize_upper
from core.utils.masks import format_placa
from core.utils.masks import format_protocolo
from core.utils.masks import normalize_protocolo
import logging

from django.conf import settings as django_settings

from documentos.services.document_cache import build_document_cache_key
from documentos.services.document_cache import build_template_cache_signature
from documentos.services.document_cache import get_cached_document_artifact
from documentos.services.document_cache import read_artifact_file_bytes
from documentos.services.facade import build_default_facade
from documentos.services.pdf_engine import resolve_pdf_engine
from documentos.services.persistence import persist_geracao
from documentos.services.responses import build_download_response
from documentos.services.timing import measure_step
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo

from .docxtpl_context import build_justificativa_docxtpl_context
from .docxtpl_context import build_oficio_docxtpl_context
from .documents import build_canonical_document_payload
from .documents import build_justificativa_payload

logger = logging.getLogger(__name__)


def _pdf_attempt_chain(*, prefer_docx_pipeline: bool) -> tuple[str, ...]:
    explicit = (getattr(django_settings, "DOCUMENTOS_DEFAULT_PDF_ENGINE", "auto") or "auto").strip().lower()
    return resolve_pdf_engine(
        explicit_setting=explicit,
        prefer_docx_pipeline=prefer_docx_pipeline,
    ).attempt_chain


def _document_cache_key(
    *,
    tipo: DocumentoTipo,
    formato: DocumentoFormato,
    reference: str,
    payload: dict,
    docxtpl_context: dict | None,
    prefer_docx: bool,
) -> str:
    chain = _pdf_attempt_chain(prefer_docx_pipeline=prefer_docx) if formato == DocumentoFormato.PDF else ()
    tpl_sig = build_template_cache_signature(tipo=tipo, formato=formato)
    return build_document_cache_key(
        tipo=tipo,
        formato=formato,
        reference=reference,
        payload=payload,
        docxtpl_context=docxtpl_context,
        attempt_chain=chain if formato == DocumentoFormato.PDF else (),
        template_signature=tpl_sig,
    )


def _try_cached_download(
    *,
    oficio_id: int,
    tipo: DocumentoTipo,
    formato: DocumentoFormato,
    reference: str,
    payload: dict,
    docxtpl_context: dict | None,
    prefer_docx: bool,
):
    if not getattr(django_settings, "DOCUMENTOS_ARTIFACT_CACHE", True):
        return None
    key = _document_cache_key(
        tipo=tipo,
        formato=formato,
        reference=reference,
        payload=payload,
        docxtpl_context=docxtpl_context,
        prefer_docx=prefer_docx,
    )
    art = get_cached_document_artifact(oficio_id=oficio_id, tipo=tipo, formato=formato, cache_key=key)
    if art is None:
        return None
    content = read_artifact_file_bytes(art)
    response = build_download_response(
        content=content,
        tipo=tipo,
        formato=formato,
        reference=reference,
        cache_hit=True,
    )
    response["X-Document-SHA256"] = art.hash_sha256
    return response


from .models import ModeloMotivoOficio
from .models import Oficio
from roteiros.models import Roteiro


class OficioVinculadoError(Exception):
    """Exclusão bloqueada porque o ofício possui vínculos protegidos."""


@transaction.atomic
def garantir_roteiro_vinculado_ao_oficio(oficio: Oficio) -> Oficio:
    """Garante um roteiro em rascunho vinculado ao ofício para edição na etapa 3."""
    if oficio.roteiro_id:
        return oficio
    roteiro = Roteiro.objects.create(
        tipo=Roteiro.TIPO_AVULSO,
        status=Roteiro.STATUS_RASCUNHO,
    )
    oficio.roteiro = roteiro
    oficio.save(update_fields=["roteiro", "updated_at"])
    return oficio


@transaction.atomic
def criar_oficio(form):
    return form.save()


@transaction.atomic
def atualizar_oficio(instance, form):
    _ = instance
    return form.save()


def aplicar_modelo_motivo_no_oficio(oficio, modelo_motivo, motivo_digitado):
    motivo_limpo = (motivo_digitado or "").strip()
    if motivo_limpo:
        oficio.motivo = motivo_limpo
        return oficio
    if modelo_motivo:
        oficio.motivo = (modelo_motivo.texto or "").strip()
    return oficio


def atualizar_status_automatico_oficio(oficio, action="save_draft", form=None):
    avaliacao = avaliar_oficio_dados_viajantes(form=form) if form is not None else avaliar_oficio_dados_viajantes(oficio=oficio)
    if action == "save_continue" and avaliacao["status"] == "complete":
        oficio.status = Oficio.STATUS_GERADO
    else:
        oficio.status = Oficio.STATUS_RASCUNHO
    return oficio


@transaction.atomic
def criar_oficio_dados_viajantes(form, action="save_draft"):
    oficio = form.save(commit=False)
    oficio.data_criacao = oficio.data_criacao or timezone.localdate()
    oficio.custeio = oficio.custeio or Oficio.CUSTEIO_UNIDADE_DPC
    modelo_motivo = form.cleaned_data.get("modelo_motivo")
    aplicar_modelo_motivo_no_oficio(oficio, modelo_motivo, form.cleaned_data.get("motivo"))
    reservar_numero_oficio(oficio)
    atualizar_status_automatico_oficio(oficio, action=action, form=form)
    oficio.save()
    form.save_m2m()
    return oficio


@transaction.atomic
def atualizar_oficio_dados_viajantes(oficio, form, action="save_draft"):
    data_criacao_original = oficio.data_criacao
    atualizado = form.save(commit=False)
    atualizado.numero = oficio.numero
    atualizado.ano = oficio.ano
    atualizado.data_criacao = data_criacao_original
    atualizado.custeio = atualizado.custeio or Oficio.CUSTEIO_UNIDADE_DPC
    modelo_motivo = form.cleaned_data.get("modelo_motivo")
    aplicar_modelo_motivo_no_oficio(atualizado, modelo_motivo, form.cleaned_data.get("motivo"))
    atualizar_status_automatico_oficio(atualizado, action=action, form=form)
    atualizado.save()
    form.save_m2m()
    return atualizado


@transaction.atomic
def atualizar_oficio_transporte(oficio, form, action="save_draft"):
    _ = action
    data_criacao_original = oficio.data_criacao
    atualizado = form.save(commit=False)
    atualizado.numero = oficio.numero
    atualizado.ano = oficio.ano
    atualizado.data_criacao = data_criacao_original
    equipe_ids = set(oficio.servidores.values_list("pk", flat=True))
    if atualizado.viatura_id:
        atualizado.transporte_placa_manual = ""
        atualizado.transporte_modelo_manual = ""
        atualizado.transporte_combustivel_manual_id = None
        atualizado.transporte_tipo_manual = ""
    else:
        atualizado.transporte_modelo_manual = normalize_upper(atualizado.transporte_modelo_manual or "")
    if atualizado.motorista_modo == Oficio.MOTORISTA_MODO_MANUAL:
        atualizado.motorista_id = None
        atualizado.motorista_manual_nome = normalize_upper(atualizado.motorista_manual_nome or "")
        atualizado.motorista_manual_rg = ""
        atualizado.motorista_manual_cpf = ""
        atualizado.motorista_manual_cargo = ""
        atualizado.motorista_manual_unidade = ""
        atualizado.motorista_manual_observacao = ""
        atualizado.motorista_protocolo_ref = normalize_protocolo(atualizado.motorista_protocolo_ref or "")
    else:
        atualizado.motorista_manual_nome = ""
        atualizado.motorista_manual_rg = ""
        atualizado.motorista_manual_cpf = ""
        atualizado.motorista_manual_cargo = ""
        atualizado.motorista_manual_unidade = ""
        atualizado.motorista_manual_observacao = ""
        if not atualizado.motorista_id:
            atualizado.motorista_oficio_referencia = ""
            atualizado.motorista_protocolo_ref = ""
        elif atualizado.motorista_id in equipe_ids:
            atualizado.motorista_oficio_referencia = ""
            atualizado.motorista_protocolo_ref = ""
        else:
            atualizado.motorista_protocolo_ref = normalize_protocolo(atualizado.motorista_protocolo_ref or "")
    atualizado.save()
    return atualizado


def avaliar_oficio_transporte(oficio):
    if oficio is None:
        return {"status": "not_started", "pendencias": []}
    tem_viatura = bool(oficio.viatura_id) or bool((oficio.transporte_placa_manual or "").strip())
    tem_motorista = bool(oficio.motorista_id) or (
        oficio.motorista_modo == Oficio.MOTORISTA_MODO_MANUAL and (oficio.motorista_manual_nome or "").strip()
    )
    if tem_viatura and tem_motorista:
        status = "complete"
    elif not tem_viatura and not tem_motorista:
        status = "not_started"
    else:
        status = "incomplete"
    return {"status": status, "pendencias": []}


@transaction.atomic
def criar_oficio_rascunho():
    oficio = Oficio.objects.create(
        data_criacao=timezone.localdate(),
        status=Oficio.STATUS_RASCUNHO,
        custeio=Oficio.CUSTEIO_UNIDADE_DPC,
    )
    reservar_numero_oficio(oficio, ano=oficio.data_criacao.year)
    return oficio


def get_next_available_numero_oficio(ano):
    resolved_year = ano or timezone.localdate().year
    numeros_ocupados = set(
        Oficio.objects.filter(ano=resolved_year)
        .exclude(numero__isnull=True)
        .order_by("numero")
        .values_list("numero", flat=True)
    )
    numero = 1
    while numero in numeros_ocupados:
        numero += 1
    return numero


@transaction.atomic
def reservar_numero_oficio(oficio, ano=None):
    if oficio.numero and oficio.ano:
        return oficio

    resolved_year = ano or timezone.localdate().year
    list(Oficio.objects.select_for_update().filter(ano=resolved_year).exclude(numero__isnull=True))
    oficio.ano = resolved_year
    oficio.numero = get_next_available_numero_oficio(resolved_year)
    oficio.save()
    return oficio


def avaliar_oficio_dados_viajantes(oficio=None, form=None):
    if form is not None:
        values = _dados_viajantes_from_form(form)
    elif oficio is not None:
        values = _dados_viajantes_from_oficio(oficio)
    else:
        values = {}

    pendencias = []
    if not values.get("motivo"):
        pendencias.append("Informe o motivo.")
    if not values.get("custeio"):
        pendencias.append("Informe o custeio.")
    if values.get("custeio") == Oficio.CUSTEIO_OUTRA_INSTITUICAO and not values.get("custeio_observacao"):
        pendencias.append("Informe a observação de custeio.")
    if not values.get("servidores_count"):
        pendencias.append("Selecione ao menos um viajante.")

    if not values.get("has_started"):
        status = "not_started"
    elif pendencias:
        status = "incomplete"
    else:
        status = "complete"
    return {"status": status, "pendencias": pendencias}


def pendencias_motorista_documento(oficio):
    pendencias = []
    modo = oficio.motorista_modo or Oficio.MOTORISTA_MODO_SERVIDOR
    if modo == Oficio.MOTORISTA_MODO_MANUAL:
        nome = (oficio.motorista_manual_nome or "").strip()
        if not nome:
            pendencias.append("Informe o nome do motorista.")
            return pendencias
        pendencias.extend(_pendencias_oficio_protocolo_motorista(oficio))
        return pendencias
    if oficio.motorista_id:
        equipe = set(oficio.servidores.values_list("pk", flat=True))
        if oficio.motorista_id not in equipe:
            pendencias.extend(_pendencias_oficio_protocolo_motorista(oficio))
    return pendencias


def _pendencias_oficio_protocolo_motorista(oficio):
    pendencias = []
    ref = (oficio.motorista_oficio_referencia or "").strip()
    if not ref or not re.match(r"^\d{1,3}/\d{4}$", ref):
        pendencias.append("Informe o ofício do motorista no formato número/ano.")
    proto = normalize_protocolo(oficio.motorista_protocolo_ref or "")
    if len(proto) != 9:
        pendencias.append("Informe o protocolo do motorista com 9 dígitos.")
    return pendencias


def _pendencias_transporte_documento(oficio):
    av = avaliar_oficio_transporte(oficio)
    if av["status"] == "complete":
        return []
    return ["Complete o transporte (viatura ou placa manual e motorista)."]


def _pendencias_roteiro_documento(oficio):
    from justificativas.services import get_primeira_saida_oficio

    pendencias = []
    if not oficio.roteiro_id:
        pendencias.append("Associe um roteiro ao ofício.")
        return pendencias
    roteiro = oficio.roteiro
    if not (roteiro.origem_cidade_id or roteiro.origem_estado_id):
        pendencias.append("Informe a sede ou origem do roteiro.")
    if get_primeira_saida_oficio(oficio) is None:
        pendencias.append("Informe a data da primeira saída no roteiro.")
    if not roteiro.destinos.exists() and not roteiro.trechos.exists():
        pendencias.append("Informe destinos ou trechos no roteiro.")
    return pendencias


def _pendencias_justificativa_documento(oficio):
    from justificativas.services import justificativa_oficio_esta_completa
    from justificativas.services import oficio_exige_justificativa

    if not oficio_exige_justificativa(oficio):
        return []
    if not justificativa_oficio_esta_completa(oficio):
        return ["Informe a justificativa obrigatória para este ofício."]
    return []


def validar_oficio_para_documento(oficio):
    dados = avaliar_oficio_dados_viajantes(oficio=oficio)
    pendencias = list(dados["pendencias"])
    checks = {"dados_viajantes": dados["status"]}

    mot = pendencias_motorista_documento(oficio)
    pendencias.extend(mot)
    checks["motorista_documento"] = "complete" if not mot else "incomplete"

    transp_extra = _pendencias_transporte_documento(oficio)
    pendencias.extend(transp_extra)
    checks["transporte"] = avaliar_oficio_transporte(oficio)["status"]

    rot_extra = _pendencias_roteiro_documento(oficio)
    pendencias.extend(rot_extra)
    checks["roteiro"] = "complete" if not rot_extra else "incomplete"

    just_extra = _pendencias_justificativa_documento(oficio)
    pendencias.extend(just_extra)
    checks["justificativa"] = "complete" if not just_extra else "incomplete"

    checks["documento"] = "complete"

    status = "complete" if not pendencias else "incomplete"
    return {"status": status, "pendencias": pendencias, "checks": checks}


def oficio_esta_completo_para_finalizar(oficio: Oficio) -> bool:
    """Indica se o ofício cumpre requisitos documentais, sem considerar assinatura digital."""
    return validar_oficio_para_documento(oficio)["status"] == "complete"


def redirect_para_corrigir_documento_oficio(oficio):
    """Primeira etapa do wizard com pendência relevante para download documental."""
    dados = avaliar_oficio_dados_viajantes(oficio=oficio)
    if dados["pendencias"]:
        return reverse("oficios:dados_viajantes", args=[oficio.pk])
    mot = pendencias_motorista_documento(oficio)
    if mot:
        return reverse("oficios:transporte", args=[oficio.pk])
    if avaliar_oficio_transporte(oficio)["status"] != "complete":
        return reverse("oficios:transporte", args=[oficio.pk])
    rot_extra = _pendencias_roteiro_documento(oficio)
    if rot_extra:
        return reverse("oficios:wizard_roteiro", args=[oficio.pk])
    from justificativas.services import justificativa_oficio_esta_completa
    from justificativas.services import oficio_exige_justificativa

    if oficio_exige_justificativa(oficio) and not justificativa_oficio_esta_completa(oficio):
        return reverse("oficios:wizard_justificativa", args=[oficio.pk])
    return reverse("oficios:wizard_documentos", args=[oficio.pk])


def gerar_resposta_documento_oficio(oficio, formato: DocumentoFormato):
    with measure_step(
        "oficio_gerar_resposta_documento_oficio",
        {"oficio_id": oficio.pk, "formato": formato.value},
    ):
        payload = build_canonical_document_payload(oficio, DocumentoTipo.OFICIO)
        docxtpl = build_oficio_docxtpl_context(oficio)
        reference = oficio.numero_formatado.replace("/", "-")
        hit = _try_cached_download(
            oficio_id=oficio.pk,
            tipo=DocumentoTipo.OFICIO,
            formato=formato,
            reference=reference,
            payload=payload,
            docxtpl_context=docxtpl,
            prefer_docx=True,
        )
        if hit is not None:
            return hit
        cache_key = _document_cache_key(
            tipo=DocumentoTipo.OFICIO,
            formato=formato,
            reference=reference,
            payload=payload,
            docxtpl_context=docxtpl,
            prefer_docx=True,
        )
        facade = build_default_facade()
        doc = facade.gerar(
            tipo=DocumentoTipo.OFICIO,
            formato=formato,
            payload=payload,
            reference=reference,
            docxtpl_context=docxtpl,
        )
        response = build_download_response(
            content=doc.conteudo,
            tipo=DocumentoTipo.OFICIO,
            formato=formato,
            reference=reference,
            cache_hit=False,
        )
        response["X-Document-SHA256"] = doc.hash_sha256
        try:
            persist_geracao(
                doc,
                oficio_id=oficio.pk,
                payload_snapshot=payload,
                cache_key=cache_key,
                engine=doc.pdf_engine_used or "",
            )
        except Exception:
            logger.exception("Não foi possível persistir artefato documental do ofício.")
        return response


def gerar_resposta_justificativa_documento(oficio, formato: DocumentoFormato):
    with measure_step(
        "oficio_gerar_resposta_justificativa_documento",
        {"oficio_id": oficio.pk, "formato": formato.value},
    ):
        payload = build_justificativa_payload(oficio)
        docxtpl = build_justificativa_docxtpl_context(oficio)
        reference = f"{oficio.numero_formatado.replace('/', '-')}-justificativa"
        hit = _try_cached_download(
            oficio_id=oficio.pk,
            tipo=DocumentoTipo.JUSTIFICATIVA,
            formato=formato,
            reference=reference,
            payload=payload,
            docxtpl_context=docxtpl,
            prefer_docx=True,
        )
        if hit is not None:
            return hit
        cache_key = _document_cache_key(
            tipo=DocumentoTipo.JUSTIFICATIVA,
            formato=formato,
            reference=reference,
            payload=payload,
            docxtpl_context=docxtpl,
            prefer_docx=True,
        )
        facade = build_default_facade()
        doc = facade.gerar(
            tipo=DocumentoTipo.JUSTIFICATIVA,
            formato=formato,
            payload=payload,
            reference=reference,
            docxtpl_context=docxtpl,
        )
        response = build_download_response(
            content=doc.conteudo,
            tipo=DocumentoTipo.JUSTIFICATIVA,
            formato=formato,
            reference=reference,
            cache_hit=False,
        )
        response["X-Document-SHA256"] = doc.hash_sha256
        try:
            persist_geracao(
                doc,
                oficio_id=oficio.pk,
                payload_snapshot=payload,
                cache_key=cache_key,
                engine=doc.pdf_engine_used or "",
            )
        except Exception:
            logger.exception("Não foi possível persistir artefato da justificativa.")
        return response


def _dados_viajantes_from_form(form):
    if form.is_bound:
        data = form.cleaned_data if form.is_valid() else form.data
        get_value = data.get
        servidores = (
            list(get_value("servidores") or [])
            if hasattr(data, "get")
            else []
        )
        if not servidores and hasattr(form.data, "getlist"):
            servidores = form.data.getlist("servidores")
        text_values = [
            get_value("assunto", ""),
            get_value("motivo", ""),
            get_value("protocolo", ""),
            get_value("custeio_observacao", ""),
        ]
        has_started = form.is_bound or any(str(value).strip() for value in text_values) or bool(servidores)
        return {
            "data_criacao": get_value("data_criacao"),
            "motivo": str(get_value("motivo", "") or "").strip(),
            "custeio": get_value("custeio"),
            "custeio_observacao": str(get_value("custeio_observacao", "") or "").strip(),
            "servidores_count": len(servidores),
            "has_started": has_started,
        }
    instance = getattr(form, "instance", None)
    return _dados_viajantes_from_oficio(instance) if instance and instance.pk else {}


def _dados_viajantes_from_oficio(oficio):
    if oficio is None:
        return {}
    text_values = [oficio.motivo, oficio.protocolo, oficio.custeio_observacao]
    servidores_count = oficio.servidores.count() if oficio.pk else 0
    return {
        "data_criacao": oficio.data_criacao,
        "motivo": oficio.motivo.strip(),
        "custeio": oficio.custeio,
        "custeio_observacao": oficio.custeio_observacao.strip(),
        "servidores_count": servidores_count,
        "has_started": bool(oficio.pk) or any(value.strip() for value in text_values) or bool(servidores_count),
    }


@transaction.atomic
def excluir_oficio(instance):
    try:
        instance.delete()
    except ProtectedError as exc:
        raise OficioVinculadoError from exc


def build_oficio_document_payload(oficio):
    viatura_label = ""
    if oficio.viatura_id:
        viatura_label = oficio.viatura.placa_formatada
    elif (oficio.transporte_placa_manual or "").strip():
        viatura_label = format_placa(oficio.transporte_placa_manual)
    motorista_label = ""
    if oficio.motorista_id:
        motorista_label = oficio.motorista.nome
    elif oficio.motorista_modo == Oficio.MOTORISTA_MODO_MANUAL:
        motorista_label = (oficio.motorista_manual_nome or "").strip()
    return {
        "numero": oficio.numero,
        "ano": oficio.ano,
        "numero_formatado": oficio.numero_formatado,
        "protocolo": format_protocolo(oficio.protocolo),
        "assunto": oficio.assunto,
        "motivo": oficio.motivo,
        "data_criacao": oficio.data_criacao,
        "status": oficio.status,
        "roteiro": str(oficio.roteiro) if oficio.roteiro else "",
        "servidores": [servidor.nome for servidor in oficio.servidores.all()],
        "viatura": viatura_label,
        "motorista": motorista_label,
        "custeio": oficio.custeio,
    }


@transaction.atomic
def criar_modelo_motivo(form):
    modelo = form.save(commit=False)
    if modelo.is_padrao:
        ModeloMotivoOficio.objects.exclude(pk=modelo.pk).update(is_padrao=False)
    modelo.save()
    return modelo


@transaction.atomic
def atualizar_modelo_motivo(instance, form):
    _ = instance
    modelo = form.save(commit=False)
    if modelo.is_padrao:
        ModeloMotivoOficio.objects.exclude(pk=modelo.pk).update(is_padrao=False)
    modelo.save()
    return modelo


@transaction.atomic
def excluir_modelo_motivo(instance):
    instance.delete()
