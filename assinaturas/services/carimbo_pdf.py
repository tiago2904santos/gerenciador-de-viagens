from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from django.utils import timezone
from pypdf import PdfReader
from pypdf import PdfWriter
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.lib.colors import white
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from assinaturas.services.hash import calcular_sha256_bytes

SIGNATURE_LABEL_WIDTH_PT = 155
SIGNATURE_LABEL_HEIGHT_PT = 54
SIGNATURE_LABEL_QR_PT = 42
SIGNATURE_LABEL_WATERMARK_ALPHA = 0.18
SIGNATURE_LABEL_MIN_BOTTOM_PT = 72

SIGNATURE_LABEL_BG_HEX = "#08172a"
SIGNATURE_LABEL_FG_HEX = "#f8fafc"
SIGNATURE_LABEL_FONT_TITLE = "Times-Bold"
SIGNATURE_LABEL_FONT_BODY = "Times-Roman"

SISTEMA_ASSINATURA = "Central de Viagens"


@dataclass(frozen=True)
class DadosCarimbo:
    nome_assinante: str
    cpf_mascarado: str
    data_hora_assinatura: datetime
    codigo_verificacao: str
    url_validacao: str
    cargo_assinante: str = ""
    documento_label: str = ""
    hash_curto: str = ""
    organizacao_label: str = "Central de Viagens - PCPR"


@dataclass(frozen=True)
class AparenciaAssinaturaLayout:
    width: float
    height: float
    padding: float
    logo_box: tuple[float, float, float, float]
    text_box: tuple[float, float, float, float]
    qr_box: tuple[float, float, float, float]


def _resolve_cv_watermark_path() -> Path | None:
    try:
        from django.conf import settings

        base = Path(settings.BASE_DIR)
    except Exception:  # noqa: BLE001 — fora do Django
        base = Path(__file__).resolve().parents[2]
    path = base / "static" / "img" / "assinatura" / "cv-watermark.png"
    return path if path.exists() else None


def _normalizar_posicao(posicao: dict | None, total_paginas: int) -> dict[str, Any]:
    raw = posicao or {}
    if total_paginas < 1:
        return {
            "page_index": 0,
            "box_x": 0.37,
            "box_y": 0.8,
            "box_w": 0.269,
            "box_h": 0.067,
            "qr": True,
        }
    page_index = int(raw.get("page_index", raw.get("pagina", total_paginas - 1)) or 0)
    if page_index < 0:
        page_index = total_paginas - 1
    page_index = min(max(page_index, 0), total_paginas - 1)
    box_w = min(max(float(raw.get("box_w", raw.get("sig_w", 0.269))), 0.20), 0.40)
    default_box_x = (1 - box_w) / 2
    return {
        "page_index": page_index,
        "box_x": min(max(float(raw.get("box_x", raw.get("sig_x", default_box_x))), 0.01), 0.95),
        "box_y": min(max(float(raw.get("box_y", raw.get("sig_y", 0.80))), 0.01), 0.95),
        "box_w": box_w,
        "box_h": min(max(float(raw.get("box_h", raw.get("sig_h", 0.067))), 0.05), 0.12),
        "qr": bool(raw.get("qr", True)),
    }


def _coerce_signature_label_size(width: float, height: float) -> tuple[float, float]:
    _ = width, height
    return SIGNATURE_LABEL_WIDTH_PT, SIGNATURE_LABEL_HEIGHT_PT


def _calcular_layout_aparencia(width: float, height: float) -> AparenciaAssinaturaLayout:
    width, height = _coerce_signature_label_size(width, height)
    padding = 6.0
    qr_size = min(SIGNATURE_LABEL_QR_PT, height - padding * 2)
    qr_box = (padding, (height - qr_size) / 2, qr_size, qr_size)
    text_left = qr_box[0] + qr_size + 7
    text_right = width - 6
    text_box = (text_left, padding, max(1.0, text_right - text_left), height - padding * 2)
    return AparenciaAssinaturaLayout(
        width=width,
        height=height,
        padding=padding,
        logo_box=(0.0, 0.0, 0.0, 0.0),
        text_box=text_box,
        qr_box=qr_box,
    )


def _font_size_to_fit(text: str, font_name: str, max_width: float, candidates: tuple[float, ...]) -> float:
    for font_size in candidates:
        if pdfmetrics.stringWidth(str(text or ""), font_name, font_size) <= max_width:
            return font_size
    return candidates[-1]


def _display_validation_url(raw_url: str) -> str:
    raw_url = str(raw_url or "").strip()
    parsed = urlparse(raw_url)
    display = parsed.path or raw_url
    if parsed.query:
        display = f"{display}?{parsed.query}"
    return display or raw_url


def _ellipsize_to_width(text: str, font_name: str, font_size: float, max_width: float) -> str:
    text = str(text or "")
    if pdfmetrics.stringWidth(text, font_name, font_size) <= max_width:
        return text
    for end in range(len(text), 0, -1):
        candidate = f"{text[:end].rstrip()}..."
        if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
            return candidate
    return "..."


def _validation_link_text(raw_url: str, font_name: str, font_size: float, max_width: float) -> str:
    prefix = "verifique em "
    display = _display_validation_url(raw_url).rstrip("/")
    text = f"{prefix}{display}"
    if pdfmetrics.stringWidth(text, font_name, font_size) <= max_width:
        return text
    marker = "/assinaturas/verificar/"
    if display.startswith(marker):
        token = display[len(marker) :].strip("/")
        base = f"{prefix}{marker}"
        for end in range(len(token), 4, -1):
            candidate = f"{base}{token[:end]}..."
            if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
                return candidate
    return _ellipsize_to_width(text, font_name, font_size, max_width)


def _draw_cv_watermark(c: canvas.Canvas, text_left: float, width: float, height: float) -> None:
    wm_size = 165.0
    wm_left = text_left - 23
    wm_bottom = -69.0
    c.saveState()
    clip = c.beginPath()
    clip.rect(text_left, 0, width - text_left, height)
    c.clipPath(clip, stroke=0, fill=0)
    try:
        c.setFillAlpha(SIGNATURE_LABEL_WATERMARK_ALPHA)
        c.setStrokeAlpha(SIGNATURE_LABEL_WATERMARK_ALPHA)
    except AttributeError:
        pass
    wm_path = _resolve_cv_watermark_path()
    if wm_path:
        try:
            c.drawImage(
                ImageReader(str(wm_path)),
                wm_left,
                wm_bottom,
                width=wm_size,
                height=wm_size,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )
        except Exception:  # noqa: BLE001 — fallback silencioso
            pass
    c.restoreState()


def _draw_qrcode_profissional(c: canvas.Canvas, box: tuple[float, float, float, float], url_validacao: str) -> None:
    left, bottom, width, height = box
    qr_size = min(width, height)
    c.saveState()
    qr_code = qr.QrCodeWidget(url_validacao or "assinatura")
    qr_code.barBorder = 1
    qr_code.barFillColor = white
    qr_code.barStrokeColor = white
    bounds = qr_code.getBounds()
    scale = qr_size / max(bounds[2] - bounds[0], bounds[3] - bounds[1], 1)
    drawing = Drawing(qr_size, qr_size, transform=[scale, 0, 0, scale, 0, 0])
    drawing.add(qr_code)
    renderPDF.draw(drawing, c, left, bottom)
    c.restoreState()


def _format_data_hora_br(dt: datetime) -> str:
    if timezone.is_aware(dt):
        loc = timezone.localtime(dt)
    else:
        loc = timezone.make_aware(dt, timezone.get_default_timezone())
    s = loc.strftime("%d/%m/%Y %H:%M:%S%z")
    if s.endswith("-0300") or s.endswith("-0200") or s.endswith("-0400"):
        return s
    return loc.strftime("%d/%m/%Y %H:%M:%S") + "-0300"


def _draw_signature_stamp_content(
    c: canvas.Canvas,
    dados_carimbo: DadosCarimbo,
    width: float,
    height: float,
    *,
    with_qr: bool = True,
) -> None:
    width, height = _coerce_signature_label_size(width, height)
    layout = _calcular_layout_aparencia(width, height)
    padding = layout.padding

    c.setFillColor(HexColor(SIGNATURE_LABEL_BG_HEX))
    c.roundRect(0, 0, width, height, 5, stroke=0, fill=1)

    text_left, _tb, text_width, _th = layout.text_box
    _draw_cv_watermark(c, text_left, width, height)

    if with_qr and dados_carimbo.url_validacao:
        _draw_qrcode_profissional(c, layout.qr_box, dados_carimbo.url_validacao)

    data_formatada = _format_data_hora_br(dados_carimbo.data_hora_assinatura)

    title = "Documento assinado eletronicamente"
    title_size = _font_size_to_fit(title, SIGNATURE_LABEL_FONT_TITLE, text_width, (5.8, 5.6, 5.4))
    y = height - 11
    c.setFillColor(HexColor(SIGNATURE_LABEL_FG_HEX))
    c.setFont(SIGNATURE_LABEL_FONT_TITLE, title_size)
    c.drawString(text_left, y, title)
    y -= 11

    name_size = _font_size_to_fit(
        dados_carimbo.nome_assinante,
        SIGNATURE_LABEL_FONT_BODY,
        text_width,
        (5.2, 5.0, 4.8, 4.6),
    )
    linhas = [
        (dados_carimbo.nome_assinante, name_size),
        (f"CPF: {dados_carimbo.cpf_mascarado}", 5.2),
        (f"Data: {data_formatada}", 5.0),
        (f"Codigo: {dados_carimbo.codigo_verificacao}", 4.8),
    ]
    for line, font_size in linhas:
        c.setFont(SIGNATURE_LABEL_FONT_BODY, font_size)
        c.drawString(text_left, y, _ellipsize_to_width(line, SIGNATURE_LABEL_FONT_BODY, font_size, text_width))
        y -= 8

    link_size = 4.2
    if dados_carimbo.url_validacao:
        link_linha = _validation_link_text(
            dados_carimbo.url_validacao,
            SIGNATURE_LABEL_FONT_BODY,
            link_size,
            text_width,
        )
    else:
        link_linha = _ellipsize_to_width(
            dados_carimbo.organizacao_label,
            SIGNATURE_LABEL_FONT_BODY,
            link_size,
            text_width,
        )
    c.setFont(SIGNATURE_LABEL_FONT_BODY, link_size)
    c.drawString(text_left, y, link_linha)
    _ = padding  # reservado para alinhamentos futuros


def renderizar_aparencia_assinatura(dados_carimbo: DadosCarimbo, width: float, height: float) -> bytes:
    width, height = _coerce_signature_label_size(width, height)
    stream = io.BytesIO()
    c = canvas.Canvas(stream, pagesize=(width, height), pageCompression=1)
    _draw_signature_stamp_content(c, dados_carimbo, width, height, with_qr=True)
    c.save()
    return stream.getvalue()


def calculate_signature_stamp_box(page_width: float, page_height: float, posicao: dict) -> tuple[float, float, float, float]:
    box_w = SIGNATURE_LABEL_WIDTH_PT
    box_h = SIGNATURE_LABEL_HEIGHT_PT
    left = page_width * float(posicao.get("box_x", 0.37))
    bottom = page_height - (page_height * posicao["box_y"]) - box_h
    left = min(max(left, 8.0), page_width - box_w - 8.0)
    bottom = min(max(bottom, SIGNATURE_LABEL_MIN_BOTTOM_PT), page_height - box_h - 8.0)
    return left, bottom, box_w, box_h


def get_signature_stamp_position(page_width: float, page_height: float, posicao: dict) -> dict[str, float]:
    left, bottom, box_w, box_h = calculate_signature_stamp_box(page_width, page_height, posicao)
    return {"left": left, "bottom": bottom, "box_w": box_w, "box_h": box_h}


def draw_signature_stamp(
    c: canvas.Canvas,
    dados_carimbo: DadosCarimbo,
    stamp_pos: dict[str, float],
    with_qr: bool,
) -> None:
    left = stamp_pos["left"]
    bottom = stamp_pos["bottom"]
    box_w = stamp_pos["box_w"]
    box_h = stamp_pos["box_h"]
    c.saveState()
    c.translate(left, bottom)
    _draw_signature_stamp_content(c, dados_carimbo, box_w, box_h, with_qr=with_qr)
    c.restoreState()


def gerar_overlay_carimbo(
    page_width: float,
    page_height: float,
    dados_carimbo: DadosCarimbo,
    posicao: dict[str, Any],
) -> bytes:
    stream = io.BytesIO()
    c = canvas.Canvas(stream, pagesize=(page_width, page_height))
    stamp_pos = get_signature_stamp_position(page_width, page_height, posicao)
    draw_signature_stamp(c, dados_carimbo, stamp_pos, with_qr=bool(posicao.get("qr")))
    c.save()
    return stream.getvalue()


def _pdf_bytes_com_metadados_assinatura(pdf_bytes: bytes, dados_carimbo: DadosCarimbo, digest: str) -> bytes:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    writer.add_metadata(
        {
            "/assinatura_codigo": dados_carimbo.codigo_verificacao,
            "/assinatura_sistema": SISTEMA_ASSINATURA,
            "/assinatura_data_hora": dados_carimbo.data_hora_assinatura.isoformat(),
            "/assinatura_hash_pdf_assinado": digest,
        }
    )
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def aplicar_carimbo_pdf(
    pdf_original: bytes,
    dados_carimbo: DadosCarimbo,
    posicao: dict | None = None,
) -> tuple[bytes, dict[str, Any]]:
    reader = PdfReader(io.BytesIO(pdf_original))
    if not reader.pages:
        raise ValueError("PDF sem páginas: não é possível aplicar o carimbo de assinatura.")

    posicao_final = _normalizar_posicao(posicao, len(reader.pages))
    target_index = int(posicao_final["page_index"])
    target_page = reader.pages[target_index]
    page_w = float(target_page.mediabox.width)
    page_h = float(target_page.mediabox.height)
    overlay_bytes = gerar_overlay_carimbo(page_w, page_h, dados_carimbo, posicao_final)
    overlay_page = PdfReader(io.BytesIO(overlay_bytes)).pages[0]

    writer = PdfWriter()
    for index, page in enumerate(reader.pages):
        if index == target_index:
            page.merge_page(overlay_page)
        writer.add_page(page)

    buf = io.BytesIO()
    writer.write(buf)
    merged_sem_meta_digest = calcular_sha256_bytes(buf.getvalue())
    final_bytes = _pdf_bytes_com_metadados_assinatura(buf.getvalue(), dados_carimbo, merged_sem_meta_digest)

    position_meta: dict[str, Any] = {
        **posicao_final,
        "page_number": target_index + 1,
        "label_width_pt": SIGNATURE_LABEL_WIDTH_PT,
        "label_height_pt": SIGNATURE_LABEL_HEIGHT_PT,
        "qr_size_pt": SIGNATURE_LABEL_QR_PT,
    }
    return final_bytes, position_meta
