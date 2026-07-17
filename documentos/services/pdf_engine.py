"""
Resolução do motor PDF (inclui modo `auto` por sistema operativo).

Não executa conversões — apenas decide a cadeia de tentativas e mensagens de apoio.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass

from django.conf import settings

from documentos.services.adapters.libreoffice_pdf import unoserver_healthcheck
from documentos.services.adapters.word_pdf import is_word_pdf_available
from documentos.services.libreoffice_resolve import resolve_libreoffice_binary
from documentos.services.libreoffice_resolve import sys_platform_is_darwin
from documentos.services.libreoffice_resolve import sys_platform_is_linux


@dataclass(frozen=True)
class PdfEngineResolution:
    """Resultado da resolução: ordem de tentativa e metadados para diagnóstico/erros."""

    attempt_chain: tuple[str, ...]
    reason: str
    available_engines: tuple[str, ...] = ()
    missing_engines: tuple[str, ...] = ()
    install_hints: tuple[str, ...] = ()


def _os_label() -> str:
    s = platform.system().lower()
    if s == "darwin":
        return "macos"
    if s == "windows":
        return "windows"
    if s == "linux":
        return "linux"
    return s or "unknown"


def _libreoffice_ok() -> bool:
    # Um executável existente pode pertencer a uma instalação incompleta.
    return bool(resolve_libreoffice_binary(verify_version=True))


def _unoserver_ok() -> bool:
    url = (getattr(settings, "DOCUMENTOS_UNOSERVER_URL", None) or "").strip()
    if not url:
        return False
    timeout = float(getattr(settings, "DOCUMENTOS_UNOSERVER_TIMEOUT_SECONDS", 3) or 3)
    return unoserver_healthcheck(url, timeout=min(timeout, 2.0))


def _word_ok() -> bool:
    return is_word_pdf_available()


def _weasy_import_ok() -> bool:
    """
    No Windows (e noutros SO sem GTK/Pango), `import weasyprint` pode levantar
    `OSError` ao carregar `libgobject` — não só `ImportError`.
    """
    try:
        import weasyprint  # noqa: F401

        return True
    except (ImportError, OSError):
        return False


def _fpdf_ok() -> bool:
    try:
        import fpdf  # noqa: F401

        return True
    except ImportError:
        return False


def _simple_fallback_allowed() -> bool:
    if not _fpdf_ok():
        return False
    if getattr(settings, "DOCUMENTOS_SIMPLE_PDF_FALLBACK", False):
        return True
    if getattr(settings, "DOCUMENTOS_PDF_AUTO_FALLBACK", False) and getattr(settings, "DEBUG", False):
        return True
    return False


def _scan_availability() -> tuple[list[str], list[str]]:
    avail: list[str] = []
    missing: list[str] = []
    for name, ok in (
        ("unoserver", _unoserver_ok()),
        ("word_com", _word_ok()),
        ("libreoffice", _libreoffice_ok()),
        ("weasyprint", _weasy_import_ok()),
        ("simple_fallback", _simple_fallback_allowed()),
    ):
        if ok:
            avail.append(name)
        else:
            missing.append(name)
    return avail, missing


def _auto_chain(*, prefer_docx_pipeline: bool) -> list[str]:
    osys = platform.system()
    if prefer_docx_pipeline:
        if osys == "Windows":
            raw = ["unoserver", "word_com", "libreoffice", "weasyprint", "simple_fallback"]
        elif sys_platform_is_linux():
            raw = ["unoserver", "libreoffice", "weasyprint", "simple_fallback"]
        elif sys_platform_is_darwin():
            raw = ["unoserver", "libreoffice", "weasyprint", "word_com", "simple_fallback"]
        else:
            raw = ["unoserver", "libreoffice", "weasyprint", "simple_fallback"]
    else:
        if osys == "Windows":
            raw = ["unoserver", "word_com", "libreoffice", "weasyprint", "simple_fallback"]
        elif sys_platform_is_linux():
            raw = ["unoserver", "libreoffice", "weasyprint", "simple_fallback"]
        elif sys_platform_is_darwin():
            raw = ["unoserver", "libreoffice", "weasyprint", "word_com", "simple_fallback"]
        else:
            raw = ["unoserver", "libreoffice", "weasyprint", "simple_fallback"]
    return [e for e in raw if _engine_available(e)]


def _engine_available(name: str) -> bool:
    if name == "unoserver":
        return _unoserver_ok()
    if name == "word_com":
        return _word_ok()
    if name == "libreoffice":
        return _libreoffice_ok()
    if name == "weasyprint":
        return _weasy_import_ok()
    if name == "simple_fallback":
        return _simple_fallback_allowed()
    return False


def _explicit_chain(explicit: str, *, auto_fallback: bool) -> list[str]:
    explicit = (explicit or "").strip().lower()
    if explicit == "simple":
        explicit = "simple_fallback"
    if explicit in ("", "auto"):
        return []
    if explicit not in ("word_com", "libreoffice", "weasyprint", "simple_fallback", "unoserver"):
        return []
    out: list[str] = []
    if _engine_available(explicit):
        out.append(explicit)
    elif not auto_fallback:
        return []
    if auto_fallback:
        for e in ("unoserver", "libreoffice", "weasyprint", "word_com", "simple_fallback"):
            if e != explicit and _engine_available(e) and e not in out:
                out.append(e)
    return out


def build_pdf_unavailable_message(resolution: PdfEngineResolution) -> str:
    osn = _os_label()
    hints = "\n".join(f"  - {h}" for h in resolution.install_hints) if resolution.install_hints else ""
    base = (
        "Não foi possível gerar PDF. Nenhum motor PDF disponível na ordem configurada.\n"
        f"Sistema: {osn}\n"
        f"Motores ausentes ou indisponíveis: {', '.join(resolution.missing_engines) or '(n/d)'}\n"
    )
    if hints:
        base += f"Opções:\n{hints}\n"
    base += "  - Diagnóstico: python manage.py documentos_check\n"
    return base.strip()


def _default_install_hints() -> list[str]:
    osn = _os_label()
    hints: list[str] = []
    if osn == "windows":
        hints.append("Instale Microsoft Word e: python -m pip install docx2pdf pywin32")
        hints.append("Ou instale LibreOffice: winget install TheDocumentFoundation.LibreOffice")
        hints.append("Ou defina DOCUMENTOS_DEFAULT_PDF_ENGINE=weasyprint se o GTK estiver configurado.")
    elif osn == "linux":
        hints.append("Instale LibreOffice: sudo apt update && sudo apt install -y libreoffice")
        hints.append("Ou configure DOCUMENTOS_LIBREOFFICE_BINARY=/usr/bin/libreoffice")
    elif osn == "macos":
        hints.append("Instale LibreOffice: brew install --cask libreoffice")
        hints.append(
            "Ou configure DOCUMENTOS_LIBREOFFICE_BINARY=/Applications/LibreOffice.app/Contents/MacOS/soffice"
        )
    return hints


def resolve_pdf_engine(
    *,
    explicit_setting: str | None,
    prefer_docx_pipeline: bool,
) -> PdfEngineResolution:
    """
    Devolve a lista ordenada de motores a tentar.

    `prefer_docx_pipeline` é verdadeiro quando existe `docxtpl_context` plano (ex.: ofício, justificativa).
    """
    explicit = (explicit_setting or "auto").strip().lower()
    auto_fb = bool(getattr(settings, "DOCUMENTOS_PDF_AUTO_FALLBACK", False))
    avail, missing = _scan_availability()

    if explicit == "auto":
        chain = _auto_chain(prefer_docx_pipeline=prefer_docx_pipeline)
        reason = "auto: primeira opção disponível por SO e fidelidade ao DOCX"
    else:
        chain = _explicit_chain(explicit, auto_fallback=auto_fb)
        reason = f"motor explícito: {explicit}" + (" + fallback" if auto_fb else "")

    hints = _default_install_hints()
    if not chain:
        return PdfEngineResolution(
            attempt_chain=(),
            reason=reason,
            available_engines=tuple(avail),
            missing_engines=tuple(missing),
            install_hints=tuple(hints),
        )

    return PdfEngineResolution(
        attempt_chain=tuple(chain),
        reason=reason,
        available_engines=tuple(avail),
        missing_engines=tuple(missing),
        install_hints=tuple(hints),
    )
