
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.pagination import contexto_paginacao

from cadastros.selectors import get_configuracao_sistema
from core.autosave import AutosavePayloadError
from core.autosave import autosave_json_response
from core.autosave import parse_autosave_payload
from core.normalizers import normalize_spaces
from core.retorno import voltar_para
from documentos.services.async_generation import enfileirar_documento

from .diario_views import (
    diario_autosave,
    diario_criar,
    diario_download,
    diario_editar_roteiro,
    diario_motorista,
    diario_servidor,
    diario_servidor_autosave,
    diario_servidor_editar_roteiro,
    diario_servidor_motorista,
)
from .document_views import (
    documentos,
    documentos_servidor,
    prestacao_arquivo_autosave,
    prestacao_despacho_assinado_anexar,
    prestacao_documento_conteudo,
    prestacao_documento_excluir,
    prestacao_oficio_assinado_anexar,
    prestacao_servidor_arquivo_autosave,
    prestacao_servidor_assinado_anexar,
)
from .model_views import modelo_editar
from .model_views import modelo_excluir
from .model_views import modelo_novo
from .model_views import modelos_index
from .assinatura_services import AssinaturaError
from .assinatura_services import assinatura_db
from .assinatura_services import assinatura_rt
from .assinatura_services import cancelar_assinatura_db
from .assinatura_services import cancelar_assinatura_rt
from .assinatura_services import emitir_link_db
from .assinatura_services import emitir_link_rt
from .assinatura_services import signer_db
from .assinatura_services import signer_rt
from .models import AssinaturaDocumento
from .diario_services import diaria_info
from .diario_services import garantir_roteiro_ajustado
from .diario_services import motorista_diario
from .diario_services import motorista_do_oficio
from .diario_services import sincronizar_trechos
from .diario_services import viatura_resumo_diario
from .diario_services import viatura_resumo_oficio
from .forms import CAMPOS_COM_MODELO
from .forms import CAMPOS_CUSTEIO_COM_OUTRO
from .forms import DiarioBordoTrechoFormSet
from .forms import DiarioMotoristaForm
from .forms import ModeloTextoRelatorioTecnicoForm
from .forms import OUTRO_VALUE
from .forms import PrestacaoDespachoForm
from .forms import PrestacaoServidorDiariaForm
from .forms import PrestacaoServidorDocumentosForm
from .forms import PrestacaoSolicitacaoForm
from .forms import RelatorioTecnicoForm
from .forms import get_custeio_valores_fixos
from .models import DiarioBordo
from .models import ModeloTextoRelatorioTecnico
from .models import PrestacaoContas
from .models import PrestacaoDocumentoAnexo
from .models import PrestacaoServidor
from .models import RelatorioTecnico
from .presenters import _anexo_assinado_info
from .presenters import apresentar_prestacao_servidor_card
from .presenters import marcar_agrupamento_cards
from .selectors import ABA_ARQUIVADOS
from .selectors import ABA_FINALIZADOS
from .selectors import ABA_LIBERADAS
from .selectors import ABA_NAO_LIBERADAS
from .selectors import contar_por_aba
from .selectors import listar_prestacoes
from .selectors import normalizar_aba
from .selectors import normalizar_abas
from .services import diaria_inicial_da_prestacao
from .services import garantir_campos_padrao_relatorio_tecnico
from .solicitacao_services import ResultadoSolicitacao
from .solicitacao_services import salvar_solicitacao_do_autosave
from .solicitacao_services import salvar_solicitacoes_em_lote
from .solicitacao_services import valores_do_lote
































from .rt_views import (
    rt_autosave,
    rt_criar,
    rt_download_servidor,
    rt_servidor,
    rt_servidor_autosave,
)
from .signature_views import (
    _assinatura_db_card,
    _assinatura_rt_card,
    assinatura_db_cancelar,
    assinatura_db_gerar,
    assinatura_rt_cancelar,
    assinatura_rt_gerar,
)
from .view_common import (
    _autosave_form_errors,
    _autosave_version,
    _build_campos_custeio,
    _build_campos_modelo,
    _build_identificacao,
    contexto_do_fluxo,
    _diario_queryset,
    _is_inline_request,
    _prestacao_full,
    _prestacao_queryset,
    _prestacao_servidor_full,
    _prestacao_servidor_queryset,
    _primeiro_servidor,
    _redirect_primeiro_servidor,
    _preview_error_response,
    _relatorio_queryset,
)

# QA-07 — a superfície pública deste módulo, escrita.
#
# Aqui a fachada do P-06 está pela metade: 98 nomes vêm de módulos irmãos e
# 16 ainda são definidos neste arquivo. Os dois grupos entram, porque `urls.py`
# chega em todos por `views.<nome>`. Sem `__all__` o ruff acusava cada
# re-export como import morto (`F401`) e escondia os que realmente eram.
__all__ = [
    "ABA_ARQUIVADOS",
    "ABA_FINALIZADOS",
    "ABA_LIBERADAS",
    "ABA_NAO_LIBERADAS",
    "AssinaturaDocumento",
    "AssinaturaError",
    "CAMPOS_COM_MODELO",
    "CAMPOS_CUSTEIO_COM_OUTRO",
    "DiarioBordo",
    "DiarioBordoTrechoFormSet",
    "DiarioMotoristaForm",
    "ModeloTextoRelatorioTecnico",
    "ModeloTextoRelatorioTecnicoForm",
    "OUTRO_VALUE",
    "PrestacaoContas",
    "PrestacaoDespachoForm",
    "PrestacaoDocumentoAnexo",
    "PrestacaoServidor",
    "PrestacaoServidorDiariaForm",
    "PrestacaoServidorDocumentosForm",
    "PrestacaoSolicitacaoForm",
    "RelatorioTecnico",
    "RelatorioTecnicoForm",
    "_anexo_assinado_info",
    "_assinatura_db_card",
    "_assinatura_rt_card",
    "_autosave_form_errors",
    "_autosave_version",
    "_build_abas",
    "_build_campos_custeio",
    "_build_campos_modelo",
    "_build_identificacao",
    "_date_autosave_value",
    "_diario_queryset",
    "_is_inline_request",
    "_prestacao_full",
    "_prestacao_queryset",
    "_prestacao_servidor_full",
    "_prestacao_servidor_queryset",
    "_preview_error_response",
    "_primeiro_servidor",
    "_redirect_lista",
    "_redirect_primeiro_servidor",
    "_relatorio_queryset",
    "_salvar_solicitacoes_em_lote",
    "_servidor_consolidado_ctx",
    "_solicitacao_autosave_value",
    "apresentar_prestacao_servidor_card",
    "assinatura_db",
    "assinatura_db_cancelar",
    "assinatura_db_gerar",
    "assinatura_rt",
    "assinatura_rt_cancelar",
    "assinatura_rt_gerar",
    "cancelar_assinatura_db",
    "cancelar_assinatura_rt",
    "consolidado",
    "consolidado_download",
    "consolidado_servidor",
    "contar_por_aba",
    "contexto_do_fluxo",
    "diaria_info",
    "diaria_inicial_da_prestacao",
    "diario_autosave",
    "diario_criar",
    "diario_download",
    "diario_editar_roteiro",
    "diario_motorista",
    "diario_servidor",
    "diario_servidor_autosave",
    "diario_servidor_editar_roteiro",
    "diario_servidor_motorista",
    "documentos",
    "documentos_servidor",
    "emitir_link_db",
    "emitir_link_rt",
    "garantir_campos_padrao_relatorio_tecnico",
    "garantir_roteiro_ajustado",
    "get_custeio_valores_fixos",
    "index",
    "listar_prestacoes",
    "marcar_agrupamento_cards",
    "modelo_editar",
    "modelo_excluir",
    "modelo_novo",
    "modelos_index",
    "motorista_diario",
    "motorista_do_oficio",
    "normalizar_aba",
    "prestacao_arquivar",
    "prestacao_arquivo_autosave",
    "prestacao_despacho_assinado_anexar",
    "prestacao_documento_conteudo",
    "prestacao_documento_excluir",
    "prestacao_finalizar",
    "prestacao_oficio_assinado_anexar",
    "prestacao_servidor_arquivar",
    "prestacao_servidor_arquivo_autosave",
    "prestacao_servidor_assinado_anexar",
    "prestacao_servidor_finalizar",
    "prestacao_servidor_solicitacao_autosave",
    "rt_autosave",
    "rt_criar",
    "rt_download_servidor",
    "rt_servidor",
    "rt_servidor_autosave",
    "signer_db",
    "signer_rt",
    "sincronizar_trechos",
    "viatura_resumo_diario",
    "viatura_resumo_oficio",
]











def _solicitacao_autosave_value(payload):
    for name, value in payload.fields.items():
        clean_name = str(name or "").strip()
        if clean_name == "numero_solicitacao" or clean_name.endswith("-numero_solicitacao"):
            return normalize_spaces(value or "")
    return None


def _date_autosave_value(payload, field_name):
    """Valor ISO bruto (ou vazio) de um campo de data individual, se presente."""
    for name, value in payload.fields.items():
        clean_name = str(name or "").strip()
        if clean_name == field_name or clean_name.endswith(f"-{field_name}"):
            return (value or "").strip()
    return None
















_ABA_LABELS = [
    (ABA_NAO_LIBERADAS, "Não liberadas"),
    (ABA_LIBERADAS, "Liberadas"),
    (ABA_ARQUIVADOS, "Arquivados"),
    (ABA_FINALIZADOS, "Finalizados"),
]

_ABA_EMPTY_MESSAGE = {
    ABA_NAO_LIBERADAS: "Nenhum servidor com diárias pendentes de liberação.",
    ABA_LIBERADAS: "Nenhum servidor com diárias já liberadas.",
    ABA_ARQUIVADOS: "Nenhuma prestação de servidor arquivada.",
    ABA_FINALIZADOS: "Nenhuma prestação de servidor finalizada ainda.",
}


def _build_abas(request, aba_atual, contagem, *, q="", status="", sort=""):
    """Abas da lista, cada uma como link que preserva a busca/ordenação atuais."""
    from urllib.parse import urlencode

    base_params = [(k, v) for k, v in (("q", q), ("status", status), ("sort", sort)) if v]
    base_url = reverse("prestacoes_contas:index")
    abas = []
    for chave, label in _ABA_LABELS:
        query = urlencode([("aba", chave), *base_params])
        abas.append(
            {
                "key": chave,
                "label": label,
                "count": contagem.get(chave, 0),
                "url": f"{base_url}?{query}",
                "is_active": chave == aba_atual,
            }
        )
    return abas


def index(request):
    if request.method == "POST" and request.POST.get("action") == "save_solicitacoes":
        resultado = _salvar_solicitacoes_em_lote(request)
        if resultado.erro:
            messages.error(request, resultado.erro)
        else:
            messages.success(request, "Números de solicitação salvos.")
        return redirect("prestacoes_contas:index")

    q         = request.GET.get("q",         "").strip()
    status    = request.GET.get("status",    "").strip()
    # Situação é MULTISSELEÇÃO e nasce VAZIA (2026-08-21): a lista abre inteira.
    # Mesmo contrato das demais listas. A aba padrão daqui era `nao_liberadas`,
    # que é uma fila de trabalho legítima — mas ela abria a tela escondendo
    # liberadas, arquivadas e finalizadas sem dizer que havia recorte ligado.
    valores_abas = request.GET.getlist("aba")
    abas_selecionadas = normalizar_abas(valores_abas) if valores_abas else []
    viagem_de = request.GET.get("viagem_de", "").strip()
    viagem_ate = request.GET.get("viagem_ate", "").strip()
    sort      = request.GET.get("sort",      "").strip()

    prestacoes = listar_prestacoes(
        q=q or None,
        status=status or None,
        aba=abas_selecionadas,
        viagem_de=viagem_de or None,
        viagem_ate=viagem_ate or None,
        sort=sort or None,
    )

    paginacao = contexto_paginacao(prestacoes, request, 20)
    page_obj = paginacao["page_obj"]
    # `NOVO-08`: uma consulta para a página inteira, não uma por card.
    configuracao = get_configuracao_sistema()
    cards = marcar_agrupamento_cards(
        [
            apresentar_prestacao_servidor_card(ps, configuracao=configuracao)
            for ps in page_obj.object_list
        ]
    )

    has_filters = any([q, status, viagem_de, viagem_ate, sort, abas_selecionadas])

    contagem = contar_por_aba(
        q=q or None,
        status=status or None,
        viagem_de=viagem_de or None,
        viagem_ate=viagem_ate or None,
    )
    escolhidas = set(abas_selecionadas)
    situacao_options = [
        {
            "value": chave,
            "label": f"{label} ({contagem.get(chave, 0)})",
            "selected": chave in escolhidas,
        }
        for chave, label in _ABA_LABELS
    ]

    return render(
        request,
        "prestacoes_contas/index.html",
        {
            "page_title": "Prestações de Contas",
            "page_description": "Acompanhamento das prestações de contas por servidor, agrupadas por ofício.",
            "cards": cards,
            **paginacao,
            "q":          q,
            "status":     status,
            "abas_selecionadas": abas_selecionadas,
            "situacao_options": situacao_options,
            "viagem_de":  viagem_de,
            "viagem_ate": viagem_ate,
            "sort":       sort,
            "has_filters": has_filters,
            # "Limpar" limpa TUDO, situação inclusive: com a lista abrindo
            # inteira, preservar a aba devolveria o filtro que acabou de ser
            # dispensado.
            "search_clear_url": reverse("prestacoes_contas:index"),
            "status_options": [{"value": "", "label": "Todos os status"}]
            + [{"value": valor, "label": rotulo} for valor, rotulo in PrestacaoServidor.STATUS_CHOICES],
            # Com UMA situação escolhida, a frase dela; com várias ou nenhuma,
            # a genérica — juntar quatro frases de vazio numa só não ajudaria
            # ninguém a entender o que está faltando.
            "empty_message": (
                _ABA_EMPTY_MESSAGE.get(
                    abas_selecionadas[0], "Nenhuma prestação de contas encontrada."
                )
                if len(abas_selecionadas) == 1
                else "Nenhuma prestação de contas encontrada."
            ),
            "sort_options": [
                {"value": "criacao_desc",  "label": "Criação: mais recente"},
                {"value": "criacao_asc",   "label": "Criação: mais antiga"},
                {"value": "viagem_asc",    "label": "Viagem: mais próxima"},
                {"value": "viagem_desc",   "label": "Viagem: mais distante"},
                {"value": "oficio_asc",    "label": "Ofício: crescente"},
                {"value": "oficio_desc",   "label": "Ofício: decrescente"},
            ],
        },
    )


def _salvar_solicitacoes_em_lote(request):
    """Fallback sem JS para solicitação e período de liberação de cada servidor."""
    valores = valores_do_lote(request.POST)
    if not valores:
        return ResultadoSolicitacao()
    servidores = _prestacao_servidor_queryset().filter(pk__in=valores)
    return salvar_solicitacoes_em_lote(servidores, valores)


def _redirect_lista(request, _obj=None):
    """Volta para a lista preservando a aba/filtros de onde a ação foi disparada."""
    return redirect(voltar_para(request, reverse("prestacoes_contas:index")))


@require_POST
def prestacao_servidor_arquivar(request, ps_pk):
    """Arquiva ou desarquiva a prestação deste servidor."""
    ps = get_object_or_404(_prestacao_servidor_queryset(), pk=ps_pk)
    ps.definir_arquivada(not ps.arquivada)
    if ps.arquivada:
        messages.success(request, f"Prestação de {ps.servidor.nome} arquivada.")
    else:
        messages.success(request, f"Prestação de {ps.servidor.nome} desarquivada.")
    return _redirect_lista(request)


@require_POST
def prestacao_servidor_finalizar(request, ps_pk):
    """Conclui ou reabre a prestação deste servidor."""
    ps = get_object_or_404(_prestacao_servidor_queryset(), pk=ps_pk)
    ps.definir_finalizada(not ps.finalizada)
    if ps.finalizada:
        messages.success(request, f"Prestação de {ps.servidor.nome} finalizada.")
    else:
        messages.success(request, f"Prestação de {ps.servidor.nome} reaberta.")
    return _redirect_lista(request)


@require_POST
def prestacao_arquivar(request, pc_pk):
    """Compatibilidade: arquiva o primeiro servidor da prestação do ofício."""
    prestacao = get_object_or_404(_prestacao_queryset(), pk=pc_pk)
    ps = _primeiro_servidor(prestacao)
    if ps is None:
        messages.error(request, "Esta prestação ainda não possui servidores.")
        return _redirect_lista(request)
    return prestacao_servidor_arquivar(request, ps.pk)


@require_POST
def prestacao_finalizar(request, pc_pk):
    """Compatibilidade: finaliza o primeiro servidor da prestação do ofício."""
    prestacao = get_object_or_404(_prestacao_queryset(), pk=pc_pk)
    ps = _primeiro_servidor(prestacao)
    if ps is None:
        messages.error(request, "Esta prestação ainda não possui servidores.")
        return _redirect_lista(request)
    return prestacao_servidor_finalizar(request, ps.pk)


@require_POST
def prestacao_servidor_solicitacao_autosave(request, ps_pk):
    ps = get_object_or_404(_prestacao_servidor_queryset(), pk=ps_pk)
    try:
        payload = parse_autosave_payload(request, expected_model="prestacao_servidor")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    resultado = salvar_solicitacao_do_autosave(
        ps,
        numero=_solicitacao_autosave_value(payload),
        datas={
            campo: _date_autosave_value(payload, campo)
            for campo in ("data_liberacao_diarias", "prazo_limite_saque")
        },
    )
    if resultado.erro:
        return autosave_json_response(ok=False, message=resultado.erro)

    return autosave_json_response(
        ok=True,
        object_id=ps.pk,
        version=_autosave_version(ps),
    )










def _servidor_consolidado_ctx(request, ps):
    return {
        "ps_pk": ps.pk,
        "nome": ps.servidor.nome,
        "is_motorista": ps.is_motorista,
        "numero_solicitacao": ps.numero_solicitacao,
        "numero_ok": bool((ps.numero_solicitacao or "").strip()),
        "assinatura_rt": _assinatura_rt_card(request, ps),
        "download_url": reverse("prestacoes_contas:consolidado_download", args=[ps.pk]),
        "preview_inline_url": reverse("prestacoes_contas:consolidado_download", args=[ps.pk]) + "?inline=1",
    }






@require_POST


@require_POST






@require_POST


@require_POST


@require_POST


@require_POST


# ─────────────────────────────────────────────────────────────────
# Assinatura eletrônica (RT por servidor e Diário de Bordo por ofício)
# ─────────────────────────────────────────────────────────────────









@require_POST


@require_POST


@require_POST


@require_POST






@require_POST


@require_POST








@require_POST


@require_POST




















def consolidado(request, pc_pk):
    """Compatibilidade: redireciona para o primeiro servidor."""
    prestacao = get_object_or_404(_prestacao_queryset(), pk=pc_pk)
    return _redirect_primeiro_servidor(request, prestacao, "prestacoes_contas:consolidado_servidor")


def consolidado_servidor(request, ps_pk):
    ps = _prestacao_servidor_full(ps_pk)
    prestacao = ps.prestacao

    return render(
        request,
        "prestacoes_contas/consolidado.html",
        {
            "page_title": f"PDF Final — {ps.servidor.nome}",
            "prestacao": prestacao,
            "ps": ps,
            "identificacao": _build_identificacao(prestacao),
            **contexto_do_fluxo(ps, "consolidado"),
            "servidores": [_servidor_consolidado_ctx(request, ps)],
            "back_url": reverse("prestacoes_contas:index"),
            "documentos_url": reverse("prestacoes_contas:documentos_servidor", args=[ps.pk]),
        },
    )


def consolidado_download(request, ps_pk):
    ps = get_object_or_404(
        _prestacao_servidor_queryset().select_related(
            "prestacao__oficio__roteiro", "servidor"
        ).prefetch_related("prestacao__servidores_prestacao"),
        pk=ps_pk,
    )
    inline = _is_inline_request(request)
    return enfileirar_documento(
        request,
        tipo="prestacao_consolidado",
        parametros={"object_id": ps.pk, "formato": "pdf"},
        disposicao="inline" if inline else "attachment",
    )


# O gerenciamento de modelos de texto do RT vive em `model_views.py` — as views
# estão re-exportadas no topo deste arquivo. `_CAMPO_LABELS` foi junto (`NOVO-03`).
