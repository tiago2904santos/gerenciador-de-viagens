import re
from dataclasses import dataclass

from django.db import IntegrityError
from django.db import transaction
from django.urls import reverse
from django.db.models import ProtectedError
from django.db.models import Q
from django.utils import timezone

from core.normalizers import normalize_upper
from core.deletion import DelecaoProtegidaError
from core.deletion import excluir_com_protecao
from core.numeracao import NAMESPACE_OFICIO
from core.numeracao import bloquear_escopo_numeracao
from core.numeracao import colisao_de_numero
from core.numeracao import reservar_numero
from core.tenancy import get_current_area
from core.utils.masks import format_placa
from core.utils.masks import format_protocolo
from core.utils.masks import normalize_protocolo
from .assunto_oficio import resolver_assunto_oficio
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
from .models import CONSTRAINT_NUMERO_OFICIO
from .models import ModeloMotivoOficio
from .models import Oficio
from .models import OficioNumeroLacuna

from roteiros.models import Roteiro

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
    cache_key: str,
):
    if not getattr(django_settings, "DOCUMENTOS_ARTIFACT_CACHE", True):
        return None
    art = get_cached_document_artifact(
        oficio_id=oficio_id,
        tipo=tipo,
        formato=formato,
        cache_key=cache_key,
    )
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


class OficioVinculadoError(Exception):
    """Exclusão bloqueada porque o ofício possui vínculos protegidos."""


class OficioNumeroConflitoError(Exception):
    """O número escolhido foi ocupado por outra requisição."""


def tocar_data_criacao_oficio(oficio: Oficio) -> Oficio:
    """Marca uma edição relevante do ofício, atualizando data_criacao para hoje."""
    oficio.data_criacao = timezone.localdate()
    oficio.save(update_fields=["data_criacao", "updated_at"])
    return oficio


def resolver_roteiro_padrao_evento(evento):
    """Retorna o roteiro do evento pronto para reuso (completo), ou None.

    Usado para pre-selecionar o roteiro do evento na Etapa 2 do oficio quando
    o oficio ainda nao tem um roteiro proprio vinculado.
    """
    if evento is None:
        return None

    from roteiros.selectors import queryset_roteiros_reutilizaveis_para_evento

    for roteiro in queryset_roteiros_reutilizaveis_para_evento(evento=evento):
        if roteiro.evento_id == evento.pk or roteiro.oficios.filter(evento=evento).exists():
            return roteiro
    return None


def obter_roteiro_escolhido_do_post(post, evento=None, area=None):
    """Retorna o Roteiro salvo selecionado no picker, ou None (sem efeitos colaterais)."""
    if (post.get("roteiro_modo") or "").strip() != "EVENTO_EXISTENTE":
        return None
    raw = post.get("roteiro_id") or post.get("roteiro_evento_id") or ""
    try:
        roteiro_id = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if not roteiro_id:
        return None
    area = area or getattr(evento, "area", None) or get_current_area()
    condicao = Q(tipo=Roteiro.TIPO_AVULSO)
    if evento is not None:
        condicao |= Q(evento=evento) | Q(oficios__evento=evento)
    # `BE-09`: `all_objects` — as quatro linhas abaixo aplicam o `area` recebido no
    # argumento (ou o do evento). Recortar de novo pela área ativa esvaziaria a
    # consulta sempre que as duas divergissem.
    queryset = Roteiro.all_objects.filter(condicao, pk=roteiro_id)
    if area is not None:
        queryset = queryset.filter(area=area)
    else:
        queryset = queryset.filter(area__isnull=True)
    return queryset.first()


@transaction.atomic
def vincular_roteiro_ao_oficio_sem_copia(oficio: Oficio, roteiro_escolhido: Roteiro, rascunho_antigo=None) -> None:
    """Vincula oficio diretamente ao roteiro existente (estado equivalente, sem alteracoes)."""
    if oficio.area_id != roteiro_escolhido.area_id:
        raise ValueError("Não é permitido vincular roteiro de outra área ao ofício.")
    oficio.roteiro = roteiro_escolhido
    oficio.save(update_fields=["roteiro", "updated_at"])

    if (
        rascunho_antigo is not None
        and rascunho_antigo.pk != roteiro_escolhido.pk
        and rascunho_antigo.status == Roteiro.STATUS_RASCUNHO
        and not rascunho_antigo.destinos.exists()
        and not rascunho_antigo.trechos.exists()
        and not Oficio.objects.filter(roteiro=rascunho_antigo).exclude(pk=oficio.pk).exists()
    ):
        try:
            rascunho_antigo.delete()
        except ProtectedError:
            pass


@dataclass(frozen=True)
class ResultadoRoteiroDoOficio:
    """O que a Etapa 2 gravou. A view traduz isto em mensagem e redirect."""

    #: O roteiro que ficou vinculado ao ofício.
    roteiro: Roteiro
    #: Vinculou ao roteiro escolhido no picker, sem gravar cópia.
    reusou_sem_copia: bool
    #: Materializou um `Roteiro` novo (o ofício não tinha rascunho próprio reaproveitável).
    criou_rascunho: bool
    #: Gravado sem validação completa (soft-advance do rodapé).
    parcial: bool


def _materializar_rascunho_do_oficio(oficio: Oficio) -> Roteiro:
    """Rascunho de roteiro próprio do ofício, ainda não persistido.

    `NOVO-88`: a área é a do **ofício**, sempre explícita. Antes disto havia duas cópias
    deste bloco na view e só uma passava `area=`; a outra deixava `Roteiro.save()`
    (`roteiros/models.py`) resolver por `get_current_area()`. As duas coincidiam por
    acidente — `get_oficio_by_id` lê o mesmo thread-local —, e fora de request a segunda
    gravava `area=NULL` contra o `NOT NULL` do `DB-02`.
    """
    area = oficio.area
    if area is None:
        # Compatibilidade transitória para ofícios legados ainda sem área: a
        # configuração resolve uma área explícita (única ou técnica), nunca NULL.
        from cadastros.models import ConfiguracaoSistema

        area = ConfiguracaoSistema.get_singleton().area
    return Roteiro(tipo=Roteiro.TIPO_AVULSO, status=Roteiro.STATUS_RASCUNHO, area=area)


def _revincular_roteiro_ao_oficio(oficio: Oficio, roteiro: Roteiro) -> None:
    """Aponta o ofício para o roteiro gravado, só quando muda."""
    if oficio.roteiro_id != roteiro.pk:
        oficio.roteiro = roteiro
        oficio.save(update_fields=["roteiro", "updated_at"])


@transaction.atomic
def salvar_roteiro_do_oficio(
    oficio: Oficio,
    post,
    form,
    *,
    roteiro_state,
    validated,
    diarias_resultado,
    roteiro_vinculado=None,
) -> ResultadoRoteiroDoOficio:
    """Decide entre reaproveitar o roteiro escolhido e gravar um próprio, e persiste.

    `BE-12`: esta é a regra que mais gera bug de dados no sistema, porque **roteiro é
    compartilhado entre ofícios**. Ela morava dentro de `wizard_roteiro`, o que a tornava
    intestável sem subir request e inalcançável pelo fluxo avulso.

    Duas travas que a decisão carrega, e que os testes congelam:

    - se o estado submetido equivale ao roteiro escolhido, **vincula sem copiar** — dois
      ofícios passam a apontar para a mesma linha, que é o desenho;
    - se não equivale, grava num rascunho **próprio**. Um roteiro que não é rascunho
      pertence a outros documentos e nunca é reescrito no lugar.

    `atomic` porque a requisição grava `Oficio`, `Roteiro`, `RoteiroDestino` e
    `RoteiroTrecho` — os services chamados são atômicos cada um, o conjunto não era
    (`BE-14`, item 1 da lista).
    """
    from roteiros.services import atualizar_roteiro
    from roteiros.services import roteiro_state_equivalente_ao_roteiro

    roteiro_escolhido = obter_roteiro_escolhido_do_post(
        post, evento=oficio.evento, area=oficio.area
    )
    if roteiro_escolhido and roteiro_state_equivalente_ao_roteiro(
        roteiro_escolhido, roteiro_state, validated
    ):
        rascunho_antigo = (
            roteiro_vinculado
            if (roteiro_vinculado and roteiro_vinculado.status == Roteiro.STATUS_RASCUNHO)
            else None
        )
        vincular_roteiro_ao_oficio_sem_copia(
            oficio, roteiro_escolhido, rascunho_antigo=rascunho_antigo
        )
        tocar_data_criacao_oficio(oficio)
        return ResultadoRoteiroDoOficio(
            roteiro=roteiro_escolhido,
            reusou_sem_copia=True,
            criou_rascunho=False,
            parcial=False,
        )

    criou = roteiro_vinculado is None or roteiro_vinculado.status != Roteiro.STATUS_RASCUNHO
    if criou:
        roteiro_vinculado = _materializar_rascunho_do_oficio(oficio)
        form.instance = roteiro_vinculado
    roteiro_salvo = atualizar_roteiro(
        roteiro_vinculado, form, roteiro_state, validated, diarias_resultado
    )
    _revincular_roteiro_ao_oficio(oficio, roteiro_salvo)
    tocar_data_criacao_oficio(oficio)
    return ResultadoRoteiroDoOficio(
        roteiro=roteiro_salvo,
        reusou_sem_copia=False,
        criou_rascunho=criou,
        parcial=False,
    )


@transaction.atomic
def salvar_rascunho_parcial_do_oficio(
    oficio: Oficio,
    form,
    *,
    roteiro_state,
    validated,
    roteiro_vinculado=None,
) -> ResultadoRoteiroDoOficio:
    """Soft-advance: grava o que houver e deixa navegar sem validação completa."""
    from roteiros.services import persistir_roteiro_rascunho_parcial

    criou = roteiro_vinculado is None or roteiro_vinculado.status != Roteiro.STATUS_RASCUNHO
    if criou:
        roteiro_vinculado = _materializar_rascunho_do_oficio(oficio)
        form.instance = roteiro_vinculado
    roteiro_salvo = persistir_roteiro_rascunho_parcial(
        roteiro_vinculado, form, roteiro_state, validated
    )
    _revincular_roteiro_ao_oficio(oficio, roteiro_salvo)
    tocar_data_criacao_oficio(oficio)
    return ResultadoRoteiroDoOficio(
        roteiro=roteiro_salvo,
        reusou_sem_copia=False,
        criou_rascunho=criou,
        parcial=True,
    )


def montar_roteiro_inicial_do_oficio(oficio: Oficio):
    """Estado do editor para o GET de um ofício **sem** roteiro próprio, sem gravar nada.

    Devolve `(form_instance, destinos_atuais, trechos_list, roteiro_state)`. Pré-seleciona
    o roteiro do evento quando há um completo pronto para reuso; senão parte de sede e
    destino do evento, sem datas — cada ofício tem horários próprios.
    """
    from roteiros.services import montar_estado_editor_roteiro_evento_selecionado
    from roteiros.services import montar_initial_roteiro_evento_sem_datas
    from roteiros.services import preparar_estado_editor_roteiro_para_get

    roteiro_padrao = resolver_roteiro_padrao_evento(oficio.evento)
    if roteiro_padrao is not None:
        destinos_atuais, trechos_list, roteiro_state = (
            montar_estado_editor_roteiro_evento_selecionado(roteiro_padrao)
        )
        form_instance = Roteiro(
            tipo=Roteiro.TIPO_AVULSO,
            status=Roteiro.STATUS_RASCUNHO,
            origem_cidade=roteiro_padrao.origem_cidade,
            origem_estado=roteiro_padrao.origem_estado,
            observacoes=roteiro_padrao.observacoes,
        )
        return form_instance, destinos_atuais, trechos_list, roteiro_state

    initial = montar_initial_roteiro_evento_sem_datas(oficio.evento)
    destinos_atuais, trechos_list, roteiro_state = preparar_estado_editor_roteiro_para_get(
        initial=initial
    )
    form_instance = Roteiro(tipo=Roteiro.TIPO_AVULSO, status=Roteiro.STATUS_RASCUNHO)
    if initial.get("origem_cidade"):
        form_instance.origem_cidade_id = initial["origem_cidade"]
    if initial.get("origem_estado"):
        form_instance.origem_estado_id = initial["origem_estado"]
    return form_instance, destinos_atuais, trechos_list, roteiro_state


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
    if oficio.area_id is None:
        oficio.area = get_current_area()
    oficio.data_criacao = oficio.data_criacao or timezone.localdate()
    oficio.custeio = oficio.custeio or Oficio.CUSTEIO_UNIDADE_DPC
    modelo_motivo = form.cleaned_data.get("modelo_motivo")
    aplicar_modelo_motivo_no_oficio(oficio, modelo_motivo, form.cleaned_data.get("motivo"))
    reservar_numero_oficio(oficio)
    atualizar_status_automatico_oficio(oficio, action=action, form=form)
    oficio.save()
    form.save_m2m()
    oficio.diarias_quantidade_servidores = max(oficio.servidores.count(), 1)
    # `BE-09`: o pk vem do ofício que acabou de ser criado nesta transação;
    # `all_objects` evita depender do contexto de área ao completar o mesmo registro.
    Oficio.all_objects.filter(pk=oficio.pk).update(
        diarias_quantidade_servidores=oficio.diarias_quantidade_servidores,
    )
    return oficio


@transaction.atomic
def atualizar_oficio_dados_viajantes(oficio, form, action="save_draft"):
    original = Oficio.objects.get(pk=oficio.pk)
    servidores_anteriores = set(
        original.servidores.values_list("pk", flat=True),
    )
    transporte_original = {
        "viatura": original.viatura,
        "porte_transporte_armas": original.porte_transporte_armas,
        "transporte_placa_manual": original.transporte_placa_manual,
        "transporte_modelo_manual": original.transporte_modelo_manual,
        "transporte_combustivel_manual": original.transporte_combustivel_manual,
        "transporte_tipo_manual": original.transporte_tipo_manual,
        "motorista_modo": original.motorista_modo,
        "motorista": original.motorista,
        "motorista_manual_nome": original.motorista_manual_nome,
        "motorista_manual_rg": original.motorista_manual_rg,
        "motorista_manual_cpf": original.motorista_manual_cpf,
        "motorista_manual_cargo": original.motorista_manual_cargo,
        "motorista_manual_unidade": original.motorista_manual_unidade,
        "motorista_manual_observacao": original.motorista_manual_observacao,
        "motorista_oficio_referencia": original.motorista_oficio_referencia,
        "motorista_protocolo_ref": original.motorista_protocolo_ref,
    }
    atualizado = form.save(commit=False)
    atualizado.diarias_quantidade_servidores = (
        original.diarias_quantidade_servidores
    )
    if atualizado.numero is None:
        atualizado.numero = original.numero
    # Ano não vem no formulário da etapa; rascunhos legados podem estar sem ano.
    atualizado.ano = original.ano or atualizado.ano or timezone.localdate().year
    atualizado.data_criacao = timezone.localdate()
    for field_name, value in transporte_original.items():
        setattr(atualizado, field_name, value)
    atualizado.custeio = atualizado.custeio or Oficio.CUSTEIO_UNIDADE_DPC
    modelo_motivo = form.cleaned_data.get("modelo_motivo")
    aplicar_modelo_motivo_no_oficio(atualizado, modelo_motivo, form.cleaned_data.get("motivo"))
    atualizar_status_automatico_oficio(atualizado, action=action, form=form)
    # `BE-15`: mesmo lock da reserva automática, **sem** o retry. Aqui o número foi
    # digitado pelo operador; trocá-lo em silêncio seria pior que devolver o erro, então
    # este caminho traduz a colisão em `OficioNumeroConflitoError` e devolve a tela.
    bloquear_escopo_numeracao(
        namespace=NAMESPACE_OFICIO,
        area_id=atualizado.area_id,
        ano=atualizado.ano,
        modelo=Oficio,
    )
    # `BE-09`: `all_objects` porque a checagem é sobre a área **deste** ofício, já
    # explícita no filtro. Com `objects`, área do registro diferente da ativa daria
    # consulta vazia: o conflito passaria batido aqui e voltaria como
    # `IntegrityError` cru no INSERT, em vez do `OficioNumeroConflitoError` que a
    # tela sabe apresentar.
    conflito = Oficio.all_objects.filter(
        area_id=atualizado.area_id,
        ano=atualizado.ano,
        numero=atualizado.numero,
    ).exclude(pk=atualizado.pk)
    if conflito.exists():
        raise OficioNumeroConflitoError(
            f"O número {atualizado.numero}/{atualizado.ano} acabou de ser usado "
            "por outro ofício. Atualize a página e escolha outro número.",
        )
    try:
        with transaction.atomic():
            atualizado.save()
    except IntegrityError as exc:
        # `BE-15`: identifica pelo metadado da exceção, com a ocupação como segundo
        # recurso. O texto do `IntegrityError` cita o nome da constraint no PostgreSQL e
        # as colunas no SQLite, então o casamento por substring só valia num dos dois.
        if not colisao_de_numero(
            exc,
            constraint=CONSTRAINT_NUMERO_OFICIO,
            ja_ocupado=lambda numero: _numero_de_oficio_ocupado(
                atualizado, numero=numero, ano=atualizado.ano
            ),
            numero=atualizado.numero,
        ):
            raise
        raise OficioNumeroConflitoError(
            f"O número {atualizado.numero}/{atualizado.ano} acabou de ser usado "
            "por outro ofício. Atualize a página e escolha outro número.",
        ) from exc
    form.save_m2m()
    servidores_atuais = set(atualizado.servidores.values_list("pk", flat=True))
    if (
        servidores_atuais != servidores_anteriores
        or atualizado.diarias_quantidade_servidores is None
    ):
        atualizado.diarias_quantidade_servidores = max(len(servidores_atuais), 1)
        # `BE-09`: o pk é da instância já carregada e validada por este service;
        # a atualização do snapshot não deve mudar de alvo com a área ativa.
        Oficio.all_objects.filter(pk=atualizado.pk).update(
            diarias_quantidade_servidores=atualizado.diarias_quantidade_servidores,
        )
    return atualizado


@transaction.atomic
def atualizar_oficio_transporte(oficio, form, action="save_draft"):
    _ = action
    atualizado = form.save(commit=False)
    atualizado.numero = oficio.numero
    atualizado.ano = oficio.ano
    atualizado.data_criacao = timezone.localdate()
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
def criar_oficio_rascunho(evento=None):
    """Cria um novo oficio a partir de um evento.

    So herda o motivo do evento (e o roteiro, resolvido depois na Etapa 2 do
    wizard). Servidores e viatura NAO sao copiados de outros oficios do mesmo
    evento: cada oficio costuma ter uma equipe/viatura propria.
    """
    seed = {}
    if evento is not None:
        from eventos.services import build_evento_document_seed

        seed = build_evento_document_seed(evento)
    area = None
    if evento is not None:
        area = getattr(evento, "area", None)
    if area is None:
        area = get_current_area()
    oficio = Oficio.objects.create(
        area=area,
        evento=evento,
        data_criacao=timezone.localdate(),
        status=Oficio.STATUS_RASCUNHO,
        custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        motivo=seed.get("motivo") or "",
        solicitante=getattr(evento, "unidade_responsavel", None) if evento is not None else None,
    )
    reservar_numero_oficio(oficio, ano=oficio.data_criacao.year)
    return oficio


def get_next_available_numero_oficio(ano, area=None):
    # Fonte única da lógica de numeração (inclui o piso por ano via settings).
    return Oficio.get_next_available_numero(ano, area=area)


def _numero_de_oficio_ocupado(oficio, *, numero: int, ano: int) -> bool:
    """Alguém já gravou este (área, ano, número)?

    `BE-15`: é o segundo recurso para distinguir "perdi a corrida" de "violei outra
    constraint", quando o banco não oferece o metadado da exceção. Ver o cabeçalho de
    `core/numeracao.py`.
    """
    return (
        # `BE-09`: `all_objects` — o escopo é a área **deste** ofício, e ela vem explícita
        # no filtro da própria linha. Com `objects`, um ofício de área diferente da ativa
        # daria consulta vazia: a colisão passaria por "não é minha" e o `IntegrityError`
        # subiria cru em vez de virar nova tentativa.
        Oficio.all_objects.filter(area_id=oficio.area_id, ano=ano, numero=numero)
        .exclude(pk=oficio.pk)
        .exists()
    )


@transaction.atomic
def reservar_numero_oficio(oficio, ano=None):
    if oficio.numero and oficio.ano:
        return oficio

    resolved_year = ano or timezone.localdate().year
    original_pk = oficio.pk
    original_adding = oficio._state.adding

    def escolher():
        return get_next_available_numero_oficio(resolved_year, area=oficio.area)

    def gravar(numero):
        oficio.ano = resolved_year
        oficio.numero = numero
        oficio.save()

    def limpar():
        oficio.numero = None
        oficio.ano = None
        if original_adding:
            oficio.pk = original_pk
            oficio._state.adding = True

    reservar_numero(
        namespace=NAMESPACE_OFICIO,
        area_id=oficio.area_id,
        ano=resolved_year,
        modelo=Oficio,
        constraint=CONSTRAINT_NUMERO_OFICIO,
        escolher=escolher,
        gravar=gravar,
        ja_ocupado=lambda numero: _numero_de_oficio_ocupado(
            oficio, numero=numero, ano=resolved_year
        ),
        apos_colisao=limpar,
    )
    return oficio


def avaliar_oficio_dados_viajantes(oficio=None, form=None):
    if form is not None:
        values = _dados_viajantes_from_form(form)
    elif oficio is not None:
        values = _dados_viajantes_from_oficio(oficio)
    else:
        values = {}

    pendencias = []
    if not values.get("protocolo"):
        pendencias.append("Informe o protocolo.")
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
        track_sla=True,
    ):
        payload = build_canonical_document_payload(oficio, DocumentoTipo.OFICIO)
        docxtpl = build_oficio_docxtpl_context(oficio)
        reference = oficio.numero_formatado.replace("/", "-")
        cache_key = _document_cache_key(
            tipo=DocumentoTipo.OFICIO,
            formato=formato,
            reference=reference,
            payload=payload,
            docxtpl_context=docxtpl,
            prefer_docx=True,
        )
        hit = _try_cached_download(
            oficio_id=oficio.pk,
            tipo=DocumentoTipo.OFICIO,
            formato=formato,
            reference=reference,
            cache_key=cache_key,
        )
        if hit is not None:
            return hit
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
        track_sla=True,
    ):
        payload = build_justificativa_payload(oficio)
        docxtpl = build_justificativa_docxtpl_context(oficio)
        reference = f"{oficio.numero_formatado.replace('/', '-')}-justificativa"
        cache_key = _document_cache_key(
            tipo=DocumentoTipo.JUSTIFICATIVA,
            formato=formato,
            reference=reference,
            payload=payload,
            docxtpl_context=docxtpl,
            prefer_docx=True,
        )
        hit = _try_cached_download(
            oficio_id=oficio.pk,
            tipo=DocumentoTipo.JUSTIFICATIVA,
            formato=formato,
            reference=reference,
            cache_key=cache_key,
        )
        if hit is not None:
            return hit
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
            "protocolo": str(get_value("protocolo", "") or "").strip(),
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
        "protocolo": oficio.protocolo.strip(),
        "custeio": oficio.custeio,
        "custeio_observacao": oficio.custeio_observacao.strip(),
        "servidores_count": servidores_count,
        "has_started": bool(oficio.pk) or any(value.strip() for value in text_values) or bool(servidores_count),
    }


@transaction.atomic
def excluir_oficio(instance):
    numero, ano, area = instance.numero, instance.ano, instance.area
    try:
        excluir_com_protecao(instance)
    except DelecaoProtegidaError as exc:
        raise OficioVinculadoError from exc
    if numero and ano:
        # `BE-09`: `all_objects` — a lacuna pertence à área do ofício excluído, que
        # já vem explícita. Com `objects` e área diferente da ativa, o `get` não
        # acharia a lacuna existente e o `create` estouraria em
        # `oficios_lacuna_area_ano_numero_unique`.
        OficioNumeroLacuna.all_objects.get_or_create(area=area, ano=ano, numero=numero)


def cancelar_oficio(instance: Oficio, motivo: str) -> Oficio:
    """Cancela o ofício. A partir daí ele não gera novas prestações de contas
    e não pode mais ser selecionado para compor uma nova Ordem de Serviço."""
    instance.cancelar(motivo)
    return instance


def retificar_oficio(instance: Oficio) -> Oficio:
    """Marca o ofício como retificado: o documento passa a exibir "Retificado"
    ao lado do número no lugar de "Autorização". Mutuamente exclusivo com a
    marcação de complementar."""
    instance.retificado_documento = True
    instance.complementar_documento = False
    instance.save(update_fields=["retificado_documento", "complementar_documento"])
    return instance


def desfazer_retificacao_oficio(instance: Oficio) -> Oficio:
    instance.retificado_documento = False
    instance.save(update_fields=["retificado_documento"])
    return instance


def marcar_oficio_complementar(instance: Oficio) -> Oficio:
    """Marca o ofício como complementar: o documento passa a exibir "Complementar"
    ao lado do número. Mutuamente exclusivo com a retificação."""
    instance.complementar_documento = True
    instance.retificado_documento = False
    instance.save(update_fields=["retificado_documento", "complementar_documento"])
    return instance


def desfazer_complementar_oficio(instance: Oficio) -> Oficio:
    instance.complementar_documento = False
    instance.save(update_fields=["complementar_documento"])
    return instance


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
    assunto_doc = resolver_assunto_oficio(oficio)
    return {
        "numero": oficio.numero,
        "ano": oficio.ano,
        "numero_formatado": oficio.numero_formatado,
        "protocolo": format_protocolo(oficio.protocolo),
        "assunto": oficio.assunto,
        "assunto_oficio": assunto_doc["assunto_oficio"],
        "assunto_linha": assunto_doc["assunto_linha"],
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
    if not modelo.area_id:
        from core.tenancy import get_current_area

        modelo.area = get_current_area()
    if modelo.is_padrao:
        # `BE-09`: `all_objects` — desmarcar o padrão anterior é sobre a área do
        # modelo, já no filtro. Recortado pela área ativa, o padrão antigo
        # sobreviveria e a gravação estouraria em
        # `oficios_motivo_area_padrao_unique`.
        ModeloMotivoOficio.all_objects.exclude(pk=modelo.pk).filter(area=modelo.area).update(
            is_padrao=False,
        )
    modelo.save()
    return modelo


@transaction.atomic
def atualizar_modelo_motivo(instance, form):
    _ = instance
    modelo = form.save(commit=False)
    if not modelo.area_id:
        from core.tenancy import get_current_area

        modelo.area = get_current_area()
    if modelo.is_padrao:
        # `BE-09`: `all_objects` — desmarcar o padrão anterior é sobre a área do
        # modelo, já no filtro. Recortado pela área ativa, o padrão antigo
        # sobreviveria e a gravação estouraria em
        # `oficios_motivo_area_padrao_unique`.
        ModeloMotivoOficio.all_objects.exclude(pk=modelo.pk).filter(area=modelo.area).update(
            is_padrao=False,
        )
    modelo.save()
    return modelo


@transaction.atomic
def excluir_modelo_motivo(instance):
    excluir_com_protecao(instance)


@transaction.atomic
def criar_rascunho_de_roteiro_do_oficio(oficio: Oficio, *, area, campos, snapshots):
    """Cria o rascunho próprio de roteiro do ofício e já vincula, numa operação só.

    `BE-14` fatia 5. São duas gravações em objetos diferentes: o `Roteiro` nasce e o
    `Oficio` recebe o vínculo. Sem transação, uma falha na segunda deixava um **roteiro
    órfão** — sem ofício, sem evento e sem tela que o alcance — enquanto o ofício voltava
    a se comportar como se o usuário nunca tivesse desmarcado o roteiro do evento. Ou
    seja: a falha reintroduzia justamente o defeito que esta rota foi escrita para
    corrigir, e ainda deixava lixo no banco.

    Devolve `(roteiro, version)`.
    """
    from roteiros.services.autosave import apply_roteiro_autosave
    from roteiros.services.autosave import build_roteiro_draft

    roteiro = build_roteiro_draft(area=area)
    version = apply_roteiro_autosave(roteiro, campos, snapshots)
    _garantir_sede_do_rascunho(roteiro)
    _revincular_roteiro_ao_oficio(oficio, roteiro)
    return roteiro, version


def _garantir_sede_do_rascunho(roteiro: Roteiro) -> None:
    """Dá ao rascunho a sede da configuração quando ela não veio suja no payload.

    A sede exibida na tela é herdada do evento/configuração e não chega no autosave se o
    usuário nunca clicou nela — sem isto o rascunho nasceria sem sede. Regra anterior ao
    `BE-14`.
    """
    if roteiro.origem_cidade_id or roteiro.origem_estado_id:
        return
    from cadastros.services import resolver_sede_ids_desde_configuracao

    estado_id, cidade_id, _aviso = resolver_sede_ids_desde_configuracao()
    if estado_id and cidade_id:
        roteiro.origem_estado_id = estado_id
        roteiro.origem_cidade_id = cidade_id
        roteiro.save(update_fields=["origem_estado", "origem_cidade", "updated_at"])
