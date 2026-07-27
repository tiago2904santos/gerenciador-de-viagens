from __future__ import annotations

import os
import socket
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

# Invocações concorrentes de `soffice` sem perfil isolado disputam o lock do
# perfil de utilizador padrão (~/.config/libreoffice/.../.lock): uma delas
# falha ou bloqueia indefinidamente. `-env:UserInstallation` isola cada
# chamada no seu próprio diretório temporário, eliminando essa disputa.
_LIBREOFFICE_TIMEOUT_SECONDS = 90


def _headless_subprocess_kwargs() -> dict[str, int]:
    if os.name != "nt":
        return {}
    return {"creationflags": int(getattr(subprocess, "CREATE_NO_WINDOW", 0))}


def _convert_via_libreoffice(*, input_bytes: bytes, filename: str, libreoffice_binary: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        tdir = Path(tmp)
        input_path = tdir / filename
        input_path.write_bytes(input_bytes)
        profile_dir = tdir / "profile"
        profile_dir.mkdir()
        try:
            subprocess.run(
                [
                    libreoffice_binary,
                    f"-env:UserInstallation={profile_dir.as_uri()}",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(tdir),
                    str(input_path),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=_LIBREOFFICE_TIMEOUT_SECONDS,
                **_headless_subprocess_kwargs(),
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"LibreOffice não respondeu em {_LIBREOFFICE_TIMEOUT_SECONDS}s (possível disputa de conversões concorrentes)."
            ) from exc
        pdf_path = tdir / f"{input_path.stem}.pdf"
        if not pdf_path.exists():
            raise RuntimeError("LibreOffice não gerou o arquivo PDF esperado.")
        return pdf_path.read_bytes()


def convert_docx_to_pdf_libreoffice(*, docx_bytes: bytes, libreoffice_binary: str) -> bytes:
    """
    Converte DOCX em PDF via LibreOffice em modo headless (sem unoserver).
    """
    return _convert_via_libreoffice(
        input_bytes=docx_bytes,
        filename="entrada.docx",
        libreoffice_binary=libreoffice_binary,
    )


def convert_xlsx_to_pdf_libreoffice(*, xlsx_bytes: bytes, libreoffice_binary: str) -> bytes:
    """Converte XLSX em PDF via LibreOffice em modo headless (sem unoserver)."""
    return _convert_via_libreoffice(
        input_bytes=xlsx_bytes,
        filename="entrada.xlsx",
        libreoffice_binary=libreoffice_binary,
    )


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
    """Converte DOCX → PDF pelo cliente XML-RPC oficial do unoserver."""
    return _convert_via_unoserver(
        data=docx_bytes,
        filename="documento.docx",
        unoserver_url=unoserver_url,
        timeout_seconds=timeout_seconds,
    )


def convert_xlsx_to_pdf_unoserver(
    *,
    xlsx_bytes: bytes,
    unoserver_url: str,
    timeout_seconds: float = 3,
) -> bytes:
    """Converte XLSX → PDF pelo cliente XML-RPC oficial do unoserver."""
    return _convert_via_unoserver(
        data=xlsx_bytes,
        filename="documento.xlsx",
        unoserver_url=unoserver_url,
        timeout_seconds=timeout_seconds,
    )


def _convert_via_unoserver(
    *,
    data: bytes,
    filename: str,
    unoserver_url: str,
    timeout_seconds: float = 3,
) -> bytes:
    """Converte pelo protocolo XML-RPC nativo do ``unoserver``.

    A porta 2003 do unoserver não é uma API REST. O cliente oficial envia os
    bytes via XML-RPC e reutiliza o processo LibreOffice já residente.
    """
    parsed = urlparse(unoserver_url)
    host = parsed.hostname
    if not host:
        raise RuntimeError("DOCUMENTOS_UNOSERVER_URL não possui host válido.")
    port = parsed.port or 2003
    protocol = (parsed.scheme or "http").lower()
    if protocol not in ("http", "https"):
        raise RuntimeError("DOCUMENTOS_UNOSERVER_URL deve usar http:// ou https://.")

    # Falha rápida. O limite da conversão também deve ser configurado no
    # servidor com ``unoserver --conversion-timeout``.
    if not unoserver_healthcheck(unoserver_url, timeout=timeout_seconds):
        raise RuntimeError("unoserver indisponível.")

    try:
        from unoserver.client import UnoClient
    except ImportError as exc:
        raise RuntimeError(
            "Cliente unoserver não instalado. Instale as dependências do projeto."
        ) from exc

    try:
        local_server = host.lower() in {"127.0.0.1", "localhost", "::1"}
        client = UnoClient(
            server=host,
            port=str(port),
            host_location="local" if local_server else "remote",
            protocol=protocol,
        )
        if local_server:
            # No mesmo host, caminhos evitam o custo do base64/XML-RPC e também
            # a limitação de NamedTemporaryFile do unoserver no Windows.
            with tempfile.TemporaryDirectory(prefix="cv3_unoserver_") as tmp:
                input_path = Path(tmp) / filename
                output_path = Path(tmp) / "documento.pdf"
                input_path.write_bytes(data)
                client.convert(
                    inpath=str(input_path),
                    outpath=str(output_path),
                    update_index=False,
                )
                resposta = output_path.read_bytes()
        else:
            resposta = client.convert(
                indata=data,
                convert_to="pdf",
                update_index=False,
            )
    except Exception as exc:
        raise RuntimeError(f"unoserver falhou ao converter {filename}: {exc}") from exc

    if not isinstance(resposta, bytes) or not resposta.startswith(b"%PDF"):
        raise RuntimeError("Resposta unoserver não é um PDF válido.")
    return resposta
