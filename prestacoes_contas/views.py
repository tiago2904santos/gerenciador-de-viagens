from pathlib import Path
import json
import re

from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from django.views.decorators.http import require_POST

from core.autosave import AutosavePayloadError
from core.autosave import autosave_json_response
from core.autosave import filter_allowed_fields
from core.autosave import parse_autosave_payload
from core.normalizers import normalize_spaces
from core.normalizers import remove_accents
from core.presenters.meta import build_meta
from core.utils.masks import format_cpf
from core.utils.masks import format_placa
from core.utils.masks import format_protocolo
from documentos.services.exceptions import DocumentValidationError
from oficios.models import Oficio

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
from .diario_services import gerar_diario_bordo_xlsx
from .diario_services import motorista_diario
from .diario_services import motorista_do_oficio
from .diario_services import nome_arquivo_diario
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
from .forms import PrestacaoServidorDocumentosForm
from .forms import RelatorioTecnicoForm
from .forms import get_custeio_valores_fixos
from .models import DiarioBordo
from .models import ModeloTextoRelatorioTecnico
from .models import PrestacaoContas
from .models import PrestacaoDocumentoAnexo
from .models import PrestacaoServidor
from .models import RelatorioTecnico
from .presenters import apresentar_prestacao_card
from .selectors import ABA_ARQUIVADOS
from .selectors import ABA_FINALIZADOS
from .selectors import ABA_FUTURAS
from .selectors import ABA_PENDENTES
from .selectors import contar_por_aba
from .selectors import listar_prestacoes
from .selectors import normalizar_aba
from .services import gerar_relatorio_tecnico_docx
from .services import gerar_prestacao_consolidado_pdf
from .services import diaria_inicial_da_prestacao
from .services import garantir_campos_padrao_relatorio_tecnico
from .services import nome_arquivo_prestacao_consolidado
from .services import nome_arquivo_rt


def _destino_display(oficio) -> str:
    try:
        destinos = list(oficio.roteiro.destinos.select_related("cidade", "estado").order_by("ordem"))
        if not destinos:
            return ""
        parts = [f"{d.cidade} ({d.estado.sigla})" for d in destinos[:3]]
        result = ", ".join(parts)
        if len(destinos) > 3:
            result += f" +{len(destinos) - 3}"
        return result
    except Exception:
        return ""


def _periodo_display(oficio) -> str:
    try:
        from django.utils import timezone as tz_module
        roteiro = oficio.roteiro
        saida_dt = roteiro.saida_dt
        if not saida_dt:
            return ""
        current_tz = tz_module.get_current_timezone()
        saida = saida_dt.astimezone(current_tz).date() if tz_module.is_aware(saida_dt) else saida_dt.date()
        chegada_dt = getattr(roteiro, "retorno_chegada_dt", None) or getattr(roteiro, "chegada_dt", None)
        if chegada_dt:
            chegada = chegada_dt.astimezone(current_tz).date() if tz_module.is_aware(chegada_dt) else chegada_dt.date()
            if saida == chegada:
                return saida.strftime("%d/%m/%Y")
            return f"{saida.strftime('%d/%m/%Y')} a {chegada.strftime('%d/%m/%Y')}"
        return saida.strftime("%d/%m/%Y")
    except Exception:
        return ""


def _build_campos_modelo(form) -> list:
    """Para cada campo de texto longo: select de modelos + textarea + URL de gerência."""
    base_url = reverse("prestacoes_contas:modelos_index")
    campos = []
    for campo, label in CAMPOS_COM_MODELO:
        select = form[f"modelo_{campo}"]
        campos.append(
            {
                "campo": campo,
                "label": label,
                "select": select,
                "textarea": form[campo],
                "manage_url": f"{base_url}#grupo-{campo}",
                "tem_modelos": select.field.queryset.exists(),
            }
        )
    return campos


def _build_campos_custeio(form) -> list:
    campos = [
        {
            "campo": "diaria",
            "label": "Diária",
            "field": form["diaria"],
            "other": None,
            "uses_other": False,
        }
    ]
    for campo, label in CAMPOS_CUSTEIO_COM_OUTRO:
        campos.append(
            {
                "campo": campo,
                "label": label,
                "field": form[campo],
                "other": form[f"{campo}_outro"],
                "uses_other": True,
            }
        )
    return campos


def _servidor_identificacao(ps) -> dict:
    servidor = ps.servidor
    return {
        "ps_pk": ps.pk,
        "nome_servidor": servidor.nome,
        "cpf_servidor": servidor.cpf_formatado,
        "cargo": str(servidor.cargo) if servidor.cargo_id else "—",
        "unidade": str(servidor.unidade) if servidor.unidade_id else "",
        "is_motorista": ps.is_motorista,
        "numero_solicitacao": ps.numero_solicitacao,
    }


def _build_identificacao(prestacao) -> dict:
    """Identificação de nível ofício + lista de servidores da prestação."""
    oficio = prestacao.oficio
    servidores = [_servidor_identificacao(ps) for ps in prestacao.servidores_prestacao.all()]
    return {
        "numero": oficio.numero_formatado,
        "protocolo": format_protocolo(oficio.protocolo) or "—",
        "data_oficio": oficio.data_criacao.strftime("%d/%m/%Y") if oficio.data_criacao else "—",
        "custeio": oficio.get_custeio_display() if oficio.custeio else "—",
        "destino": _destino_display(oficio) or "—",
        "periodo": _periodo_display(oficio) or "—",
        "servidores": servidores,
        "servidores_count": len(servidores),
    }


def _marcar_prestacao_em_preenchimento(prestacao):
    if prestacao.status == PrestacaoContas.STATUS_PENDENTE:
        prestacao.status = PrestacaoContas.STATUS_EM_PREENCHIMENTO
        prestacao.save(update_fields=["status", "atualizado_em"])


def _anexos_rows(prestacao, anexos_qs):
    rows = []
    for anexo in anexos_qs.order_by("criado_em", "pk"):
        rows.append(
            {
                "id": anexo.pk,
                "nome": anexo.nome_original or Path(anexo.arquivo.name).name,
                "url": anexo.arquivo.url,
                "delete_url": reverse(
                    "prestacoes_contas:prestacao_documento_excluir",
                    args=[prestacao.pk, anexo.pk],
                ),
            },
        )
    return rows


def _anexos_resumo(anexos_qs):
    anexos = list(anexos_qs)
    if not anexos:
        return {"status": False, "value": "Pendente"}
    if len(anexos) == 1:
        nome = anexos[0].nome_original or Path(anexos[0].arquivo.name).name
        return {"status": True, "value": nome}
    return {"status": True, "value": f"{len(anexos)} arquivos anexados"}


def _build_prestacao_steps(prestacao, atual: str) -> list:
    """Etapas do wizard da prestação de contas."""
    documentos_url = reverse("prestacoes_contas:documentos", args=[prestacao.pk])
    rt_url = reverse("prestacoes_contas:rt_criar", args=[prestacao.pk])
    diario_url = reverse("prestacoes_contas:diario_criar", args=[prestacao.pk])
    consolidado_url = reverse("prestacoes_contas:consolidado", args=[prestacao.pk])
    etapas = [
        ("rt", "Etapa 1", "Relatório Técnico", rt_url),
        ("diario", "Etapa 2", "Diário de Bordo", diario_url),
        ("documentos", "Etapa 3", "Documentos", documentos_url),
        ("consolidado", "Etapa 4", "PDF Final", consolidado_url),
    ]
    steps = []
    atingiu_atual = False
    for chave, step_label, titulo, url in etapas:
        if chave == atual:
            state_class = "is-current"
            aria_current = "step"
            atingiu_atual = True
            status = "Em edição"
        elif atingiu_atual:
            state_class = ""
            aria_current = ""
            status = "A seguir"
        else:
            state_class = "is-complete"
            aria_current = ""
            status = "Concluído"
        steps.append(
            {
                "marker": "✓" if state_class == "is-complete" else str(len(steps) + 1),
                "step_label": step_label,
                "title": titulo,
                "status": status,
                "state_class": state_class,
                "aria_current": aria_current,
                "url": url,
            }
        )
    return steps


def _autosave_version(obj, field_name="atualizado_em") -> int:
    obj.refresh_from_db()
    value = getattr(obj, field_name, None)
    if value is None:
        return 0
    return int(timezone.localtime(value).timestamp())


def _autosave_form_errors(form):
    return {
        field: [str(item) for item in messages_list]
        for field, messages_list in form.errors.items()
    }


def _solicitacao_autosave_value(payload):
    for name, value in payload.fields.items():
        clean_name = str(name or "").strip()
        if clean_name == "numero_solicitacao" or clean_name.endswith("-numero_solicitacao"):
            return normalize_spaces(value or "")
    return None


def _salvar_rt_autosave(relatorio, clean_fields):
    if not clean_fields:
        return
    update_fields = set()
    for campo, value in clean_fields.items():
        if campo.endswith("_outro"):
            base = campo.removesuffix("_outro")
            if base in {item[0] for item in CAMPOS_CUSTEIO_COM_OUTRO}:
                text = normalize_spaces(value or "")
                if text:
                    setattr(relatorio, base, text)
                    update_fields.add(base)
            continue
        if campo in {item[0] for item in CAMPOS_CUSTEIO_COM_OUTRO}:
            text = normalize_spaces(value or "")
            if text == OUTRO_VALUE:
                continue
            if text in get_custeio_valores_fixos(campo):
                setattr(relatorio, campo, text)
                update_fields.add(campo)
            continue
        setattr(relatorio, campo, normalize_spaces(value or ""))
        update_fields.add(campo)
    if update_fields:
        relatorio.save(update_fields=[*update_fields, "atualizado_em"])


def _parse_km_autosave(value):
    digitos = re.sub(r"\D", "", str(value or ""))
    return int(digitos) if digitos else None


def _salvar_diario_autosave(diario, payload):
    linhas = list(
        diario.trechos.select_related("trecho").order_by("ordem", "pk")
    )
    changed = False
    for dirty_name in payload.dirty_fields:
        match = re.match(r"^form-(\d+)-(km_inicial|km_final|abastecimento)$", str(dirty_name or ""))
        if not match:
            continue
        index = int(match.group(1))
        field = match.group(2)
        if index >= len(linhas):
            continue
        linha = linhas[index]
        value = payload.fields.get(dirty_name)
        if field in {"km_inicial", "km_final"}:
            setattr(linha, field, _parse_km_autosave(value))
        elif field == "abastecimento":
            linha.abastecimento = str(value or "") != "nao"
        linha.save(update_fields=[field])
        changed = True
    if changed:
        diario.save(update_fields=["atualizado_em"])


def _is_inline_request(request) -> bool:
    """Indica se o PDF deve ser servido embutido (iframe) em vez de baixado."""
    return (request.GET.get("inline") or "").strip() in {"1", "true", "sim"}


def _preview_error_response(exc) -> HttpResponse:
    """Mensagem amigável renderizada dentro do iframe quando a geração falha."""
    html = (
        '<!doctype html><html lang="pt-br"><head><meta charset="utf-8">'
        '<style>body{margin:0;display:flex;align-items:center;justify-content:center;'
        "min-height:100vh;font-family:system-ui,sans-serif;color:#52657a;background:#f8fafd;}"
        ".msg{max-width:32rem;padding:1.5rem;text-align:center;line-height:1.5;}</style>"
        "</head><body><div class=\"msg\">"
        "<strong>Não foi possível gerar a pré-visualização.</strong><br>"
        f"{escape(str(exc))}</div></body></html>"
    )
    return HttpResponse(html, content_type="text/html; charset=utf-8", status=422)


def _trecho_display(linha) -> dict:
    """Dados somente-leitura de um trecho (origem/destino/datas) para o card do diário."""
    from django.utils import timezone as tz

    trecho = linha.trecho

    def cidade(c, e):
        if c is not None:
            return str(getattr(c, "nome", c)).upper()
        if e is not None:
            return str(getattr(e, "sigla", e)).upper()
        return "—"

    def fmt(dt):
        if not dt:
            return {"data": "", "hora": ""}
        local = tz.localtime(dt) if tz.is_aware(dt) else dt
        return {"data": local.strftime("%d/%m/%Y"), "hora": local.strftime("%H:%M")}

    origem = cidade(getattr(trecho, "origem_cidade", None), getattr(trecho, "origem_estado", None)) if trecho else "—"
    destino = cidade(getattr(trecho, "destino_cidade", None), getattr(trecho, "destino_estado", None)) if trecho else "—"
    saida = fmt(getattr(trecho, "saida_dt", None)) if trecho else {"data": "", "hora": ""}
    chegada = fmt(getattr(trecho, "chegada_dt", None)) if trecho else {"data": "", "hora": ""}
    return {
        "ordem": linha.ordem + 1,
        "origem": origem,
        "destino": destino,
        "rota": f"{origem} → {destino}",
        "saida": saida,
        "chegada": chegada,
    }


_ABA_LABELS = [
    (ABA_PENDENTES, "Pendentes"),
    (ABA_FUTURAS, "Que vão acontecer"),
    (ABA_ARQUIVADOS, "Arquivados"),
    (ABA_FINALIZADOS, "Finalizados"),
]

_ABA_EMPTY_MESSAGE = {
    ABA_PENDENTES: "Nenhuma prestação pendente. Viagens que ainda vão acontecer estão na aba “Que vão acontecer”.",
    ABA_FUTURAS: "Nenhuma viagem agendada para os próximos dias.",
    ABA_ARQUIVADOS: "Nenhuma prestação arquivada.",
    ABA_FINALIZADOS: "Nenhuma prestação finalizada ainda.",
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
        _salvar_solicitacoes_em_lote(request)
        messages.success(request, "Números de solicitação salvos.")
        return redirect("prestacoes_contas:index")

    q         = request.GET.get("q",         "").strip()
    status    = request.GET.get("status",    "").strip()
    aba       = normalizar_aba(request.GET.get("aba", ""))
    viagem_de = request.GET.get("viagem_de", "").strip()
    viagem_ate = request.GET.get("viagem_ate", "").strip()
    sort      = request.GET.get("sort",      "").strip()

    prestacoes = listar_prestacoes(
        q=q or None,
        status=status or None,
        aba=aba,
        viagem_de=viagem_de or None,
        viagem_ate=viagem_ate or None,
        sort=sort or None,
    )

    cards = [apresentar_prestacao_card(prestacao) for prestacao in prestacoes]

    has_filters = any([q, status, viagem_de, viagem_ate, sort])

    contagem = contar_por_aba(
        q=q or None,
        status=status or None,
        viagem_de=viagem_de or None,
        viagem_ate=viagem_ate or None,
    )
    abas = _build_abas(request, aba, contagem, q=q, status=status, sort=sort)

    return render(
        request,
        "prestacoes_contas/index.html",
        {
            "page_title": "Prestações de Contas",
            "page_description": "Acompanhamento das prestações de contas por ofício.",
            "cards": cards,
            "q":          q,
            "status":     status,
            "aba":        aba,
            "abas":       abas,
            "viagem_de":  viagem_de,
            "viagem_ate": viagem_ate,
            "sort":       sort,
            "has_filters": has_filters,
            "search_clear_url": f"{reverse('prestacoes_contas:index')}?aba={aba}",
            "status_options": [{"value": "", "label": "Todos os status"}]
            + [{"value": v, "label": l} for v, l in PrestacaoContas.STATUS_CHOICES],
            "empty_message": _ABA_EMPTY_MESSAGE.get(aba, "Nenhuma prestação de contas encontrada."),
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
    """Fallback sem JS: salva os campos ``ps-<pk>-numero_solicitacao`` do card."""
    atualizacoes = {}
    for name, value in request.POST.items():
        match = re.match(r"^ps-(\d+)-numero_solicitacao$", name)
        if match:
            atualizacoes[int(match.group(1))] = normalize_spaces(value or "")
    if not atualizacoes:
        return
    servidores = PrestacaoServidor.objects.filter(pk__in=atualizacoes.keys())
    for ps in servidores:
        novo = atualizacoes.get(ps.pk, "")
        if ps.numero_solicitacao != novo:
            ps.numero_solicitacao = novo
            ps.save(update_fields=["numero_solicitacao", "atualizado_em"])


def _redirect_lista(request, prestacao):
    """Volta para a lista preservando a aba/filtros de onde a ação foi disparada."""
    destino = request.POST.get("next") or reverse("prestacoes_contas:index")
    return redirect(destino)


@require_POST
def prestacao_arquivar(request, pc_pk):
    """Arquiva ou desarquiva a prestação (alterna conforme o estado atual)."""
    prestacao = get_object_or_404(PrestacaoContas, pk=pc_pk)
    prestacao.definir_arquivada(not prestacao.arquivada)
    if prestacao.arquivada:
        messages.success(request, "Prestação arquivada.")
    else:
        messages.success(request, "Prestação desarquivada.")
    return _redirect_lista(request, prestacao)


@require_POST
def prestacao_finalizar(request, pc_pk):
    """Conclui ou reabre a prestação (alterna conforme o estado atual)."""
    prestacao = get_object_or_404(PrestacaoContas, pk=pc_pk)
    prestacao.definir_finalizada(not prestacao.finalizada)
    if prestacao.finalizada:
        messages.success(request, "Prestação finalizada.")
    else:
        messages.success(request, "Prestação reaberta.")
    return _redirect_lista(request, prestacao)


@require_POST
def prestacao_servidor_solicitacao_autosave(request, ps_pk):
    ps = get_object_or_404(PrestacaoServidor, pk=ps_pk)
    try:
        payload = parse_autosave_payload(request, expected_model="prestacao_servidor")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    valor = _solicitacao_autosave_value(payload)
    if valor is not None and ps.numero_solicitacao != valor:
        ps.numero_solicitacao = valor
        ps.save(update_fields=["numero_solicitacao", "atualizado_em"])
        _marcar_prestacao_em_preenchimento(ps.prestacao)
    return autosave_json_response(
        ok=True,
        object_id=ps.pk,
        version=_autosave_version(ps),
    )


def _prestacao_full(pc_pk):
    return get_object_or_404(
        PrestacaoContas.objects.select_related("oficio__roteiro").prefetch_related(
            "servidores_prestacao__servidor__cargo",
            "servidores_prestacao__servidor__unidade",
            "servidores_prestacao__documentos_anexos",
            "documentos_anexos",
        ),
        pk=pc_pk,
    )


def documentos(request, pc_pk):
    """Etapa 3: despacho (compartilhado) + arquivos assinados por servidor.

    Cada servidor anexa o comprovante de saque/transferência e o relatório técnico
    assinado; o motorista anexa também o diário de bordo assinado. Cada seção
    autosalva de forma independente (número via autosave.js, arquivos via
    prestacoes-contas-documentos.js), por isso a página é apenas de leitura/edição
    contínua — a navegação entre etapas é por links.
    """
    prestacao = _prestacao_full(pc_pk)
    servidores = list(prestacao.servidores_prestacao.all())

    despacho_form = PrestacaoDespachoForm(instance=prestacao)

    servidores_ctx = []
    for ps in servidores:
        form = PrestacaoServidorDocumentosForm(instance=ps, prefix=f"ps-{ps.pk}")
        comprovantes = ps.documentos_anexos.filter(tipo=PrestacaoDocumentoAnexo.TIPO_COMPROVANTE)
        rt_assinados = ps.documentos_anexos.filter(tipo=PrestacaoDocumentoAnexo.TIPO_RT_ASSINADO)
        diario_assinados = ps.documentos_anexos.filter(tipo=PrestacaoDocumentoAnexo.TIPO_DB_ASSINADO)
        servidores_ctx.append(
            {
                "ps": ps,
                "identificacao": _servidor_identificacao(ps),
                "form": form,
                "comprovante_anexos": _anexos_rows(prestacao, comprovantes),
                "rt_assinado_anexos": _anexos_rows(prestacao, rt_assinados),
                "diario_assinado_anexos": _anexos_rows(prestacao, diario_assinados),
                "arquivo_autosave_url": reverse(
                    "prestacoes_contas:prestacao_servidor_arquivo_autosave", args=[ps.pk]
                ),
                "solicitacao_autosave_url": reverse(
                    "prestacoes_contas:prestacao_servidor_solicitacao_autosave", args=[ps.pk]
                ),
            }
        )

    despacho_anexos = prestacao.documentos_anexos.filter(tipo=PrestacaoDocumentoAnexo.TIPO_DESPACHO)

    return render(
        request,
        "prestacoes_contas/documentos_form.html",
        {
            "page_title": "Documentos da Prestação",
            "despacho_form": despacho_form,
            "prestacao": prestacao,
            "servidores": servidores_ctx,
            "identificacao": _build_identificacao(prestacao),
            "wizard_page_steps": _build_prestacao_steps(prestacao, "documentos"),
            "diario_url": reverse("prestacoes_contas:diario_criar", args=[prestacao.pk]),
            "consolidado_url": reverse("prestacoes_contas:consolidado", args=[prestacao.pk]),
            "despacho_autosave_url": reverse(
                "prestacoes_contas:prestacao_arquivo_autosave", args=[prestacao.pk]
            ),
            "despacho_anexos": _anexos_rows(prestacao, despacho_anexos),
        },
    )


@require_POST
def prestacao_arquivo_autosave(request, pc_pk):
    """Autosave do despacho (compartilhado)."""
    prestacao = get_object_or_404(PrestacaoContas, pk=pc_pk)
    form = PrestacaoDespachoForm(request.POST, request.FILES, instance=prestacao)
    if not form.is_valid():
        return autosave_json_response(
            ok=False,
            message="Alguns anexos ainda precisam de ajuste antes do autosave.",
            errors=_autosave_form_errors(form),
        )
    form.save()
    _marcar_prestacao_em_preenchimento(prestacao)
    return autosave_json_response(
        ok=True,
        object_id=prestacao.pk,
        version=_autosave_version(prestacao),
    )


@require_POST
def prestacao_servidor_arquivo_autosave(request, ps_pk):
    """Autosave do comprovante de saque (individual do servidor).

    Salva apenas os anexos — não reescreve o ``numero_solicitacao`` (que tem seu
    próprio autosave), evitando apagá-lo quando o POST traz só o arquivo.
    """
    ps = get_object_or_404(PrestacaoServidor.objects.select_related("prestacao"), pk=ps_pk)
    form = PrestacaoServidorDocumentosForm(request.POST, request.FILES, instance=ps, prefix=f"ps-{ps.pk}")
    if not form.is_valid():
        return autosave_json_response(
            ok=False,
            message="Alguns anexos ainda precisam de ajuste antes do autosave.",
            errors=_autosave_form_errors(form),
        )
    form.save_anexos(ps)
    _marcar_prestacao_em_preenchimento(ps.prestacao)
    return autosave_json_response(
        ok=True,
        object_id=ps.pk,
        version=_autosave_version(ps),
    )


@require_POST
def prestacao_documento_excluir(request, pc_pk, anexo_pk):
    prestacao = get_object_or_404(PrestacaoContas, pk=pc_pk)
    anexo = get_object_or_404(
        PrestacaoDocumentoAnexo,
        pk=anexo_pk,
        prestacao=prestacao,
    )
    if anexo.arquivo:
        anexo.arquivo.delete(save=False)
    anexo.delete()
    _marcar_prestacao_em_preenchimento(prestacao)
    return autosave_json_response(
        ok=True,
        object_id=prestacao.pk,
        version=_autosave_version(prestacao),
    )


# ─────────────────────────────────────────────────────────────────
# Assinatura eletrônica (RT por servidor e Diário de Bordo por ofício)
# ─────────────────────────────────────────────────────────────────

def _whatsapp_data(link_absoluto, signer, doc_labels) -> dict:
    """Telefone (com DDI) e mensagem; o front monta a URL por app/aparelho no clique."""
    docs_txt = " e ".join(doc_labels)
    msg = (
        "Olá! Para concluir a prestação de contas, preciso da sua assinatura no "
        f"{docs_txt}. Acesse o link, confirme sua identidade e assine: {link_absoluto}"
    )
    telefone = (getattr(signer, "telefone", "") or "").strip() if signer else ""
    fone = f"55{telefone}" if (len(telefone) == 11 and telefone.isdigit()) else ""
    return {"phone": fone, "msg": msg}


def _assinatura_card(request, *, doc, signer, tipo, label, motivo_sem_signer, gerar_url, cancelar_url) -> dict:
    cpf_ok = bool(signer and len((getattr(signer, "cpf", "") or "").strip()) == 11)
    motivo = ""
    if signer is None:
        motivo = motivo_sem_signer
    elif not cpf_ok:
        quem = "motorista" if tipo == AssinaturaDocumento.TIPO_DB else "servidor"
        motivo = f"Cadastre o CPF do {quem} ({signer}) para gerar o link de assinatura."

    assinada = bool(doc and doc.status == AssinaturaDocumento.STATUS_ASSINADA)
    link_ativo = bool(doc and doc.link_ativo)
    link_abs = ""
    wa = {"phone": "", "msg": ""}
    if link_ativo:
        link_abs = request.build_absolute_uri(
            reverse("prestacoes_contas:assinatura_landing", args=[doc.link_token])
        )
        wa = _whatsapp_data(link_abs, signer, [label])

    return {
        "tipo": tipo,
        "label": label,
        "signatario": str(signer) if signer else "—",
        "assinada": assinada,
        "assinado_em": doc.assinado_em if assinada else None,
        "codigo": doc.codigo_verificacao if assinada else "",
        "pode_assinar": cpf_ok,
        "motivo": motivo,
        "link_ativo": link_ativo,
        "link_absoluto": link_abs,
        "expira_em": doc.link_expira_em if link_ativo else None,
        "whatsapp_phone": wa["phone"],
        "whatsapp_msg": wa["msg"],
        "gerar_url": gerar_url,
        "cancelar_url": cancelar_url,
    }


def _assinatura_rt_card(request, ps) -> dict:
    return _assinatura_card(
        request,
        doc=assinatura_rt(ps),
        signer=signer_rt(ps),
        tipo=AssinaturaDocumento.TIPO_RT,
        label=f"Relatório Técnico — {ps.servidor.nome}",
        motivo_sem_signer="Servidor da prestação não definido.",
        gerar_url=reverse("prestacoes_contas:assinatura_rt_gerar", args=[ps.pk]),
        cancelar_url=reverse("prestacoes_contas:assinatura_rt_cancelar", args=[ps.pk]),
    )


def _assinatura_db_card(request, prestacao) -> dict:
    return _assinatura_card(
        request,
        doc=assinatura_db(prestacao),
        signer=signer_db(prestacao),
        tipo=AssinaturaDocumento.TIPO_DB,
        label="Diário de Bordo",
        motivo_sem_signer="Defina o motorista do ofício para gerar o link.",
        gerar_url=reverse("prestacoes_contas:assinatura_db_gerar", args=[prestacao.pk]),
        cancelar_url=reverse("prestacoes_contas:assinatura_db_cancelar", args=[prestacao.pk]),
    )


@require_POST
def assinatura_rt_gerar(request, ps_pk):
    ps = get_object_or_404(
        PrestacaoServidor.objects.select_related("prestacao__oficio", "servidor"), pk=ps_pk
    )
    forcar = request.POST.get("forcar") == "1"
    next_url = request.POST.get("next") or reverse(
        "prestacoes_contas:consolidado", args=[ps.prestacao_id]
    )
    try:
        token, _docs = emitir_link_rt(ps, forcar=forcar)
    except (AssinaturaError, DocumentValidationError) as exc:
        messages.error(request, str(exc))
        return redirect(next_url)
    link = request.build_absolute_uri(
        reverse("prestacoes_contas:assinatura_landing", args=[token])
    )
    messages.success(request, f"Link de assinatura gerado. Envie ao signatário: {link}")
    return redirect(next_url)


@require_POST
def assinatura_db_gerar(request, pc_pk):
    prestacao = get_object_or_404(
        PrestacaoContas.objects.select_related("oficio__motorista"), pk=pc_pk
    )
    forcar = request.POST.get("forcar") == "1"
    next_url = request.POST.get("next") or reverse(
        "prestacoes_contas:consolidado", args=[prestacao.pk]
    )
    try:
        token, _docs = emitir_link_db(prestacao, forcar=forcar)
    except (AssinaturaError, DocumentValidationError) as exc:
        messages.error(request, str(exc))
        return redirect(next_url)
    link = request.build_absolute_uri(
        reverse("prestacoes_contas:assinatura_landing", args=[token])
    )
    messages.success(request, f"Link de assinatura gerado. Envie ao signatário: {link}")
    return redirect(next_url)


@require_POST
def assinatura_rt_cancelar(request, ps_pk):
    ps = get_object_or_404(PrestacaoServidor, pk=ps_pk)
    next_url = request.POST.get("next") or reverse(
        "prestacoes_contas:consolidado", args=[ps.prestacao_id]
    )
    cancelar_assinatura_rt(ps)
    messages.success(request, "Link/assinatura removidos. Você pode gerar um novo link.")
    return redirect(next_url)


@require_POST
def assinatura_db_cancelar(request, pc_pk):
    prestacao = get_object_or_404(PrestacaoContas, pk=pc_pk)
    next_url = request.POST.get("next") or reverse(
        "prestacoes_contas:consolidado", args=[prestacao.pk]
    )
    cancelar_assinatura_db(prestacao)
    messages.success(request, "Link/assinatura removidos. Você pode gerar um novo link.")
    return redirect(next_url)


def rt_criar(request, pc_pk):
    """Edição do texto compartilhado do RT; a geração/preview é por servidor."""
    prestacao = _prestacao_full(pc_pk)

    relatorio, _ = RelatorioTecnico.objects.get_or_create(prestacao=prestacao)
    garantir_campos_padrao_relatorio_tecnico(relatorio)
    identificacao = _build_identificacao(prestacao)
    servidores = list(prestacao.servidores_prestacao.all())

    if request.method == "POST":
        form = RelatorioTecnicoForm(request.POST, instance=relatorio, relatorio=relatorio)
        if form.is_valid():
            form.save()
            _marcar_prestacao_em_preenchimento(prestacao)
            messages.success(request, "Texto do relatório técnico salvo.")
            return redirect("prestacoes_contas:rt_criar", pc_pk=prestacao.pk)
    else:
        initial = {}
        if not relatorio.diaria:
            initial["diaria"] = diaria_inicial_da_prestacao(prestacao)
        if not relatorio.motivo:
            initial["motivo"] = prestacao.oficio.motivo or ""
        form = RelatorioTecnicoForm(instance=relatorio, relatorio=relatorio, initial=initial)

    servidores_ctx = [
        {
            "ps_pk": ps.pk,
            "nome": ps.servidor.nome,
            "is_motorista": ps.is_motorista,
            "download_pdf_url": reverse(
                "prestacoes_contas:rt_download_servidor_formato", args=[ps.pk, "pdf"]
            ),
            "download_docx_url": reverse(
                "prestacoes_contas:rt_download_servidor_formato", args=[ps.pk, "docx"]
            ),
            "preview_inline_url": reverse(
                "prestacoes_contas:rt_download_servidor_formato", args=[ps.pk, "pdf"]
            ) + "?inline=1",
        }
        for ps in servidores
    ]

    return render(
        request,
        "prestacoes_contas/relatorio_tecnico_form.html",
        {
            "page_title": "Relatório Técnico",
            "form": form,
            "campos_modelo": _build_campos_modelo(form),
            "campos_custeio": _build_campos_custeio(form),
            "relatorio": relatorio,
            "prestacao": prestacao,
            "identificacao": identificacao,
            "servidores": servidores_ctx,
            "wizard_page_steps": _build_prestacao_steps(prestacao, "rt"),
            "diaria_info": diaria_info(prestacao),
            "documentos_url": reverse("prestacoes_contas:documentos", args=[prestacao.pk]),
            "diario_url": reverse("prestacoes_contas:diario_criar", args=[prestacao.pk]),
            "autosave_url": reverse("prestacoes_contas:rt_autosave", args=[relatorio.pk]),
            "preview_inline_url": servidores_ctx[0]["preview_inline_url"] if servidores_ctx else "",
        },
    )


@require_POST
def rt_autosave(request, pk):
    relatorio = get_object_or_404(RelatorioTecnico, pk=pk)
    try:
        payload = parse_autosave_payload(request, expected_model="relatorio_tecnico")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    allowed_fields = {
        "diaria",
        "translado",
        "combustivel",
        "passagem",
        "translado_outro",
        "combustivel_outro",
        "passagem_outro",
        "motivo",
        "atividade",
        "conclusao",
        "medidas",
        "info_complementares",
    }
    clean_fields = filter_allowed_fields(payload.fields, payload.dirty_fields, allowed_fields)
    _salvar_rt_autosave(relatorio, clean_fields)
    if clean_fields and relatorio.prestacao.status == PrestacaoContas.STATUS_PENDENTE:
        relatorio.prestacao.status = PrestacaoContas.STATUS_EM_PREENCHIMENTO
        relatorio.prestacao.save(update_fields=["status", "atualizado_em"])
    return autosave_json_response(
        ok=True,
        object_id=relatorio.pk,
        version=_autosave_version(relatorio),
    )


def rt_download_servidor(request, ps_pk, formato="docx"):
    ps = get_object_or_404(
        PrestacaoServidor.objects.select_related(
            "prestacao__oficio__roteiro", "servidor"
        ),
        pk=ps_pk,
    )
    relatorio, _ = RelatorioTecnico.objects.get_or_create(prestacao=ps.prestacao)
    garantir_campos_padrao_relatorio_tecnico(relatorio)

    inline = _is_inline_request(request)
    formato = (formato or "docx").strip().lower()
    if formato == "pdf":
        try:
            from .assinatura_services import pdf_rt_assinado_ou_gerado
            conteudo = pdf_rt_assinado_ou_gerado(ps)
        except DocumentValidationError as exc:
            if inline:
                return _preview_error_response(exc)
            messages.error(request, str(exc))
            return redirect("prestacoes_contas:rt_criar", pc_pk=ps.prestacao_id)
        content_type = "application/pdf"
    else:
        conteudo = gerar_relatorio_tecnico_docx(relatorio, ps.servidor)
        formato = "docx"
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    nome = nome_arquivo_rt(relatorio, ps.servidor, formato=formato)
    disposition = "inline" if inline and formato == "pdf" else "attachment"
    response = HttpResponse(conteudo, content_type=content_type)
    response["Content-Disposition"] = f'{disposition}; filename="{nome}"'
    if disposition == "inline":
        response["X-Frame-Options"] = "SAMEORIGIN"
    return response


def diario_criar(request, pc_pk):
    """Etapa 2 do wizard: diário de bordo do veículo a partir do roteiro do ofício."""
    prestacao = get_object_or_404(
        PrestacaoContas.objects.select_related(
            "oficio__roteiro",
            "oficio__viatura",
            "oficio__motorista",
        ).prefetch_related(
            "servidores_prestacao__servidor__cargo",
            "servidores_prestacao__servidor__unidade",
        ),
        pk=pc_pk,
    )

    diario, _ = DiarioBordo.objects.get_or_create(prestacao=prestacao)
    sincronizar_trechos(diario)
    queryset = diario.trechos.select_related(
        "trecho__origem_cidade",
        "trecho__origem_estado",
        "trecho__destino_cidade",
        "trecho__destino_estado",
    ).order_by("ordem", "pk")

    if request.method == "POST":
        formset = DiarioBordoTrechoFormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            formset.save()
            _marcar_prestacao_em_preenchimento(prestacao)
            formato = "pdf" if request.POST.get("action") == "download_pdf" else "xlsx"
            return redirect("prestacoes_contas:diario_download_formato", pk=diario.pk, formato=formato)
    else:
        formset = DiarioBordoTrechoFormSet(queryset=queryset)

    linhas = list(queryset)
    trechos = [
        {"form": form, "display": _trecho_display(linha)}
        for form, linha in zip(formset.forms, linhas)
    ]

    return render(
        request,
        "prestacoes_contas/diario_bordo_form.html",
        {
            "page_title": "Diário de Bordo",
            "prestacao": prestacao,
            "diario": diario,
            "formset": formset,
            "trechos": trechos,
            "identificacao": _build_identificacao(prestacao),
            "wizard_page_steps": _build_prestacao_steps(prestacao, "diario"),
            "diaria_info": diaria_info(prestacao),
            "assinatura": _assinatura_db_card(request, prestacao),
            "assinatura_next_url": reverse("prestacoes_contas:diario_criar", args=[prestacao.pk]),
            "editar_roteiro_url": reverse("prestacoes_contas:diario_editar_roteiro", args=[prestacao.pk]),
            "editar_motorista_url": reverse("prestacoes_contas:diario_motorista", args=[prestacao.pk]),
            "motorista_resumo": _motorista_resumo(diario),
            "rt_url": reverse("prestacoes_contas:rt_criar", args=[prestacao.pk]),
            "documentos_url": reverse("prestacoes_contas:documentos", args=[prestacao.pk]),
            "autosave_url": reverse("prestacoes_contas:diario_autosave", args=[diario.pk]),
            "preview_inline_url": reverse("prestacoes_contas:diario_download_formato", args=[diario.pk, "pdf"]) + "?inline=1",
            "preview_pdf_url": reverse("prestacoes_contas:diario_download_formato", args=[diario.pk, "pdf"]),
            "preview_xlsx_url": reverse("prestacoes_contas:diario_download_formato", args=[diario.pk, "xlsx"]),
        },
    )


@require_POST
def diario_autosave(request, pk):
    diario = get_object_or_404(DiarioBordo.objects.select_related("prestacao"), pk=pk)
    sincronizar_trechos(diario)
    try:
        payload = parse_autosave_payload(request, expected_model="diario_bordo")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    _salvar_diario_autosave(diario, payload)
    if payload.dirty_fields and diario.prestacao.status == PrestacaoContas.STATUS_PENDENTE:
        diario.prestacao.status = PrestacaoContas.STATUS_EM_PREENCHIMENTO
        diario.prestacao.save(update_fields=["status", "atualizado_em"])
    return autosave_json_response(
        ok=True,
        object_id=diario.pk,
        version=_autosave_version(diario),
    )


def diario_editar_roteiro(request, pc_pk):
    """Abre o editor de roteiro sobre a cópia da prestação (clona do ofício na 1ª vez)."""
    from urllib.parse import urlencode

    prestacao = get_object_or_404(
        PrestacaoContas.objects.select_related("oficio__roteiro"),
        pk=pc_pk,
    )
    copia = garantir_roteiro_ajustado(prestacao)
    diario_url = reverse("prestacoes_contas:diario_criar", args=[prestacao.pk])
    if copia is None:
        messages.error(request, "Este ofício não possui roteiro para editar.")
        return redirect(diario_url)
    editar_url = reverse("roteiros:editar", args=[copia.pk])
    return redirect(f"{editar_url}?{urlencode({'next': diario_url})}")


_MOTORISTA_ORIGEM_LABEL = {
    DiarioBordo.MOTORISTA_MODO_OFICIO: "Motorista do ofício",
    DiarioBordo.MOTORISTA_MODO_SERVIDOR: "Outro servidor deste ofício",
    DiarioBordo.MOTORISTA_MODO_OUTRO: "Motorista de outro ofício",
}


def _motorista_resumo(diario) -> dict:
    """Motorista efetivo do diário (considerando a troca) para exibir na Etapa 3."""
    nome, cpf = motorista_diario(diario)
    return {
        "nome": nome or "—",
        "cpf": cpf or "",
        "origem": _MOTORISTA_ORIGEM_LABEL.get(diario.motorista_modo, "Motorista do ofício"),
        "alterado": diario.motorista_alterado,
    }


def _sincronizar_info_complementares_rt(prestacao):
    """Após trocar motorista/viatura, gera a prévia em Informações complementares do
    RT — apenas quando o campo ainda está vazio (não sobrescreve texto do usuário)."""
    from .services import descricao_ajustes_prestacao

    relatorio = RelatorioTecnico.objects.filter(prestacao=prestacao).first()
    if relatorio is None or normalize_spaces(relatorio.info_complementares or ""):
        return
    texto = descricao_ajustes_prestacao(prestacao)
    if texto:
        relatorio.info_complementares = texto
        relatorio.save(update_fields=["info_complementares", "atualizado_em"])


def _oficio_prefill_dados(oficio) -> dict:
    """Dados de um ofício para auto-preencher o formulário de troca (motorista + viatura)."""
    from .diario_services import _viatura_dados  # uso interno no mesmo app

    nome, cpf = motorista_do_oficio(oficio)
    numero = str(oficio.numero or "").strip()
    ano = str(oficio.ano or "").strip()
    numero_ano = f"{numero}/{ano}" if numero and ano else numero

    viatura = {"modo": "", "id": "", "modelo": "", "placa": "", "tipo": "", "combustivel": ""}
    if oficio.viatura_id:
        v = oficio.viatura
        viatura = {
            "modo": DiarioBordo.VIATURA_MODO_BANCO,
            "id": str(oficio.viatura_id),
            "modelo": v.modelo or "",
            "placa": v.placa or "",
            "tipo": v.tipo or "",
            "combustivel": str(v.combustivel) if v.combustivel_id else "",
        }
    elif (oficio.transporte_modelo_manual or oficio.transporte_placa_manual or oficio.transporte_tipo_manual):
        viatura = {
            "modo": DiarioBordo.VIATURA_MODO_MANUAL,
            "id": "",
            "modelo": oficio.transporte_modelo_manual or "",
            "placa": oficio.transporte_placa_manual or "",
            "tipo": oficio.transporte_tipo_manual or "",
            "combustivel": str(oficio.transporte_combustivel_manual) if oficio.transporte_combustivel_manual_id else "",
        }

    label = numero_ano or f"Ofício {oficio.pk}"
    if nome:
        label = f"{label} — {nome}"
    return {
        "id": oficio.pk,
        "label": label,
        "numero_ano": numero_ano,
        "protocolo": format_protocolo(oficio.protocolo) or "",
        "motorista_nome": nome or "",
        "motorista_cpf": format_cpf(cpf) or cpf or "",
        "viatura": viatura,
    }


def diario_motorista(request, pc_pk):
    """Etapa 2 — troca o motorista/viatura apenas deste diário, sem alterar o ofício."""
    prestacao = get_object_or_404(
        PrestacaoContas.objects.select_related("oficio", "oficio__viatura").prefetch_related(
            "oficio__servidores__cargo",
            "oficio__servidores__unidade",
        ),
        pk=pc_pk,
    )
    diario, _ = DiarioBordo.objects.get_or_create(prestacao=prestacao)
    diario_url = reverse("prestacoes_contas:diario_criar", args=[prestacao.pk])

    if request.method == "POST":
        form = DiarioMotoristaForm(request.POST, instance=diario, oficio=prestacao.oficio)
        if form.is_valid():
            form.save()
            _sincronizar_info_complementares_rt(prestacao)
            _marcar_prestacao_em_preenchimento(prestacao)
            messages.success(request, "Diário de bordo atualizado (motorista/viatura).")
            return redirect(diario_url)
    else:
        form = DiarioMotoristaForm(instance=diario, oficio=prestacao.oficio)

    oficio_nome, oficio_cpf = motorista_do_oficio(prestacao.oficio)

    # Ofícios existentes (com número) para o select de "motorista de outro ofício".
    oficios = (
        Oficio.objects.select_related("viatura", "viatura__combustivel", "motorista", "transporte_combustivel_manual")
        .exclude(pk=prestacao.oficio_id)
        .filter(numero__isnull=False)
        .order_by("-ano", "-numero")[:200]
    )
    oficios_prefill = [_oficio_prefill_dados(o) for o in oficios]

    return render(
        request,
        "prestacoes_contas/diario_motorista_form.html",
        {
            "page_title": "Trocar motorista / viatura",
            "prestacao": prestacao,
            "diario": diario,
            "form": form,
            "identificacao": _build_identificacao(prestacao),
            "wizard_page_steps": _build_prestacao_steps(prestacao, "diario"),
            "motorista_oficio_nome": oficio_nome or "—",
            "motorista_oficio_cpf": oficio_cpf,
            "viatura_oficio": viatura_resumo_oficio(prestacao.oficio),
            "oficios_prefill": oficios_prefill,
            "oficios_prefill_json": json.dumps(oficios_prefill),
            "diario_url": diario_url,
        },
    )


def diario_download(request, pk, formato="xlsx"):
    diario = get_object_or_404(
        DiarioBordo.objects.select_related(
            "prestacao__oficio__roteiro",
            "prestacao__oficio__viatura",
            "prestacao__oficio__motorista",
        ),
        pk=pk,
    )

    inline = _is_inline_request(request)
    formato = (formato or "xlsx").strip().lower()
    if formato == "pdf":
        try:
            from .assinatura_services import pdf_db_assinado_ou_gerado
            conteudo = pdf_db_assinado_ou_gerado(diario.prestacao)
        except DocumentValidationError as exc:
            if inline:
                return _preview_error_response(exc)
            messages.error(request, str(exc))
            return redirect("prestacoes_contas:diario_criar", pc_pk=diario.prestacao_id)
        content_type = "application/pdf"
    else:
        conteudo = gerar_diario_bordo_xlsx(diario)
        formato = "xlsx"
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    nome = nome_arquivo_diario(diario, formato=formato)
    disposition = "inline" if inline and formato == "pdf" else "attachment"
    response = HttpResponse(conteudo, content_type=content_type)
    response["Content-Disposition"] = f'{disposition}; filename="{nome}"'
    if disposition == "inline":
        response["X-Frame-Options"] = "SAMEORIGIN"
    return response


def consolidado(request, pc_pk):
    prestacao = _prestacao_full(pc_pk)

    try:
        prestacao.relatorio_tecnico
        relatorio_ok = True
    except RelatorioTecnico.DoesNotExist:
        relatorio_ok = False
    diario_ok = DiarioBordo.objects.filter(prestacao=prestacao).exists()
    despacho_resumo = _anexos_resumo(
        prestacao.documentos_anexos.filter(tipo=PrestacaoDocumentoAnexo.TIPO_DESPACHO)
    )

    itens = [
        {
            "label": "Despacho assinado do ofício",
            "status": despacho_resumo["status"],
            "value": despacho_resumo["value"],
        },
        {
            "label": "Relatório Técnico",
            "status": relatorio_ok,
            "value": "Criado" if relatorio_ok else "Será criado com os dados atuais",
        },
        {
            "label": "Diário de Bordo",
            "status": diario_ok,
            "value": "Criado" if diario_ok else "Será criado com os dados atuais",
        },
    ]

    servidores_ctx = []
    for ps in prestacao.servidores_prestacao.all():
        comprovante_resumo = _anexos_resumo(
            ps.documentos_anexos.filter(tipo=PrestacaoDocumentoAnexo.TIPO_COMPROVANTE)
        )
        rt_assinado_resumo = _anexos_resumo(
            ps.documentos_anexos.filter(tipo=PrestacaoDocumentoAnexo.TIPO_RT_ASSINADO)
        )
        diario_assinado_resumo = _anexos_resumo(
            ps.documentos_anexos.filter(tipo=PrestacaoDocumentoAnexo.TIPO_DB_ASSINADO)
        )
        servidores_ctx.append(
            {
                "ps_pk": ps.pk,
                "nome": ps.servidor.nome,
                "is_motorista": ps.is_motorista,
                "numero_solicitacao": ps.numero_solicitacao,
                "numero_ok": bool((ps.numero_solicitacao or "").strip()),
                "comprovante_resumo": comprovante_resumo,
                "rt_assinado_resumo": rt_assinado_resumo,
                "diario_assinado_resumo": diario_assinado_resumo,
                "assinatura_rt": _assinatura_rt_card(request, ps),
                "download_url": reverse("prestacoes_contas:consolidado_download", args=[ps.pk]),
                "preview_inline_url": reverse("prestacoes_contas:consolidado_download", args=[ps.pk]) + "?inline=1",
            }
        )

    return render(
        request,
        "prestacoes_contas/consolidado.html",
        {
            "page_title": "PDF Final",
            "prestacao": prestacao,
            "identificacao": _build_identificacao(prestacao),
            "wizard_page_steps": _build_prestacao_steps(prestacao, "consolidado"),
            "itens_consolidado": itens,
            "servidores": servidores_ctx,
            "assinatura_db": _assinatura_db_card(request, prestacao),
            "assinatura_next_url": reverse("prestacoes_contas:consolidado", args=[prestacao.pk]),
            "documentos_url": reverse("prestacoes_contas:documentos", args=[prestacao.pk]),
        },
    )


def consolidado_download(request, ps_pk):
    ps = get_object_or_404(
        PrestacaoServidor.objects.select_related(
            "prestacao__oficio__roteiro", "servidor"
        ).prefetch_related("prestacao__servidores_prestacao"),
        pk=ps_pk,
    )
    inline = _is_inline_request(request)
    try:
        conteudo = gerar_prestacao_consolidado_pdf(ps)
    except DocumentValidationError as exc:
        if inline:
            return _preview_error_response(exc)
        messages.error(request, str(exc))
        return redirect("prestacoes_contas:consolidado", pc_pk=ps.prestacao_id)

    nome = nome_arquivo_prestacao_consolidado(ps)
    disposition = "inline" if inline else "attachment"
    response = HttpResponse(conteudo, content_type="application/pdf")
    response["Content-Disposition"] = f'{disposition}; filename="{nome}"'
    if disposition == "inline":
        response["X-Frame-Options"] = "SAMEORIGIN"
    return response


# ─────────────────────────────────────────────────────────────────
# Gerenciamento de modelos de texto do RT
# ─────────────────────────────────────────────────────────────────

_CAMPO_LABELS = dict(ModeloTextoRelatorioTecnico.CAMPO_CHOICES)


def modelos_index(request):
    q = (request.GET.get("q") or "").strip()
    novo_base = reverse("prestacoes_contas:modelo_novo")

    grupos = []
    for campo, label in ModeloTextoRelatorioTecnico.CAMPO_CHOICES:
        modelos = ModeloTextoRelatorioTecnico.objects.filter(campo=campo)
        if q:
            q_unaccent = remove_accents(q)
            modelos = modelos.filter(Q(nome__unaccent__icontains=q_unaccent) | Q(texto__unaccent__icontains=q_unaccent))

        rows = []
        for modelo in modelos:
            texto = (modelo.texto or "").strip()
            if len(texto) > 90:
                texto = f"{texto[:90]}..."
            rows.append(
                {
                    "title": modelo.nome,
                    "badges": [],
                    "meta": [build_meta("Prévia", texto or "—")],
                    "edit_url": reverse("prestacoes_contas:modelo_editar", args=[modelo.pk]),
                    "delete_url": reverse("prestacoes_contas:modelo_excluir", args=[modelo.pk]),
                }
            )

        grupos.append(
            {
                "campo": campo,
                "label": label,
                "rows": rows,
                "new_url": f"{novo_base}?campo={campo}",
            }
        )

    return render(
        request,
        "prestacoes_contas/modelos_texto/index.html",
        {
            "page_title": "Modelos de texto do RT",
            "page_description": "Textos reutilizáveis para preencher rapidamente os campos do relatório técnico.",
            "q": q,
            "grupos": grupos,
        },
    )


def modelo_novo(request):
    initial = {}
    campo = (request.GET.get("campo") or "").strip()
    if campo in _CAMPO_LABELS:
        initial["campo"] = campo

    form = ModeloTextoRelatorioTecnicoForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Modelo criado com sucesso.")
        return redirect(_voltar_modelos_url(form.cleaned_data["campo"]))

    return render(
        request,
        "prestacoes_contas/modelos_texto/form.html",
        {
            "page_title": "Novo modelo de texto",
            "page_description": "Crie textos reutilizáveis para agilizar o preenchimento do relatório técnico.",
            "form": form,
            "back_url": reverse("prestacoes_contas:modelos_index"),
            "submit_label": "Salvar modelo",
        },
    )


def modelo_editar(request, pk):
    modelo = get_object_or_404(ModeloTextoRelatorioTecnico, pk=pk)
    form = ModeloTextoRelatorioTecnicoForm(request.POST or None, instance=modelo)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Modelo atualizado com sucesso.")
        return redirect(_voltar_modelos_url(form.cleaned_data["campo"]))

    return render(
        request,
        "prestacoes_contas/modelos_texto/form.html",
        {
            "page_title": "Editar modelo de texto",
            "page_description": "Edite o texto reutilizável usado no relatório técnico.",
            "form": form,
            "back_url": _voltar_modelos_url(modelo.campo),
            "submit_label": "Salvar alterações",
        },
    )


def modelo_excluir(request, pk):
    modelo = get_object_or_404(ModeloTextoRelatorioTecnico, pk=pk)
    if request.method == "POST":
        campo = modelo.campo
        modelo.delete()
        messages.success(request, "Modelo excluído com sucesso.")
        return redirect(_voltar_modelos_url(campo))

    return render(
        request,
        "prestacoes_contas/modelos_texto/confirm_delete.html",
        {
            "page_title": "Excluir modelo de texto",
            "page_description": "Confirme a remoção deste modelo.",
            "object": modelo,
            "back_url": _voltar_modelos_url(modelo.campo),
        },
    )


def _voltar_modelos_url(campo) -> str:
    url = reverse("prestacoes_contas:modelos_index")
    if campo in _CAMPO_LABELS:
        return f"{url}?campo={campo}"
    return url
