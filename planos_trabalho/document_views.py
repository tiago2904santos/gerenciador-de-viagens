from __future__ import annotations
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET
from documentos.services.responses import build_inline_pdf_response_from_download_response
from documentos.services.timing import measure_step
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo
from .presenters import apresentar_resumo_documentos
from .services import avaliar_pendencias_documento
from .services import gerar_resposta_plano_documento
from .services import marcar_plano_gerado
from .services import montar_efetivo_texto
from .services import sincronizar_scratchpad
from .services import montar_texto_coordenacao
from .services import montar_valor_do_plano_texto
from .view_helpers import _get_plano, _wizard_normalizar_acao, _redirect_plano_lista, _wizard_shell_ctx


def wizard_documentos(request, pk):
    plano = _get_plano(pk)
    # Em multi-evento, garante que o rascunho atual esteja refletido como evento
    # antes de avaliar pendências e gerar o documento (sem limpar o rascunho).
    sincronizar_scratchpad(plano)
    pendencias = avaliar_pendencias_documento(plano)

    if request.method == "POST":
        nav_action = _wizard_normalizar_acao(request.POST, default="save_draft")
        if nav_action == "finalizar":
            if pendencias:
                for msg in pendencias:
                    messages.error(request, msg)
                return redirect("planos_trabalho:wizard_documentos", pk=pk)
            marcar_plano_gerado(plano)
            messages.success(request, "Plano de trabalho finalizado com sucesso.")
            return _redirect_plano_lista(plano)
        if nav_action == "wizard_back":
            return redirect("planos_trabalho:wizard_atividades", pk=pk)
        if nav_action == "save_draft_list":
            messages.success(request, "Retornamos à lista de planos.")
            return _redirect_plano_lista(plano)
        return redirect("planos_trabalho:wizard_documentos", pk=pk)

    resumo_diarias = montar_valor_do_plano_texto(plano)
    return render(
        request,
        "planos_trabalho/wizard_documentos.html",
        {
            "page_title": "Plano de Trabalho",
            **_wizard_shell_ctx(plano=plano, etapa_atual="documentos"),
            "pendencias_documentos": pendencias,
            "mostrar_pendencias": bool(pendencias),
            "documento_disponivel": not pendencias,
            "is_multi_evento": plano.is_multi_evento,
            "evento_adicionar_url": reverse("planos_trabalho:evento_adicionar", args=[plano.pk]),
            "pdf_inline_url": reverse("planos_trabalho:pdf_inline", args=[plano.pk]),
            "baixar_docx_url": reverse("planos_trabalho:baixar_documento", args=[plano.pk, "docx"]),
            "baixar_pdf_url": reverse("planos_trabalho:baixar_documento", args=[plano.pk, "pdf"]),
            "resumo_documentos": apresentar_resumo_documentos(plano),
            "resumo": {
                "destino": plano.destino_display,
                "periodo": plano.periodo_display,
                "programa": plano.programa_display or "—",
                "horario": plano.horario_atendimento or "—",
                "efetivo": montar_efetivo_texto(plano) or "—",
                "valor_plano": resumo_diarias or "—",
                "coordenacao": (
                    (plano.coordenacao or "").strip()
                    or (montar_texto_coordenacao(plano) if plano.coordenacao_auto else "")
                    or "—"
                ),
            },
        },
    )


@require_GET
def pdf_inline(request, pk):
    plano = _get_plano(pk)
    pendencias = avaliar_pendencias_documento(plano)
    if pendencias:
        messages.error(request, "Documento não gerado porque o plano está incompleto.")
        return redirect(f"{reverse('planos_trabalho:wizard_documentos', args=[plano.pk])}?documento_incompleto=1")
    reference = f"{plano.numero:02d}-{plano.ano}" if plano.numero and plano.ano else f"plano-{plano.pk}"
    with measure_step("http_plano_trabalho_pdf_inline", {"plano_id": plano.pk}):
        try:
            resp = gerar_resposta_plano_documento(plano, DocumentoFormato.PDF)
        except Exception as exc:  # noqa: BLE001 — superfície amigável p/ erro de motor PDF
            messages.error(request, str(exc))
            return redirect("planos_trabalho:wizard_documentos", pk=plano.pk)
    return build_inline_pdf_response_from_download_response(
        request,
        resp,
        tipo=DocumentoTipo.PLANO_TRABALHO,
        reference=reference,
        now=timezone.now(),
    )


def baixar_documento(request, pk, formato):
    plano = _get_plano(pk)
    try:
        formato_documento = DocumentoFormato(formato)
    except ValueError as exc:
        raise Http404("Formato documental não suportado.") from exc

    pendencias = avaliar_pendencias_documento(plano)
    if pendencias:
        messages.error(request, "Documento não gerado porque o plano está incompleto.")
        return redirect(f"{reverse('planos_trabalho:wizard_documentos', args=[plano.pk])}?documento_incompleto=1")
    with measure_step(
        "http_baixar_plano_trabalho",
        {"plano_id": plano.pk, "formato": formato_documento.value},
    ):
        try:
            response = gerar_resposta_plano_documento(plano, formato_documento)
        except Exception as exc:  # noqa: BLE001
            if formato_documento == DocumentoFormato.PDF:
                messages.error(request, str(exc))
                return redirect("planos_trabalho:wizard_documentos", pk=plano.pk)
            raise
    marcar_plano_gerado(plano)
    return response
