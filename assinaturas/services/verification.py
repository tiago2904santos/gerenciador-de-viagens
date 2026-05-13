from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any

from documentos.models import DocumentoArtefato
from documentos.services.access import select_artefato_pdf_fieldfile


def _verificar_artefato_etiqueta_pdf(artefato: DocumentoArtefato) -> dict[str, Any]:
    from assinaturas.models import AssinaturaDigital
    from assinaturas.services.assinatura_artefato import assinatura_arquivo_esta_integra

    reg = AssinaturaDigital.objects.filter(artefato=artefato).order_by("-criado_em").first()
    if reg is None:
        return {
            "ok": False,
            "reason": "no_registration",
            "detail": "Sem registo de assinatura para o artefato.",
        }
    if not assinatura_arquivo_esta_integra(reg):
        return {
            "ok": False,
            "reason": "hash_mismatch",
            "detail": "O PDF assinado não coincide com o hash guardado.",
        }
    return {
        "ok": True,
        "reason": "ok",
        "summary": "Etiqueta PDF e hash consistentes.",
        "backend": "etiqueta_pdf",
    }


def verificar_pdf_bytes(pdf_bytes: bytes) -> dict[str, Any]:
    """Validação criptográfica/estrutural das assinaturas embutidas no PDF (pyHanko)."""
    from pyhanko.pdf_utils.misc import PdfReadError
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature

    try:
        reader = PdfFileReader(BytesIO(pdf_bytes))
        embedded = list(reader.embedded_regular_signatures)
    except PdfReadError as exc:
        return {"ok": False, "reason": "pdf_read_error", "detail": str(exc)}
    if not embedded:
        return {"ok": False, "reason": "no_signatures"}

    sig = embedded[0]
    try:
        status = validate_pdf_signature(sig)
    except Exception as exc:  # noqa: BLE001 — erros variados da cadeia/ASN.1
        return {"ok": False, "reason": "validation_error", "detail": str(exc)}

    summary = ""
    try:
        summary = status.pretty_print_details()
    except Exception:  # noqa: BLE001
        summary = ""

    return {
        "ok": bool(status.bottom_line),
        "reason": "ok" if status.bottom_line else "signature_invalid",
        "summary": summary,
    }


def verificar_artefato_documento(artefato: DocumentoArtefato) -> dict[str, Any]:
    """
    Duas camadas: validação das assinaturas no ficheiro PDF servido e confronto com hash persistido.
    Para `assinatura_backend=etiqueta_pdf`, valida apenas integridade com o registo AssinaturaDigital.
    """
    if (artefato.assinatura_backend or "").strip() == "etiqueta_pdf":
        return _verificar_artefato_etiqueta_pdf(artefato)
    field = select_artefato_pdf_fieldfile(artefato)
    if field is None:
        return {"ok": False, "reason": "no_file"}
    try:
        data = field.read()
    except OSError as exc:
        return {"ok": False, "reason": "read_error", "detail": str(exc)}

    crypto = verificar_pdf_bytes(data)
    if not crypto.get("ok"):
        return crypto

    digest = hashlib.sha256(data).hexdigest()
    if artefato.arquivo_assinado and getattr(artefato.arquivo_assinado, "name", ""):
        expected = (artefato.hash_sha256_assinado or "").strip().lower()
        if expected and digest != expected:
            return {
                "ok": False,
                "reason": "hash_mismatch",
                "detail": "O ficheiro servido não coincide com o hash registado após assinatura.",
            }

    return crypto
