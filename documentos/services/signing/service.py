from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any

from django.conf import settings


FIELD_NAME_DEFAULT = "AssinaturaCentralViagens"


class ServicoAssinaturaPDF:
    """Assina bytes de PDF conforme `SIGNATURE_BACKEND` nos settings."""

    def assinar(self, pdf_bytes: bytes) -> tuple[bytes, dict[str, Any]]:
        return assinar_pdf_final(pdf_bytes)


def assinar_pdf_final(
    pdf_bytes: bytes,
    *,
    signature_position: dict[str, Any] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    backend = (getattr(settings, "SIGNATURE_BACKEND", "disabled") or "disabled").lower()
    sha_in = hashlib.sha256(pdf_bytes).hexdigest()
    if backend == "disabled":
        return pdf_bytes, {
            "backend": "disabled",
            "field_name": FIELD_NAME_DEFAULT,
            "sha256_in": sha_in,
            "sha256_out": sha_in,
            "visible": False,
            "signature_position": signature_position,
        }
    if backend == "pkcs12":
        signed, meta = _assinar_pkcs12(
            pdf_bytes,
            sha256_in=sha_in,
            signature_position=signature_position,
        )
        meta.setdefault("field_name", FIELD_NAME_DEFAULT)
        return signed, meta
    raise ValueError(f"Backend de assinatura não suportado: {backend}")


def _assinar_pkcs12(
    pdf_bytes: bytes,
    *,
    sha256_in: str,
    signature_position: dict[str, Any] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    path = getattr(settings, "SIGNATURE_PKCS12_PATH", None)
    if not path:
        raise RuntimeError("SIGNATURE_PKCS12_PATH não configurado.")
    password = getattr(settings, "SIGNATURE_PKCS12_PASSWORD", None) or ""

    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign import fields
    from pyhanko.sign.fields import PdfWriteError
    from pyhanko.sign.signers import PdfSignatureMetadata
    from pyhanko.sign.signers import PdfSigner
    from pyhanko.sign.signers import SimpleSigner

    passphrase = password.encode("utf-8") if password else None
    simple = SimpleSigner.load_pkcs12(pfx_file=path, passphrase=passphrase)

    reader = PdfFileReader(BytesIO(pdf_bytes))
    writer = IncrementalPdfFileWriter(reader)

    reason = (getattr(settings, "SIGNATURE_REASON", None) or "").strip() or None
    location = (getattr(settings, "SIGNATURE_LOCATION", None) or "").strip() or None
    visible = getattr(settings, "SIGNATURE_VISIBLE", True)
    field_name = getattr(settings, "SIGNATURE_FIELD_NAME", None) or FIELD_NAME_DEFAULT

    appended_visible = False
    if signature_position:
        visible = False
    if visible:
        try:
            fields.append_signature_field(
                writer,
                fields.SigFieldSpec(
                    sig_field_name=field_name,
                    on_page=-1,
                    box=(72, 120, 340, 200),
                    doc_mdp_update_value=fields.MDPPerm.NO_CHANGES,
                ),
            )
            appended_visible = True
        except (PdfWriteError, OSError, ValueError, KeyError):
            appended_visible = False

    meta_sig = PdfSignatureMetadata(
        field_name=field_name,
        reason=reason,
        location=location,
        embed_validation_info=False,
    )
    pdf_signer = PdfSigner(signature_meta=meta_sig, signer=simple)
    out = BytesIO()
    pdf_signer.sign_pdf(writer, output=out)
    signed = out.getvalue()
    sha_out = hashlib.sha256(signed).hexdigest()
    return signed, {
        "backend": "pkcs12",
        "field_name": field_name,
        "sha256_in": sha256_in,
        "sha256_out": sha_out,
        "visible": bool(visible and appended_visible),
        "reason": reason or "",
        "location": location or "",
        "signature_position": signature_position,
    }
