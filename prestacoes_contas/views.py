from pathlib import Path
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
from core.presenters.meta import build_meta
from core.utils.masks import format_protocolo
from documentos.services.exceptions import DocumentValidationError
from urllib.parse import quote

from .assinatura_services import AssinaturaError
from .assinatura_services import assinaturas_status
from .assinatura_services import cancelar_assinatura
from .assinatura_services import emitir_link
from .assinatura_services import signer_do_documento
from .models import AssinaturaDocumento
from .diario_services import diaria_info
from .diario_services import garantir_roteiro_ajustado
from .diario_services import gerar_diario_bordo_pdf
from .diario_services import gerar_diario_bordo_xlsx
from .diario_services import nome_arquivo_diario
from .diario_services import sincronizar_trechos
from .forms import CAMPOS_COM_MODELO
from .forms import CAMPOS_CUSTEIO_COM_OUTRO
from .forms import DiarioBordoTrechoFormSet
from .forms import ModeloTextoRelatorioTecnicoForm
from .forms import OUTRO_VALUE
from .forms import PrestacaoDocumentosForm
from .forms import PrestacaoSolicitacaoForm
from .forms import RelatorioTecnicoForm
from .forms import get_custeio_valores_fixos
from .models import DiarioBordo
from .models import ModeloTextoRelatorioTecnico
from .models import PrestacaoContas
from .models import PrestacaoDocumentoAnexo
from .models import RelatorioTecnico
from .presenters import apresentar_prestacao_card
from .selectors import listar_prestacoes
from .services import gerar_relatorio_tecnico_docx
from .services import gerar_relatorio_tecnico_pdf
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


def _build_identificacao(pc) -> dict:
    oficio = pc.oficio
    servidor = pc.servidor
    return {
        "numero": oficio.numero_formatado,
        "protocolo": format_protocolo(oficio.protocolo) or "—",
        "data_oficio": oficio.data_criacao.strftime("%d/%m/%Y") if oficio.data_criacao else "—",
        "custeio": oficio.get_custeio_display() if oficio.custeio else "—",
        "destino": _destino_display(oficio) or "—",
        "periodo": _periodo_display(oficio) or "—",
        "nome_servidor": servidor.nome,
        "rg_servidor": servidor.rg_formatado,
        "cargo": str(servidor.cargo) if servidor.cargo_id else "—",
        "unidade": str(servidor.unidade) if servidor.unidade_id else "",
        "is_motorista": oficio.motorista_id == servidor.id,
    }


def _marcar_prestacao_em_preenchimento(prestacao):
    if prestacao.status == PrestacaoContas.STATUS_PENDENTE:
        prestacao.status = PrestacaoContas.STATUS_EM_PREENCHIMENTO
        prestacao.save(update_fields=["status", "atualizado_em"])


def _documento_anexos_rows(prestacao, tipo):
    rows = []
    for anexo in prestacao.documentos_anexos.filter(tipo=tipo).order_by("criado_em", "pk"):
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


def _documento_anexos_resumo(prestacao, tipo):
    anexos = [
        anexo
        for anexo in prestacao.documentos_anexos.all()
        if anexo.tipo == tipo
    ]
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
        ("documentos", "Etapa 1", "Documentos", documentos_url),
        ("rt", "Etapa 2", "Relatório Técnico", rt_url),
        ("diario", "Etapa 3", "Diário de Bordo", diario_url),
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


def _prestacao_autosave_fields(payload):
    fields = {}
    for name, value in payload.fields.items():
        clean_name = str(name or "").strip()
        if clean_name == "numero_solicitacao" or clean_name.endswith("-numero_solicitacao"):
            fields["numero_solicitacao"] = value
    dirty_fields = ["numero_solicitacao"] if fields else []
    return filter_allowed_fields(fields, dirty_fields, {"numero_solicitacao"})


def _salvar_prestacao_autosave(prestacao, clean_fields):
    if "numero_solicitacao" not in clean_fields:
        return
    prestacao.numero_solicitacao = normalize_spaces(clean_fields["numero_solicitacao"] or "")
    prestacao.save(update_fields=["numero_solicitacao", "atualizado_em"])


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


def index(request):
    if request.method == "POST" and request.POST.get("action") == "save_solicitacao":
        prestacao_id = request.POST.get("prestacao_id")
        prestacao = get_object_or_404(PrestacaoContas, pk=prestacao_id)
        prefix = f"prestacao-{prestacao.pk}"
        form = PrestacaoSolicitacaoForm(request.POST, instance=prestacao, prefix=prefix)
        if form.is_valid():
            form.save()
            messages.success(request, "Número da solicitação salvo.")
        else:
            messages.error(request, "Confira o número da solicitação informado.")
        return redirect("prestacoes_contas:index")

    q         = request.GET.get("q",         "").strip()
    status    = request.GET.get("status",    "").strip()
    temporal  = request.GET.get("temporal",  "").strip()
    viagem_de = request.GET.get("viagem_de", "").strip()
    viagem_ate = request.GET.get("viagem_ate", "").strip()
    sort      = request.GET.get("sort",      "").strip()

    prestacoes = listar_prestacoes(
        q=q or None,
        status=status or None,
        temporal=temporal or None,
        viagem_de=viagem_de or None,
        viagem_ate=viagem_ate or None,
        sort=sort or None,
    )

    cards = []
    for prestacao in prestacoes:
        solicitacao_form = PrestacaoSolicitacaoForm(
            instance=prestacao,
            prefix=f"prestacao-{prestacao.pk}",
        )
        cards.append(apresentar_prestacao_card(prestacao, solicitacao_form))

    has_filters = any([q, status, temporal, viagem_de, viagem_ate, sort])

    return render(
        request,
        "prestacoes_contas/index.html",
        {
            "page_title": "Prestações de Contas",
            "page_description": "Acompanhamento das prestações de contas por servidor e ofício.",
            "cards": cards,
            "q":          q,
            "status":     status,
            "temporal":   temporal,
            "viagem_de":  viagem_de,
            "viagem_ate": viagem_ate,
            "sort":       sort,
            "has_filters": has_filters,
            "search_clear_url": reverse("prestacoes_contas:index"),
            "status_options": [{"value": "", "label": "Todos os status"}]
            + [{"value": v, "label": l} for v, l in PrestacaoContas.STATUS_CHOICES],
            "temporal_options": [
                {"value": "",          "label": "Qualquer período"},
                {"value": "futuro",    "label": "Futuras"},
                {"value": "andamento", "label": "Em andamento"},
                {"value": "passado",   "label": "Passadas"},
            ],
            "sort_options": [
                {"value": "criacao_desc",  "label": "Criação: mais recente"},
                {"value": "criacao_asc",   "label": "Criação: mais antiga"},
                {"value": "viagem_asc",    "label": "Viagem: mais próxima"},
                {"value": "viagem_desc",   "label": "Viagem: mais distante"},
                {"value": "servidor_asc",  "label": "Servidor: A–Z"},
                {"value": "servidor_desc", "label": "Servidor: Z–A"},
            ],
            "empty_message": "Nenhuma prestação de contas encontrada com os filtros aplicados.",
        },
    )


def documentos(request, pc_pk):
    prestacao = get_object_or_404(
        PrestacaoContas.objects.select_related(
            "oficio__roteiro",
            "servidor__cargo",
            "servidor__unidade",
        ).prefetch_related("documentos_anexos"),
        pk=pc_pk,
    )

    if request.method == "POST":
        form = PrestacaoDocumentosForm(request.POST, request.FILES, instance=prestacao)
        if form.is_valid():
            form.save()
            _marcar_prestacao_em_preenchimento(prestacao)
            messages.success(request, "Documentos da prestação salvos.")
            if request.POST.get("action") == "save_continue":
                return redirect("prestacoes_contas:rt_criar", pc_pk=prestacao.pk)
            return redirect("prestacoes_contas:documentos", pc_pk=prestacao.pk)
    else:
        form = PrestacaoDocumentosForm(instance=prestacao)

    return render(
        request,
        "prestacoes_contas/documentos_form.html",
        {
            "page_title": "Documentos da Prestação",
            "form": form,
            "prestacao": prestacao,
            "identificacao": _build_identificacao(prestacao),
            "wizard_page_steps": _build_prestacao_steps(prestacao, "documentos"),
            "rt_url": reverse("prestacoes_contas:rt_criar", args=[prestacao.pk]),
            "autosave_url": reverse("prestacoes_contas:prestacao_autosave", args=[prestacao.pk]),
            "arquivo_autosave_url": reverse("prestacoes_contas:prestacao_arquivo_autosave", args=[prestacao.pk]),
            "despacho_anexos": _documento_anexos_rows(prestacao, PrestacaoDocumentoAnexo.TIPO_DESPACHO),
            "comprovante_anexos": _documento_anexos_rows(prestacao, PrestacaoDocumentoAnexo.TIPO_COMPROVANTE),
        },
    )


@require_POST
def prestacao_autosave(request, pc_pk):
    prestacao = get_object_or_404(PrestacaoContas, pk=pc_pk)
    try:
        payload = parse_autosave_payload(request, expected_model="prestacao_contas")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    clean_fields = _prestacao_autosave_fields(payload)
    _salvar_prestacao_autosave(prestacao, clean_fields)
    return autosave_json_response(
        ok=True,
        object_id=prestacao.pk,
        version=_autosave_version(prestacao),
    )


@require_POST
def prestacao_arquivo_autosave(request, pc_pk):
    prestacao = get_object_or_404(PrestacaoContas, pk=pc_pk)
    form = PrestacaoDocumentosForm(request.POST, request.FILES, instance=prestacao)
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
# Assinatura eletrônica (RT e Diário de Bordo)
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


def _assinatura_card(request, prestacao, tipo, status_map) -> dict:
    doc = status_map.get(tipo)
    signer = signer_do_documento(prestacao, tipo)
    label = dict(AssinaturaDocumento.TIPO_CHOICES)[tipo]
    cpf_ok = bool(signer and len((getattr(signer, "cpf", "") or "").strip()) == 11)
    motivo = ""
    if signer is None:
        motivo = (
            "Defina o motorista do ofício para gerar o link."
            if tipo == AssinaturaDocumento.TIPO_DB
            else "Servidor da prestação não definido."
        )
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
        "gerar_url": reverse("prestacoes_contas:assinatura_gerar", args=[prestacao.pk]),
        "cancelar_url": reverse("prestacoes_contas:assinatura_cancelar", args=[prestacao.pk, tipo]),
    }


@require_POST
def assinatura_gerar(request, pc_pk):
    prestacao = get_object_or_404(
        PrestacaoContas.objects.select_related("oficio__motorista", "servidor"),
        pk=pc_pk,
    )
    tipos = request.POST.getlist("tipos")
    if not tipos and request.POST.get("tipo"):
        tipos = [request.POST.get("tipo")]
    forcar = request.POST.get("forcar") == "1"
    next_url = request.POST.get("next") or reverse(
        "prestacoes_contas:consolidado", args=[prestacao.pk]
    )
    try:
        token, _docs = emitir_link(prestacao, tipos, forcar=forcar)
    except (AssinaturaError, DocumentValidationError) as exc:
        messages.error(request, str(exc))
        return redirect(next_url)
    link = request.build_absolute_uri(
        reverse("prestacoes_contas:assinatura_landing", args=[token])
    )
    messages.success(request, f"Link de assinatura gerado. Envie ao signatário: {link}")
    return redirect(next_url)


@require_POST
def assinatura_cancelar(request, pc_pk, tipo):
    prestacao = get_object_or_404(PrestacaoContas, pk=pc_pk)
    next_url = request.POST.get("next") or reverse(
        "prestacoes_contas:consolidado", args=[prestacao.pk]
    )
    cancelar_assinatura(prestacao, tipo)
    messages.success(request, "Link/assinatura removidos. Você pode gerar um novo link.")
    return redirect(next_url)


def rt_criar(request, pc_pk):
    """Página única de criação/edição do RT de uma prestação, com dados do ofício exibidos."""
    prestacao = get_object_or_404(
        PrestacaoContas.objects.select_related(
            "oficio__roteiro",
            "servidor__cargo",
            "servidor__unidade",
        ),
        pk=pc_pk,
    )

    relatorio, _ = RelatorioTecnico.objects.get_or_create(prestacao=prestacao)
    garantir_campos_padrao_relatorio_tecnico(relatorio)
    identificacao = _build_identificacao(prestacao)

    if request.method == "POST":
        form = RelatorioTecnicoForm(request.POST, instance=relatorio, relatorio=relatorio)
        if form.is_valid():
            form.save()
            prestacao.status = PrestacaoContas.STATUS_EM_PREENCHIMENTO
            prestacao.save(update_fields=["status", "atualizado_em"])
            formato = "pdf" if request.POST.get("action") == "download_pdf" else "docx"
            return redirect("prestacoes_contas:rt_download_formato", pk=relatorio.pk, formato=formato)
    else:
        initial = {}
        if not relatorio.diaria:
            initial["diaria"] = diaria_inicial_da_prestacao(prestacao)
        if not relatorio.motivo:
            initial["motivo"] = prestacao.oficio.motivo or ""
        form = RelatorioTecnicoForm(instance=relatorio, relatorio=relatorio, initial=initial)

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
            "wizard_page_steps": _build_prestacao_steps(prestacao, "rt"),
            "diaria_info": diaria_info(prestacao),
            "assinatura": _assinatura_card(request, prestacao, AssinaturaDocumento.TIPO_RT, assinaturas_status(prestacao)),
            "assinatura_next_url": reverse("prestacoes_contas:rt_criar", args=[prestacao.pk]),
            "documentos_url": reverse("prestacoes_contas:documentos", args=[prestacao.pk]),
            "autosave_url": reverse("prestacoes_contas:rt_autosave", args=[relatorio.pk]),
            "preview_inline_url": reverse("prestacoes_contas:rt_download_formato", args=[relatorio.pk, "pdf"]) + "?inline=1",
            "preview_pdf_url": reverse("prestacoes_contas:rt_download_formato", args=[relatorio.pk, "pdf"]),
            "preview_docx_url": reverse("prestacoes_contas:rt_download_formato", args=[relatorio.pk, "docx"]),
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


def diario_criar(request, pc_pk):
    """Etapa 2 do wizard: diário de bordo do veículo a partir do roteiro do ofício."""
    prestacao = get_object_or_404(
        PrestacaoContas.objects.select_related(
            "oficio__roteiro",
            "oficio__viatura",
            "oficio__motorista",
            "servidor__cargo",
            "servidor__unidade",
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
            if prestacao.status == PrestacaoContas.STATUS_PENDENTE:
                prestacao.status = PrestacaoContas.STATUS_EM_PREENCHIMENTO
                prestacao.save(update_fields=["status", "atualizado_em"])
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
            "assinatura": _assinatura_card(request, prestacao, AssinaturaDocumento.TIPO_DB, assinaturas_status(prestacao)),
            "assinatura_next_url": reverse("prestacoes_contas:diario_criar", args=[prestacao.pk]),
            "editar_roteiro_url": reverse("prestacoes_contas:diario_editar_roteiro", args=[prestacao.pk]),
            "rt_url": reverse("prestacoes_contas:rt_criar", args=[prestacao.pk]),
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


def diario_download(request, pk, formato="xlsx"):
    diario = get_object_or_404(
        DiarioBordo.objects.select_related(
            "prestacao__oficio__roteiro",
            "prestacao__oficio__viatura",
            "prestacao__oficio__motorista",
            "prestacao__servidor",
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


def rt_download(request, pk, formato="docx"):
    relatorio = get_object_or_404(
        RelatorioTecnico.objects.select_related(
            "prestacao__oficio__roteiro",
            "prestacao__servidor",
        ),
        pk=pk,
    )

    inline = _is_inline_request(request)
    garantir_campos_padrao_relatorio_tecnico(relatorio)
    formato = (formato or "docx").strip().lower()
    if formato == "pdf":
        try:
            from .assinatura_services import pdf_rt_assinado_ou_gerado
            conteudo = pdf_rt_assinado_ou_gerado(relatorio.prestacao)
        except DocumentValidationError as exc:
            if inline:
                return _preview_error_response(exc)
            messages.error(request, str(exc))
            return redirect("prestacoes_contas:rt_criar", pc_pk=relatorio.prestacao_id)
        content_type = "application/pdf"
    else:
        conteudo = gerar_relatorio_tecnico_docx(relatorio)
        formato = "docx"
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    nome = nome_arquivo_rt(relatorio, formato=formato)

    disposition = "inline" if inline and formato == "pdf" else "attachment"
    response = HttpResponse(conteudo, content_type=content_type)
    response["Content-Disposition"] = f'{disposition}; filename="{nome}"'
    if disposition == "inline":
        response["X-Frame-Options"] = "SAMEORIGIN"
    return response


def consolidado(request, pc_pk):
    prestacao = get_object_or_404(
        PrestacaoContas.objects.select_related(
            "oficio__roteiro",
            "servidor__cargo",
            "servidor__unidade",
        ).prefetch_related("relatorio_tecnico", "documentos_anexos"),
        pk=pc_pk,
    )
    try:
        prestacao.relatorio_tecnico
        relatorio_ok = True
    except RelatorioTecnico.DoesNotExist:
        relatorio_ok = False
    diario_ok = DiarioBordo.objects.filter(prestacao=prestacao).exists()
    despacho_resumo = _documento_anexos_resumo(prestacao, PrestacaoDocumentoAnexo.TIPO_DESPACHO)
    comprovante_resumo = _documento_anexos_resumo(prestacao, PrestacaoDocumentoAnexo.TIPO_COMPROVANTE)
    itens = [
        {
            "label": "Número da solicitação",
            "status": bool((prestacao.numero_solicitacao or "").strip()),
            "value": prestacao.numero_solicitacao or "Pendente",
        },
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
        {
            "label": "Comprovante de saque/transferência",
            "status": comprovante_resumo["status"],
            "value": comprovante_resumo["value"],
        },
    ]

    status_map = assinaturas_status(prestacao)
    assinatura_rt = _assinatura_card(request, prestacao, AssinaturaDocumento.TIPO_RT, status_map)
    assinatura_db = _assinatura_card(request, prestacao, AssinaturaDocumento.TIPO_DB, status_map)
    combinado_possivel = (
        assinatura_rt["pode_assinar"]
        and assinatura_db["pode_assinar"]
        and not assinatura_rt["assinada"]
        and not assinatura_db["assinada"]
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
            "assinaturas": [assinatura_rt, assinatura_db],
            "assinatura_combinado_possivel": combinado_possivel,
            "assinatura_gerar_url": reverse("prestacoes_contas:assinatura_gerar", args=[prestacao.pk]),
            "assinatura_next_url": reverse("prestacoes_contas:consolidado", args=[prestacao.pk]),
            "download_url": reverse("prestacoes_contas:consolidado_download", args=[prestacao.pk]),
            "preview_inline_url": reverse("prestacoes_contas:consolidado_download", args=[prestacao.pk]) + "?inline=1",
            "diario_url": reverse("prestacoes_contas:diario_criar", args=[prestacao.pk]),
        },
    )


def consolidado_download(request, pc_pk):
    prestacao = get_object_or_404(
        PrestacaoContas.objects.select_related(
            "oficio__roteiro",
            "servidor",
        ),
        pk=pc_pk,
    )
    inline = _is_inline_request(request)
    try:
        conteudo = gerar_prestacao_consolidado_pdf(prestacao)
    except DocumentValidationError as exc:
        if inline:
            return _preview_error_response(exc)
        messages.error(request, str(exc))
        return redirect("prestacoes_contas:consolidado", pc_pk=prestacao.pk)

    nome = nome_arquivo_prestacao_consolidado(prestacao)
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
            modelos = modelos.filter(Q(nome__icontains=q) | Q(texto__icontains=q))

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
