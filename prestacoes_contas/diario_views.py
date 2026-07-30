import re
from urllib.parse import urlencode

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.autosave import AutosavePayloadError, autosave_json_response, parse_autosave_payload
from core.normalizers import normalize_spaces
from core.tenancy import filter_queryset_by_area
from core.utils.masks import format_cpf, format_protocolo
from documentos.services.async_generation import enfileirar_documento
from oficios.models import Oficio

from .diario_services import (
    diaria_info,
    garantir_roteiro_ajustado,
    motorista_diario,
    motorista_do_oficio,
    sincronizar_trechos,
    viatura_resumo_oficio,
)
from .forms import DiarioBordoTrechoFormSet, DiarioMotoristaForm
from .models import DiarioBordo, RelatorioTecnico
from .signature_views import _assinatura_db_card
from .view_common import (
    _autosave_version,
    _build_identificacao,
    _build_prestacao_steps,
    _diario_queryset,
    _is_inline_request,
    _marcar_servidor_em_preenchimento,
    _marcar_servidores_pendentes,
    _prestacao_queryset,
    _prestacao_servidor_full,
    _prestacao_servidor_queryset,
    _primeiro_servidor,
    _redirect_primeiro_servidor,
)


_MOTORISTA_ORIGEM_LABEL = {
    DiarioBordo.MOTORISTA_MODO_OFICIO: "Motorista do ofício",
    DiarioBordo.MOTORISTA_MODO_SERVIDOR: "Outro servidor deste ofício",
    DiarioBordo.MOTORISTA_MODO_OUTRO: "Motorista de outro ofício",
}


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


def diario_criar(request, pc_pk):
    """Compatibilidade: redireciona para o primeiro servidor."""
    prestacao = get_object_or_404(_prestacao_queryset(), pk=pc_pk)
    return _redirect_primeiro_servidor(request, prestacao, "prestacoes_contas:diario_servidor")


def diario_servidor(request, ps_pk):
    """Etapa 2 do wizard: diário compartilhado; navegação por servidor."""
    ps = _prestacao_servidor_full(ps_pk)
    prestacao = ps.prestacao

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
            _marcar_servidor_em_preenchimento(ps)
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
            "page_title": f"Diário de Bordo — {ps.servidor.nome}",
            "prestacao": prestacao,
            "ps": ps,
            "diario": diario,
            "formset": formset,
            "trechos": trechos,
            "identificacao": _build_identificacao(prestacao),
            "wizard_page_steps": _build_prestacao_steps(ps, "diario"),
            "diaria_info": diaria_info(prestacao),
            "back_url": reverse("prestacoes_contas:index"),
            "assinatura": _assinatura_db_card(request, prestacao),
            "assinatura_next_url": reverse("prestacoes_contas:diario_servidor", args=[ps.pk]),
            "editar_roteiro_url": reverse("prestacoes_contas:diario_servidor_editar_roteiro", args=[ps.pk]),
            "editar_motorista_url": reverse("prestacoes_contas:diario_servidor_motorista", args=[ps.pk]),
            "motorista_resumo": _motorista_resumo(diario),
            "rt_url": reverse("prestacoes_contas:rt_servidor", args=[ps.pk]),
            "documentos_url": reverse("prestacoes_contas:documentos_servidor", args=[ps.pk]),
            "autosave_url": reverse("prestacoes_contas:diario_servidor_autosave", args=[ps.pk]),
            "preview_inline_url": reverse("prestacoes_contas:diario_download_formato", args=[diario.pk, "pdf"]) + "?inline=1",
            "preview_pdf_url": reverse("prestacoes_contas:diario_download_formato", args=[diario.pk, "pdf"]),
            "preview_xlsx_url": reverse("prestacoes_contas:diario_download_formato", args=[diario.pk, "xlsx"]),
        },
    )


def diario_servidor_autosave(request, ps_pk):
    ps = get_object_or_404(_prestacao_servidor_queryset().select_related("prestacao"), pk=ps_pk)
    diario = get_object_or_404(_diario_queryset(), prestacao=ps.prestacao)
    sincronizar_trechos(diario)
    try:
        payload = parse_autosave_payload(request, expected_model="diario_bordo")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    _salvar_diario_autosave(diario, payload)
    if payload.dirty_fields:
        _marcar_servidor_em_preenchimento(ps)
    return autosave_json_response(
        ok=True,
        object_id=diario.pk,
        version=_autosave_version(diario),
    )


def diario_autosave(request, pk):
    diario = get_object_or_404(_diario_queryset().select_related("prestacao"), pk=pk)
    sincronizar_trechos(diario)
    try:
        payload = parse_autosave_payload(request, expected_model="diario_bordo")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    _salvar_diario_autosave(diario, payload)
    if payload.dirty_fields:
        _marcar_servidores_pendentes(diario.prestacao)
    return autosave_json_response(
        ok=True,
        object_id=diario.pk,
        version=_autosave_version(diario),
    )


def diario_editar_roteiro(request, pc_pk):
    """Compatibilidade: redireciona para o primeiro servidor."""
    prestacao = get_object_or_404(_prestacao_queryset(), pk=pc_pk)
    return _redirect_primeiro_servidor(request, prestacao, "prestacoes_contas:diario_servidor_editar_roteiro")


def diario_servidor_editar_roteiro(request, ps_pk):
    """Abre o editor de roteiro sobre a cópia da prestação (clona do ofício na 1ª vez)."""
    from urllib.parse import urlencode

    ps = get_object_or_404(
        _prestacao_servidor_queryset().select_related("prestacao__oficio__roteiro"),
        pk=ps_pk,
    )
    prestacao = ps.prestacao
    copia = garantir_roteiro_ajustado(prestacao)
    diario_url = reverse("prestacoes_contas:diario_servidor", args=[ps.pk])
    if copia is None:
        messages.error(request, "Este ofício não possui roteiro para editar.")
        return redirect(diario_url)
    editar_url = reverse("roteiros:editar", args=[copia.pk])
    return redirect(f"{editar_url}?{urlencode({'next': diario_url})}")


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
    """Compatibilidade: redireciona para o primeiro servidor."""
    prestacao = get_object_or_404(_prestacao_queryset(), pk=pc_pk)
    return _redirect_primeiro_servidor(request, prestacao, "prestacoes_contas:diario_servidor_motorista")


def diario_servidor_motorista(request, ps_pk):
    """Etapa 2 — troca o motorista/viatura apenas deste diário, sem alterar o ofício."""
    ps = get_object_or_404(
        _prestacao_servidor_queryset()
        .select_related("prestacao__oficio", "prestacao__oficio__viatura")
        .prefetch_related(
            "prestacao__oficio__servidores__cargo",
            "prestacao__oficio__servidores__unidade",
        ),
        pk=ps_pk,
    )
    prestacao = ps.prestacao
    diario, _ = DiarioBordo.objects.get_or_create(prestacao=prestacao)
    diario_url = reverse("prestacoes_contas:diario_servidor", args=[ps.pk])

    if request.method == "POST":
        form = DiarioMotoristaForm(request.POST, instance=diario, oficio=prestacao.oficio)
        if form.is_valid():
            form.save()
            _sincronizar_info_complementares_rt(prestacao)
            _marcar_servidor_em_preenchimento(ps)
            messages.success(request, "Diário de bordo atualizado (motorista/viatura).")
            return redirect(diario_url)
    else:
        form = DiarioMotoristaForm(instance=diario, oficio=prestacao.oficio)

    oficio_nome, oficio_cpf = motorista_do_oficio(prestacao.oficio)

    oficios = (
        filter_queryset_by_area(Oficio.objects)
        .select_related("viatura", "viatura__combustivel", "motorista", "transporte_combustivel_manual")
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
            "ps": ps,
            "diario": diario,
            "form": form,
            "identificacao": _build_identificacao(prestacao),
            "wizard_page_steps": _build_prestacao_steps(ps, "diario"),
            "back_url": reverse("prestacoes_contas:index"),
            "motorista_oficio_nome": oficio_nome or "—",
            "motorista_oficio_cpf": oficio_cpf,
            "viatura_oficio": viatura_resumo_oficio(prestacao.oficio),
            "oficios_prefill": oficios_prefill,
            "diario_url": diario_url,
        },
    )


def diario_download(request, pk, formato="xlsx"):
    diario = get_object_or_404(
        _diario_queryset().select_related(
            "prestacao__oficio__roteiro",
            "prestacao__oficio__viatura",
            "prestacao__oficio__motorista",
        ),
        pk=pk,
    )

    inline = _is_inline_request(request)
    formato = (formato or "xlsx").strip().lower()
    if formato not in {"pdf", "xlsx"}:
        formato = "xlsx"
    return enfileirar_documento(
        request,
        tipo="prestacao_diario",
        parametros={"object_id": diario.pk, "formato": formato},
        disposicao="inline" if inline and formato == "pdf" else "attachment",
    )
