"""Normalização da posição da etiqueta de assinatura (coordenadas 0–1, origem no canto superior esquerdo da página)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class SignaturePositionNormalizada:
    """Caixa da etiqueta em coordenadas normalizadas (origem topo-esquerdo da página)."""

    page_index: int
    box_x: float
    box_y: float
    box_w: float
    box_h: float
    qr: bool = True

    def to_audit_dict(self) -> dict[str, Any]:
        return {
            "page_index": self.page_index,
            "box_x": self.box_x,
            "box_y": self.box_y,
            "box_w": self.box_w,
            "box_h": self.box_h,
            "qr": self.qr,
        }


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def parse_signature_position_from_post(
    post: Mapping[str, Any],
    *,
    num_pages: int,
) -> SignaturePositionNormalizada | None:
    """
    Lê sig_x, sig_y, sig_w, sig_h, sig_page do POST.
    Retorna None se nenhum campo relevante existir (ex.: fluxo antigo sem etiqueta).
    """
    if "sig_x" not in post and "sig_y" not in post:
        return None
    try:
        x = float(post.get("sig_x", 0.58))
        y = float(post.get("sig_y", 0.78))
        w = float(post.get("sig_w", 0.34))
        h = float(post.get("sig_h", 0.11))
        raw_pg = post.get("sig_page", -1)
        pg = int(float(raw_pg)) if str(raw_pg).strip() not in {"", "None"} else -1
    except (TypeError, ValueError):
        return None
    x = _clamp(x, 0.0, 1.0)
    y = _clamp(y, 0.0, 1.0)
    w = _clamp(w, 0.20, 0.95)
    h = _clamp(h, 0.06, 0.22)
    if x + w > 1.0:
        x = max(0.0, 1.0 - w)
    if y + h > 1.0:
        y = max(0.0, 1.0 - h)
    if num_pages < 1:
        num_pages = 1
    if pg == -1:
        idx = num_pages - 1
    else:
        idx = max(0, min(num_pages - 1, pg))
    return SignaturePositionNormalizada(
        page_index=idx,
        box_x=x,
        box_y=y,
        box_w=w,
        box_h=h,
        qr=True,
    )
