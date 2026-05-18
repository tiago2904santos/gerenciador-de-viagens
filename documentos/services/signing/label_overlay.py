"""Desenha a etiqueta institucional no PDF (conteúdo vetorial) antes da assinatura criptográfica."""

from __future__ import annotations

import io
import logging
import re
from typing import Any

from pypdf import PdfReader
from pypdf import PdfWriter

from documentos.services.signing.position import SignaturePositionNormalizada

logger = logging.getLogger(__name__)


def _page_dimensions_pt(page) -> tuple[float, float]:
    mb = page.mediabox
    return float(mb.width), float(mb.height)


def _looks_like_sha256_prefix(value: str) -> bool:
    """Fragmentos de hash SHA-256 não devem aparecer como «código» legível na etiqueta."""
    s = (value or "").strip()
    if len(s) != 12:
        return False
    return bool(re.fullmatch(r"[0-9a-fA-F]{12}", s))


def _wrap_lines_for_width(
    c,
    text: str,
    *,
    font_name: str,
    font_size: float,
    max_width: float,
    max_lines: int,
) -> list[str]:
    """Quebra texto em linhas que cabem em ``max_width`` (medido com a fonte já activa)."""
    text = (text or "").strip()
    if not text:
        return []
    c.setFont(font_name, font_size)
    if c.stringWidth(text, font_name, font_size) <= max_width:
        return [text]
    lines: list[str] = []
    current = ""
    for ch in text:
        trial = current + ch
        if c.stringWidth(trial, font_name, font_size) <= max_width:
            current = trial
            continue
        if current:
            lines.append(current)
            current = ch
        else:
            lines.append(ch)
            current = ""
        if len(lines) >= max_lines:
            break
    if len(lines) < max_lines and current:
        lines.append(current)
    elif current and lines:
        last = lines[-1].rstrip()
        if len(last) > 4:
            lines[-1] = last[:-3].rstrip() + "…"
        else:
            lines[-1] = (last + "…")[: max_width // max(font_size, 1)]
    return lines


def _build_label_overlay_pdf(
    width_pt: float,
    height_pt: float,
    pos: SignaturePositionNormalizada,
    *,
    signer_name: str,
    verification_url: str,
    code_short: str,
) -> bytes:
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width_pt, height_pt))

    llx = pos.box_x * width_pt
    lly = (1.0 - pos.box_y - pos.box_h) * height_pt
    ww = pos.box_w * width_pt
    hh = pos.box_h * height_pt

    pad = min(ww, hh) * 0.06
    inner_w = ww - 2 * pad
    inner_h = hh - 2 * pad

    c.setFillColor(colors.HexColor("#0b2b4a"))
    c.setStrokeColor(colors.HexColor("#1a4a7a"))
    c.setLineWidth(0.5)
    path = c.beginPath()
    r = min(3.5, ww * 0.04)
    path.roundRect(llx, lly, ww, hh, r)
    c.drawPath(path, fill=1, stroke=1)

    c.setFillColor(colors.white)
    title = "DOCUMENTO ASSINADO ELETRONICAMENTE"
    fs_title = max(6.0, min(9.0, hh * 0.11))
    fs_body = max(5.0, min(7.5, hh * 0.095))
    fs_meta = max(4.5, min(6.5, hh * 0.082))
    c.setFont("Helvetica-Bold", fs_title)
    c.drawString(llx + pad, lly + hh - pad - fs_title - 1, title)

    c.setFont("Helvetica", fs_body)
    name = (signer_name or "—")[:64]
    c.drawString(llx + pad, lly + hh - pad - fs_title - fs_body - 4, name)

    qr_size = min(inner_h - 18, inner_w * 0.28, 52)
    if pos.qr and qr_size > 14:
        qr_reserved = qr_size + pad * 1.5
    else:
        qr_reserved = pad

    url_max_w = max(inner_w - qr_reserved, inner_w * 0.45)
    reserved_top = lly + hh - pad - fs_title - fs_body - 8
    url_heading = "Validação (URL):" if "verificar" in (verification_url or "").lower() else "Documento (URL):"
    y_meta = lly + pad
    c.setFont("Helvetica-Bold", fs_meta * 0.92)
    c.drawString(llx + pad, y_meta, url_heading)
    y_meta += fs_meta * 1.1

    c.setFont("Helvetica", fs_meta)
    url_lines = _wrap_lines_for_width(
        c,
        verification_url,
        font_name="Helvetica",
        font_size=fs_meta,
        max_width=url_max_w,
        max_lines=3,
    )
    for ln in url_lines:
        if y_meta + fs_meta > reserved_top:
            break
        c.drawString(llx + pad, y_meta, ln)
        y_meta += fs_meta + 1.2

    code_line = ""
    cs = (code_short or "").strip()
    if cs and not _looks_like_sha256_prefix(cs):
        code_line = f"Código: {cs[:48]}{'…' if len(cs) > 48 else ''}"

    if code_line and y_meta + fs_meta + 2 <= reserved_top:
        c.drawString(llx + pad, y_meta + 2, code_line)

    if pos.qr and qr_size > 14:
        try:
            import qrcode
            from reportlab.lib.utils import ImageReader

            qr = qrcode.QRCode(version=None, box_size=2, border=0)
            qr.add_data(verification_url[:2048])
            qr.make(fit=True)
            pil = qr.make_image(fill_color="black", back_color="white")
            bio = io.BytesIO()
            pil.save(bio, format="PNG")
            bio.seek(0)
            qx = llx + ww - pad - qr_size
            qy = lly + pad
            c.drawImage(ImageReader(bio), qx, qy, width=qr_size, height=qr_size, mask="auto")
        except Exception:
            logger.debug("QR da etiqueta omitido (dependência ou dados).", exc_info=True)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def aplicar_etiqueta_assinatura_pdf(
    pdf_bytes: bytes,
    pos: SignaturePositionNormalizada,
    *,
    signer_name: str,
    verification_url: str,
    code_short: str,
) -> tuple[bytes, dict[str, Any]]:
    """
    Incorpora a etiqueta como conteúdo gráfico na página indicada.
    Retorna PDF em bytes e metadados para auditoria.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    n = len(reader.pages)
    if n == 0:
        return pdf_bytes, {"stamp": "skipped", "reason": "no_pages"}
    idx = max(0, min(n - 1, pos.page_index))
    page = reader.pages[idx]
    w_pt, h_pt = _page_dimensions_pt(page)
    overlay_pdf = _build_label_overlay_pdf(
        w_pt,
        h_pt,
        pos,
        signer_name=signer_name,
        verification_url=verification_url,
        code_short=code_short,
    )
    overlay_reader = PdfReader(io.BytesIO(overlay_pdf))
    overlay_page = overlay_reader.pages[0]
    page.merge_page(overlay_page)

    writer = PdfWriter()
    for i, p in enumerate(reader.pages):
        writer.add_page(p)
    out = io.BytesIO()
    writer.write(out)
    merged = out.getvalue()
    meta = {
        "stamp": "label_overlay",
        "signature_position": pos.to_audit_dict(),
    }
    return merged, meta
