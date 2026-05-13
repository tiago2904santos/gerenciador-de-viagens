from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO


def calcular_sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def calcular_sha256_arquivo(path_or_file: str | Path | BinaryIO) -> str:
    """
    Aceita caminho (`str`/`Path`) ou objeto ficheiro binário com `read()`.
    """
    if isinstance(path_or_file, (str, Path)):
        data = Path(path_or_file).read_bytes()
    else:
        data = path_or_file.read()
    return calcular_sha256_bytes(data)
