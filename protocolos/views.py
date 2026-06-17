"""Views da Central de Protocolos.

As views chamam APENAS ``protocolos.services`` / ``protocolos.selectors`` —
nunca o client HTTP do eProtocolo diretamente. Feedback ao usuário sempre via
``django.contrib.messages``.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

_login = login_required(login_url="core:login")

from integracoes.eprotocolo import settings as epro_cfg
from integracoes.eprotocolo.exceptions import EProtocoloError

from . import forms, permissions, selectors, services
from .models import Protocolo, ProtocoloDocumento


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
        "eprotocolo_demo_label": "Modo demonstracao" if modo_demo else epro_cfg.descricao_ambiente(),
        "eprotocolo_ambiente_label": "Treinamento" if modo_demo else epro_cfg.ambiente(),
    }


def _avisar_modo(request):
    if not epro_cfg.eprotocolo_esta_configurado():
        messages.warning(
            request,
            "Operacao registrada em ambiente de treinamento/mock. Nenhuma chamada real foi feita.",
        )
        return
        messages.warning(
            request,
            "Integração eProtocolo em modo mock — nenhuma chamada real foi feita. "
            "Configure as credenciais no .env para ativar o modo real.",
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
    protocolos_resumo = {protocolo.pk: services.resumo_operacional(protocolo) for protocolo in protocolos}

    contexto = {
        "page_title": "Central de Protocolos",
        "protocolos": protocolos,
        "protocolos_resumo": protocolos_resumo,
        "q": busca,
        "status": status,
        "status_options": selectors.status_local_options(),
        "create_url": reverse("protocolos:novo"),
        "search_clear_url": reverse("protocolos:index"),
        "empty_message": "Nenhum protocolo encontrado.",
        **_contexto_integracao(),
    }
    return render(request, "protocolos/protocolo_list.html", contexto)


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
        "logs": protocolo.logs.all()[:50],
        **_contexto_integracao(),
    }
    return render(request, "protocolos/protocolo_detail.html", contexto)


# ---------------------------------------------------------------------------
# Criação manual
# ---------------------------------------------------------------------------
@_login
def novo(request):
    if not permissions.pode_criar_protocolo(request.user):
        messages.error(request, "Você não tem permissão para criar protocolos.")
        return redirect("protocolos:index")

    if request.method == "POST":
        form = forms.VinculoManualForm(request.POST)
        if form.is_valid():
            protocolo = services.vincular_protocolo_manual(
                form.cleaned_data["numero"],
                assunto=form.cleaned_data["assunto"],
                descricao=form.cleaned_data["descricao"],
            )
            messages.success(request, "Protocolo cadastrado com sucesso.")
            return redirect("protocolos:detail", pk=protocolo.pk)
    else:
        form = forms.VinculoManualForm()

    contexto = {
        "page_title": "Novo protocolo",
        "form": form,
        "form_action": reverse("protocolos:novo"),
        "submit_label": "Cadastrar protocolo",
        **_contexto_integracao(),
    }
    return render(request, "protocolos/protocolo_form.html", contexto)


# ---------------------------------------------------------------------------
# Criar a partir de documento interno (compact block → "Gerar protocolo")
# ---------------------------------------------------------------------------
@_login
def vincular(request):
    if not permissions.pode_criar_protocolo(request.user):
        messages.error(request, "Você não tem permissão para gerar protocolos.")
        return redirect("protocolos:index")

    if request.method == "GET":
        content_type_id = request.GET.get("content_type_id")
        object_id = request.GET.get("object_id")
        documento = _resolver_documento(content_type_id, object_id)
        if documento is None:
            messages.error(request, "Documento de origem inválido.")
            return redirect("protocolos:index")
        contexto = {
            "page_title": "Gerar protocolo",
            "form_action": reverse("protocolos:vincular"),
            "confirm_message": f"Gerar um protocolo no eProtocolo a partir de “{documento}”?",
            "submit_label": "Gerar protocolo",
            "cancel_url": reverse("protocolos:index"),
            "hidden_fields": {
                "content_type_id": content_type_id,
                "object_id": object_id,
                "enviar_documento": request.GET.get("enviar_documento", "1"),
            },
            **_contexto_integracao(),
        }
        return render(request, "protocolos/protocolo_confirm.html", contexto)

    documento = _resolver_documento(request.POST.get("content_type_id"),
                                    request.POST.get("object_id"))
    if documento is None:
        messages.error(request, "Documento de origem inválido.")
        return redirect("protocolos:index")

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
        return redirect("protocolos:index")
    return redirect("protocolos:detail", pk=protocolo.pk)


# ---------------------------------------------------------------------------
# Atualizar / sincronizar
# ---------------------------------------------------------------------------
@_login
def atualizar(request, pk):
    protocolo = get_object_or_404(Protocolo, pk=pk)
    if request.method == "GET":
        contexto = {
            "page_title": f"Atualizar situação — {protocolo.numero_display}",
            "form_action": reverse("protocolos:atualizar", args=[pk]),
            "confirm_message": "Sincronizar este protocolo com o eProtocolo agora?",
            "submit_label": "Atualizar situação",
            "cancel_url": reverse("protocolos:detail", args=[pk]),
            "hidden_fields": {},
            **_contexto_integracao(),
        }
        return render(request, "protocolos/protocolo_confirm.html", contexto)
    try:
        services.sincronizar_protocolo(protocolo)
        _avisar_modo(request)
        messages.success(
            request,
            "Situacao atualizada em ambiente de treinamento."
            if epro_cfg.em_modo_mock() else "Situacao do protocolo atualizada.",
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

    if request.method == "POST":
        form = forms.AnexarDocumentoForm(request.POST, request.FILES)
        if form.is_valid():
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
    else:
        form = forms.AnexarDocumentoForm()

    contexto = {
        "page_title": f"Enviar documento — {protocolo.numero_display}",
        "protocolo": protocolo,
        "form": form,
        "form_action": reverse("protocolos:enviar_documento", args=[pk]),
        "submit_label": "Enviar documento",
        **_contexto_integracao(),
    }
    return render(request, "protocolos/protocolo_form.html", contexto)


# ---------------------------------------------------------------------------
# Concluir cadastro
# ---------------------------------------------------------------------------
@_login
@require_POST
def concluir(request, pk):
    protocolo = get_object_or_404(Protocolo, pk=pk)
    try:
        services.concluir_cadastro_eprotocolo(protocolo)
        _avisar_modo(request)
        messages.success(
            request,
            "Cadastro concluido em modo treinamento."
            if epro_cfg.em_modo_mock() else "Cadastro do protocolo concluido.",
        )
    except EProtocoloError as exc:
        messages.error(request, getattr(exc, "mensagem_usuario", str(exc)))
    return redirect("protocolos:detail", pk=pk)


# ---------------------------------------------------------------------------
# Solicitar assinatura
# ---------------------------------------------------------------------------
@_login
def solicitar_assinatura(request, pk):
    protocolo = get_object_or_404(Protocolo, pk=pk)
    if not permissions.pode_solicitar_assinatura(request.user):
        messages.error(request, "Você não tem permissão para solicitar assinaturas.")
        return redirect("protocolos:detail", pk=pk)

    if request.method == "POST":
        form = forms.SolicitarAssinaturaForm(request.POST, protocolo=protocolo)
        if form.is_valid():
            try:
                services.solicitar_assinatura_documento(
                    protocolo,
                    documento=form.cleaned_data.get("documento"),
                    cpf=form.cleaned_data["cpf"],
                    nome=form.cleaned_data["nome"],
                    observacao=form.cleaned_data.get("observacao", ""),
                )
                _avisar_modo(request)
                messages.success(
                    request,
                    "Assinatura solicitada em modo treinamento."
                    if epro_cfg.em_modo_mock() else "Solicitacao de assinatura registrada.",
                )
                return redirect("protocolos:detail", pk=pk)
            except EProtocoloError as exc:
                messages.error(request, getattr(exc, "mensagem_usuario", str(exc)))
    else:
        form = forms.SolicitarAssinaturaForm(protocolo=protocolo)

    contexto = {
        "page_title": f"Solicitar assinatura — {protocolo.numero_display}",
        "protocolo": protocolo,
        "form": form,
        "form_action": reverse("protocolos:solicitar_assinatura", args=[pk]),
        "submit_label": "Solicitar assinatura",
        **_contexto_integracao(),
    }
    return render(request, "protocolos/protocolo_form.html", contexto)


# ---------------------------------------------------------------------------
# Tramitar
# ---------------------------------------------------------------------------
@_login
def tramitar(request, pk):
    protocolo = get_object_or_404(Protocolo, pk=pk)
    if not permissions.pode_tramitar(request.user):
        messages.error(request, "Você não tem permissão para tramitar protocolos.")
        return redirect("protocolos:detail", pk=pk)

    if request.method == "POST":
        form = forms.TramitarForm(request.POST)
        if form.is_valid():
            try:
                services.tramitar(
                    protocolo,
                    form.cleaned_data["cod_local_para"],
                    cpf_destinatario=form.cleaned_data.get("cpf_destinatario"),
                    parecer=form.cleaned_data.get("parecer"),
                    nome_local_para=form.cleaned_data.get("nome_local_para", ""),
                    nome_destinatario=form.cleaned_data.get("nome_destinatario", ""),
                )
                _avisar_modo(request)
                messages.success(
                    request,
                    "Tramitacao simulada registrada."
                    if epro_cfg.em_modo_mock() else "Protocolo tramitado.",
                )
                return redirect("protocolos:detail", pk=pk)
            except EProtocoloError as exc:
                messages.error(request, getattr(exc, "mensagem_usuario", str(exc)))
    else:
        form = forms.TramitarForm()

    contexto = {
        "page_title": f"Tramitar — {protocolo.numero_display}",
        "protocolo": protocolo,
        "form": form,
        "form_action": reverse("protocolos:tramitar", args=[pk]),
        "submit_label": "Tramitar protocolo",
        **_contexto_integracao(),
    }
    return render(request, "protocolos/protocolo_form.html", contexto)


# ---------------------------------------------------------------------------
# Movimentações / Logs (páginas focadas)
# ---------------------------------------------------------------------------
@_login
def movimentacoes(request, pk):
    protocolo = get_object_or_404(Protocolo, pk=pk)
    contexto = {
        "page_title": f"Movimentações — {protocolo.numero_display}",
        "protocolo": protocolo,
        "movimentacoes": protocolo.movimentacoes.all(),
        **_contexto_integracao(),
    }
    return render(request, "protocolos/protocolo_movimentacoes.html", contexto)


@_login
def logs(request, pk):
    protocolo = get_object_or_404(Protocolo, pk=pk)
    contexto = {
        "page_title": f"Logs de integração — {protocolo.numero_display}",
        "protocolo": protocolo,
        "logs": protocolo.logs.all()[:200],
        **_contexto_integracao(),
    }
    return render(request, "protocolos/protocolo_logs.html", contexto)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _resolver_documento(content_type_id, object_id):
    if not (content_type_id and object_id):
        return None
    try:
        ct = ContentType.objects.get_for_id(int(content_type_id))
        return ct.get_object_for_this_type(pk=int(object_id))
    except (ContentType.DoesNotExist, ValueError, LookupError):
        return None
    except Exception:
        return None
