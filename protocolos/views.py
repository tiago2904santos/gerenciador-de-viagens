"""Views da Central de Protocolos — fachada fina.

As views chamam APENAS ``forms``/``selectors``/``services``/``permissions`` —
nunca o client HTTP do eProtocolo, e nunca um manager de modelo: a catraca de
ORM em views (`core/tests/test_view_module_boundaries.py`) conta cada acesso,
e a resolução de content type que morava aqui desceu para ``selectors``.
Feedback ao usuário sempre via ``django.contrib.messages``.

Fatia 1 da restauração (NOVO-20260823-014253): index, detalhe, criação (de
ofício ou vínculo manual), envio de documento e sincronização. Assinatura,
tramitação, conclusão e páginas de movimentações/logs voltam na fatia 2.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from integracoes.eprotocolo import settings as epro_cfg
from integracoes.eprotocolo.exceptions import EProtocoloError

from . import forms, permissions, selectors, services
from .models import Protocolo

_login = login_required(login_url="core:login")


# ---------------------------------------------------------------------------
# Contexto comum
# ---------------------------------------------------------------------------
def _contexto_integracao() -> dict:
    modo_demo = epro_cfg.em_modo_mock()
    return {
        "eprotocolo_configurado": epro_cfg.eprotocolo_esta_configurado(),
        "eprotocolo_descricao": epro_cfg.descricao_ambiente(),
        "eprotocolo_modo_mock": modo_demo,
        "eprotocolo_modo_demo": modo_demo,
        "eprotocolo_demo_label": "Modo demonstração" if modo_demo else epro_cfg.descricao_ambiente(),
        "eprotocolo_ambiente_label": "Treinamento" if modo_demo else epro_cfg.ambiente(),
    }


def _avisar_modo(request):
    """Um aviso por operação em ambiente não-real.

    A versão original tinha um segundo `messages.warning` inalcançável depois
    do `return` — resto de edição da fase demo, removido na restauração.
    """
    if not epro_cfg.eprotocolo_esta_configurado():
        messages.warning(
            request,
            "Operação registrada em ambiente de treinamento/mock. Nenhuma chamada real foi feita.",
        )


# ---------------------------------------------------------------------------
# Lista
# ---------------------------------------------------------------------------
@_login
def index(request):
    if epro_cfg.em_modo_mock():
        services.garantir_protocolos_demo_treinamento()
    busca = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    protocolos = selectors.listar_protocolos(busca=busca, status=status)

    contexto = {
        "page_title": "Central de Protocolos",
        "protocolos": protocolos,
        "q": busca,
        "status": status,
        "status_options": selectors.status_local_options(),
        "create_url": reverse("protocolos:protocolo_create"),
        "search_clear_url": reverse("protocolos:index"),
        "has_filters": bool(busca or status),
        **_contexto_integracao(),
    }
    return render(request, "protocolos/index.html", contexto)


# ---------------------------------------------------------------------------
# Detalhe
# ---------------------------------------------------------------------------
@_login
def detail(request, pk):
    try:
        protocolo = selectors.obter_protocolo_detalhado(pk)
    except Protocolo.DoesNotExist as exc:
        raise Http404("Protocolo não encontrado.") from exc

    contexto = {
        "page_title": f"Protocolo {protocolo.numero_display}",
        "protocolo": protocolo,
        "resumo_operacional": services.resumo_operacional(protocolo),
        "documentos": protocolo.documentos.all(),
        "assinaturas": protocolo.assinaturas.all(),
        "pendencias": protocolo.pendencias.all(),
        "tramitacoes": protocolo.tramitacoes.all(),
        "movimentacoes": protocolo.movimentacoes.all(),
        **_contexto_integracao(),
    }
    return render(request, "protocolos/detalhe.html", contexto)


# ---------------------------------------------------------------------------
# Criação — uma tela, dois caminhos: protocolar um ofício ou vincular número
# ---------------------------------------------------------------------------
@_login
def protocolo_create(request):
    if not permissions.pode_criar_protocolo(request.user):
        messages.error(request, "Você não tem permissão para criar protocolos.")
        return redirect("protocolos:index")

    form = forms.VinculoManualForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        protocolo = services.vincular_protocolo_manual(
            form.cleaned_data["numero"],
            assunto=form.cleaned_data["assunto"],
            descricao=form.cleaned_data["descricao"],
        )
        messages.success(request, "Protocolo cadastrado com sucesso.")
        return redirect("protocolos:detail", pk=protocolo.pk)

    contexto = {
        "page_title": "Novo protocolo",
        "form": form,
        "form_action": reverse("protocolos:protocolo_create"),
        "protocolar_form": forms.ProtocolarOficioForm(),
        "protocolar_action": reverse("protocolos:vincular"),
        "oficio_content_type_id": selectors.content_type_id_de_oficio(),
        **_contexto_integracao(),
    }
    return render(request, "protocolos/form.html", contexto)


# ---------------------------------------------------------------------------
# Protocolar a partir de um documento interno
# ---------------------------------------------------------------------------
@_login
@require_POST
def vincular(request):
    """POST-only: a tela de criação já É a confirmação.

    A versão original tinha um GET de confirmação em página própria; no v2 a
    confirmação é o próprio formulário — quem chega aqui já escolheu o ofício.
    """
    if not permissions.pode_criar_protocolo(request.user):
        messages.error(request, "Você não tem permissão para gerar protocolos.")
        return redirect("protocolos:index")

    # `object_id` é o contrato dos links vindos de outros documentos (fatia 3);
    # `oficio` é o name do form da tela de criação. Os dois chegam aqui.
    documento = selectors.origem_por_content_type(
        request.POST.get("content_type_id"),
        request.POST.get("object_id") or request.POST.get("oficio"),
    )
    if documento is None:
        messages.error(request, "Documento de origem inválido.")
        return redirect("protocolos:protocolo_create")

    enviar_pdf = request.POST.get("enviar_documento") == "1"
    try:
        protocolo = services.criar_protocolo_a_partir_de_documento(documento)
        _avisar_modo(request)
        messages.success(request, f"Protocolo gerado: {protocolo.numero_display}.")
        if enviar_pdf:
            doc = services.enviar_documento_principal(protocolo)
            if doc is None:
                messages.info(
                    request,
                    "O PDF do documento não pôde ser gerado automaticamente neste "
                    "ambiente. Você pode anexá-lo manualmente na tela do protocolo.",
                )
    except EProtocoloError as exc:
        messages.error(request, getattr(exc, "mensagem_usuario", str(exc)))
        return redirect("protocolos:protocolo_create")
    return redirect("protocolos:detail", pk=protocolo.pk)


# ---------------------------------------------------------------------------
# Atualizar / sincronizar
# ---------------------------------------------------------------------------
@_login
@require_POST
def atualizar(request, pk):
    """POST-only: a confirmação é o modal do v2 na tela de detalhe."""
    protocolo = get_object_or_404(Protocolo, pk=pk)
    try:
        services.sincronizar_protocolo(protocolo)
        _avisar_modo(request)
        messages.success(
            request,
            "Situação atualizada em ambiente de treinamento."
            if epro_cfg.em_modo_mock() else "Situação do protocolo atualizada.",
        )
    except EProtocoloError as exc:
        messages.error(request, getattr(exc, "mensagem_usuario", str(exc)))
    return redirect("protocolos:detail", pk=pk)


# ---------------------------------------------------------------------------
# Enviar documento
# ---------------------------------------------------------------------------
@_login
def enviar_documento(request, pk):
    protocolo = get_object_or_404(Protocolo, pk=pk)
    if not permissions.pode_enviar_documento(request.user):
        messages.error(request, "Você não tem permissão para enviar documentos.")
        return redirect("protocolos:detail", pk=pk)

    form = forms.AnexarDocumentoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            if form.cleaned_data.get("usar_documento_principal") and protocolo.origem_object is not None:
                doc = services.enviar_documento_principal(protocolo)
                if doc is None:
                    messages.warning(request, "Não foi possível gerar o PDF do documento vinculado.")
                else:
                    _avisar_modo(request)
                    messages.success(
                        request,
                        "Documento enviado em modo simulado."
                        if epro_cfg.em_modo_mock() else "Documento principal enviado.",
                    )
            else:
                arquivo = form.cleaned_data["arquivo"]
                conteudo = arquivo.read()
                nome = form.cleaned_data.get("nome_arquivo") or arquivo.name
                services.anexar_documento(
                    protocolo,
                    tipo=form.cleaned_data["tipo_documento"],
                    nome_arquivo=nome,
                    conteudo=conteudo,
                )
                _avisar_modo(request)
                messages.success(
                    request,
                    "Documento enviado em modo simulado."
                    if epro_cfg.em_modo_mock() else "Documento enviado e registrado.",
                )
            return redirect("protocolos:detail", pk=pk)
        except EProtocoloError as exc:
            messages.error(request, getattr(exc, "mensagem_usuario", str(exc)))

    contexto = {
        "page_title": f"Enviar documento — {protocolo.numero_display}",
        "protocolo": protocolo,
        "form": form,
        "form_action": reverse("protocolos:enviar_documento", args=[pk]),
        "voltar_url": reverse("protocolos:detail", args=[pk]),
        **_contexto_integracao(),
    }
    return render(request, "protocolos/enviar_documento.html", contexto)
