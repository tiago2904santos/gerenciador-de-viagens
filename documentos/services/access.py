"""Regras de acesso e resolução de ficheiro PDF para artefatos documentais."""

from __future__ import annotations

from django.conf import settings
from django.db.models.fields.files import FieldFile
from django.http import Http404
from django.http import HttpRequest
from django.http import HttpResponse

from documentos.models import DocumentoArtefato
from documentos.services.filenames import slugify_filename_part
from documentos.services.pdf_streaming import build_pdf_inline_from_file_object
from documentos.services.pdf_streaming import build_pdf_inline_response


def ensure_request_may_view_artefato_pdf(request: HttpRequest, artefato: DocumentoArtefato) -> None:
    """Garante que o utilizador autenticado pode visualizar o PDF deste artefato."""
    del request  # reservado para regras futuras (ex.: dono do ofício)
    if artefato.formato != "pdf":
        raise Http404()
    if artefato.oficio_id:
        from oficios.selectors import get_oficio_by_id

        get_oficio_by_id(artefato.oficio_id)
        return
    if artefato.servidor_id:
        return
    raise Http404()


def select_artefato_pdf_fieldfile(artefato: DocumentoArtefato) -> FieldFile | None:
    """Campo de ficheiro a servir: assinado se existir no storage, senão o original."""
    versao = artefato.versoes_assinadas.filter(
        revogada_em__isnull=True,
    ).order_by("-criado_em").first()
    if versao is not None:
        assinado = versao.arquivo
        try:
            if assinado.storage.exists(assinado.name):
                return assinado
        except OSError:
            return None
    ass = artefato.arquivo_assinado
    if ass and getattr(ass, "name", ""):
        try:
            if ass.storage.exists(ass.name):
                return ass
        except OSError:
            return None
    arq = artefato.arquivo
    if arq and getattr(arq, "name", ""):
        try:
            if arq.storage.exists(arq.name):
                return arq
        except OSError:
            return None
    return None


def artefato_pdf_download_filename(artefato: DocumentoArtefato) -> str:
    base = slugify_filename_part(artefato.tipo)
    return f"{base}_{artefato.pk}.pdf"


def build_pdf_http_response_for_artefato(request: HttpRequest, artefato: DocumentoArtefato) -> HttpResponse:
    """Constrói a resposta HTTP inline (com Range) a partir do storage do artefato."""
    if not getattr(settings, "DOCUMENTOS_PERSIST_ARTEFATOS", False):
        raise Http404("Visualização de PDF requer artefatos persistidos.")
    field = select_artefato_pdf_fieldfile(artefato)
    if field is None:
        raise Http404("Ficheiro PDF não encontrado.")
    filename = artefato_pdf_download_filename(artefato)
    try:
        path = field.path
    except NotImplementedError:
        fh = field.open("rb")
        size = field.size
        return build_pdf_inline_from_file_object(
            request,
            file_obj=fh,
            file_size=size,
            filename=filename,
        )
    return build_pdf_inline_response(request, file_path=path, filename=filename)


def artefato_has_readable_pdf(artefato: DocumentoArtefato) -> bool:
    if artefato.formato != "pdf":
        return False
    if not getattr(settings, "DOCUMENTOS_PERSIST_ARTEFATOS", False):
        return False
    return select_artefato_pdf_fieldfile(artefato) is not None
