"""
Conversão DOCX → PDF via Microsoft Word (Windows / COM apenas).

Não invocar fora de Windows; use `is_word_pdf_available()` antes.
"""

from __future__ import annotations

import logging
import platform
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_WORD_ERR = (
    "Microsoft Word não está disponível para conversão PDF. "
    "Instale o LibreOffice ou configure outro motor PDF."
)


def is_word_pdf_available() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        return False
    word = None
    try:
        import win32com.client

        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        return True
    except Exception:
        return False
    finally:
        if word is not None:
            try:
                word.Quit(SaveChanges=0)
            except Exception:
                pass


def convert_docx_to_pdf_word_com(docx_bytes: bytes) -> bytes:
    if platform.system() != "Windows":
        raise OSError("Conversão via Word COM só é suportada no Windows.")

    try:
        import docx2pdf
    except ImportError:
        docx2pdf = None

    if docx2pdf is not None:
        return _convert_via_docx2pdf(docx_bytes)

    return _convert_via_win32com(docx_bytes)


def _convert_via_docx2pdf(docx_bytes: bytes) -> bytes:
    import docx2pdf

    with tempfile.TemporaryDirectory(prefix="cv3_word_") as tmp:
        in_path = Path(tmp) / "entrada.docx"
        out_path = Path(tmp) / "entrada.pdf"
        in_path.write_bytes(docx_bytes)
        try:
            docx2pdf.convert(str(in_path), str(out_path))
        except Exception as exc:
            logger.warning("docx2pdf.convert falhou: %s", exc, exc_info=True)
            raise RuntimeError(_WORD_ERR) from exc
        if not out_path.is_file():
            raise RuntimeError(_WORD_ERR)
        return out_path.read_bytes()


def _convert_via_win32com(docx_bytes: bytes) -> bytes:
    import pythoncom
    import win32com.client

    wd_format_pdf = 17
    with tempfile.TemporaryDirectory(prefix="cv3_word_") as tmp:
        in_path = Path(tmp) / "entrada.docx"
        out_path = Path(tmp) / "entrada.pdf"
        in_path.write_bytes(docx_bytes)
        pythoncom.CoInitialize()
        word = None
        try:
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            doc = word.Documents.Open(str(in_path), ReadOnly=True)
            try:
                doc.SaveAs(str(out_path), FileFormat=wd_format_pdf)
            finally:
                doc.Close(SaveChanges=0)
        except Exception as exc:
            logger.warning("win32com Word SaveAs PDF falhou: %s", exc, exc_info=True)
            raise RuntimeError(_WORD_ERR) from exc
        finally:
            if word is not None:
                try:
                    word.Quit(SaveChanges=0)
                except Exception:
                    pass
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
        if not out_path.is_file():
            raise RuntimeError(_WORD_ERR)
        return out_path.read_bytes()
