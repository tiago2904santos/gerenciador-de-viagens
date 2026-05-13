from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Mapping


def render_docx_bytes(*, template_path: Path, context: Mapping[str, object]) -> bytes:
    try:
        from docxtpl import DocxTemplate
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Pacote 'docxtpl' não instalado no ambiente ativo. "
            "Execute: python -m pip install docxtpl python-docx"
        ) from exc

    tpl = DocxTemplate(str(template_path))
    tpl.render(dict(context))
    buf = BytesIO()
    tpl.save(buf)
    return buf.getvalue()
