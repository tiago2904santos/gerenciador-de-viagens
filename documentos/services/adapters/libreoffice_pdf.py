from __future__ import annotations

import socket
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests


def convert_docx_to_pdf_libreoffice(*, docx_bytes: bytes, libreoffice_binary: str) -> bytes:
    """
    Converte DOCX em PDF via LibreOffice em modo headless (sem unoserver).
    """
    with tempfile.TemporaryDirectory() as tmp:
        tdir = Path(tmp)
        docx_path = tdir / "entrada.docx"
        docx_path.write_bytes(docx_bytes)
        subprocess.run(
            [
                libreoffice_binary,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(tdir),
                str(docx_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        pdf_path = tdir / "entrada.pdf"
        if not pdf_path.exists():
            raise RuntimeError("LibreOffice não gerou o arquivo PDF esperado.")
        return pdf_path.read_bytes()


def unoserver_healthcheck(base_url: str, *, timeout: float = 3) -> bool:
    """Verifica se a porta do unoserver aceita conexão (rápido, sem corpo HTTP)."""
    try:
        u = urlparse(base_url)
        if not u.hostname:
            return False
        port = u.port or 2004
        with socket.create_connection((u.hostname, port), timeout=timeout):
            return True
    except OSError:
        return False


def convert_docx_to_pdf_unoserver(
    *,
    docx_bytes: bytes,
    unoserver_url: str,
    timeout_seconds: float = 3,
) -> bytes:
    """
    Converte DOCX → PDF via unoserver HTTP (POST /request com ficheiro).
    Tenta nomes de campo comuns (`upload`, `file`) por compatibilidade.
    """
    base = unoserver_url.rstrip("/")
    url = f"{base}/request"
    last_err: Exception | None = None
    for field in ("upload", "file"):
        try:
            r = requests.post(
                url,
                files={field: ("documento.docx", docx_bytes)},
                timeout=timeout_seconds,
            )
            if r.status_code != 200:
                last_err = RuntimeError(f"unoserver HTTP {r.status_code}")
                continue
            data = r.content
            if len(data) > 4 and data[:4] == b"%PDF":
                return data
            last_err = RuntimeError("Resposta unoserver não é PDF")
        except requests.RequestException as exc:
            last_err = exc
            continue
    raise RuntimeError(f"unoserver indisponível ou resposta inválida: {last_err}")
