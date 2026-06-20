from decimal import Decimal

from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse

from core.presenters.meta import build_meta
from core.utils.masks import format_protocolo
from documentos.services.exceptions import DocumentValidationError

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
from .forms import RelatorioTecnicoForm
from .models import DiarioBordo
from .models import ModeloTextoRelatorioTecnico
from .models import PrestacaoContas
from .models import RelatorioTecnico
from .services import gerar_relatorio_tecnico_docx
from .services import gerar_relatorio_tecnico_pdf
from .services import nome_arquivo_rt


def _diaria_inicial_da_prestacao(prestacao) -> str:
    try:
        from documentos.services.formatters import format_currency_br
        oficio = prestacao.oficio
        roteiro = oficio.roteiro
        if roteiro and roteiro.valor_diarias:
            total_servidores = oficio.servidores.count() or 1
            valor_por_servidor = Decimal(roteiro.valor_diarias) / Decimal(total_servidores)
            return format_currency_br(valor_por_servidor)
    except Exception:
        pass
    return ""


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


def _build_prestacao_steps(prestacao, atual: str) -> list:
    """Etapas do wizard da prestação: 1) Relatório Técnico, 2) Diário de Bordo."""
    rt_url = reverse("prestacoes_contas:rt_criar", args=[prestacao.pk])
    diario_url = reverse("prestacoes_contas:diario_criar", args=[prestacao.pk])
    etapas = [
        ("rt", "Etapa 1", "Relatório Técnico", rt_url),
        ("diario", "Etapa 2", "Diário de Bordo", diario_url),
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
    prestacoes = (
        PrestacaoContas.objects.select_related(
            "oficio",
            "servidor",
            "servidor__cargo",
            "servidor__unidade",
        )
        .prefetch_related("relatorio_tecnico")
        .order_by("-criado_em")
    )
    return render(
        request,
        "prestacoes_contas/index.html",
        {
            "page_title": "Prestações de Contas",
            "page_description": "Acompanhamento das prestações de contas por servidor e ofício.",
            "prestacoes": prestacoes,
        },
    )


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
            initial["diaria"] = _diaria_inicial_da_prestacao(prestacao)
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
        },
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
            "editar_roteiro_url": reverse("prestacoes_contas:diario_editar_roteiro", args=[prestacao.pk]),
            "rt_url": reverse("prestacoes_contas:rt_criar", args=[prestacao.pk]),
        },
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

    formato = (formato or "xlsx").strip().lower()
    if formato == "pdf":
        try:
            conteudo = gerar_diario_bordo_pdf(diario)
        except DocumentValidationError as exc:
            messages.error(request, str(exc))
            return redirect("prestacoes_contas:diario_criar", pc_pk=diario.prestacao_id)
        content_type = "application/pdf"
    else:
        conteudo = gerar_diario_bordo_xlsx(diario)
        formato = "xlsx"
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    nome = nome_arquivo_diario(diario, formato=formato)
    response = HttpResponse(conteudo, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{nome}"'
    return response


def rt_download(request, pk, formato="docx"):
    relatorio = get_object_or_404(
        RelatorioTecnico.objects.select_related(
            "prestacao__oficio__roteiro",
            "prestacao__servidor",
        ),
        pk=pk,
    )

    formato = (formato or "docx").strip().lower()
    if formato == "pdf":
        try:
            conteudo = gerar_relatorio_tecnico_pdf(relatorio)
        except DocumentValidationError as exc:
            messages.error(request, str(exc))
            return redirect("prestacoes_contas:rt_criar", pc_pk=relatorio.prestacao_id)
        content_type = "application/pdf"
    else:
        conteudo = gerar_relatorio_tecnico_docx(relatorio)
        formato = "docx"
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    nome = nome_arquivo_rt(relatorio, formato=formato)

    response = HttpResponse(conteudo, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{nome}"'
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
