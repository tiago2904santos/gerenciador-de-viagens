"""Respostas HTTP para downloads documentais (centralizar comportamento partilhado)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from documentos.services.exceptions import DocumentValidationError
from documentos.services.types import DocumentoFormato

if TYPE_CHECKING:
    from django.http import HttpResponse


def download_documento_or_redirect_pdf_error(
    request,
    *,
    oficio_id: int,
    formato: DocumentoFormato,
    gerar: Callable[[], HttpResponse],
):
    """
    Para PDF, captura falhas de motor/configuração e redireciona ao wizard de documentos
    com mensagem; DOCX e outros formatos propagam excepções.
    """
    if formato != DocumentoFormato.PDF:
        return gerar()
    try:
        return gerar()
    except DocumentValidationError as exc:
        messages.error(request, str(exc))
        return redirect(reverse("oficios:wizard_documentos", args=[oficio_id]))
