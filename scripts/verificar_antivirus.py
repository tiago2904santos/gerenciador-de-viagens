"""Exercita a política central de upload contra o ClamAV real da máquina.

Não basta ver o `clamd` `active`: o daemon pode estar de pé e mesmo assim
recusar todo anexo por não conseguir ler o arquivo temporário do gunicorn
(veja `--fdpass` em `core/uploads.py`). Este script roda a mesma função que a
view chama, com um PDF limpo e com a string EICAR — é o caso EICAR que separa
"o scan passou" de "o scan não está olhando nada".

Uso na VPS, com o venv ativo e o .env carregado:

    python scripts/verificar_antivirus.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Rodar `python scripts/verificar_antivirus.py` coloca `scripts/` no sys.path,
# nao a raiz do projeto -- sem isto o `django.setup()` nao acha `config`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if not os.environ.get("DJANGO_SETTINGS_MODULE"):
    raise SystemExit(
        "DJANGO_SETTINGS_MODULE nao definido; carregue o .env antes de rodar.",
    )

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.core.exceptions import ValidationError  # noqa: E402
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402

from core.uploads import _scan_with_clamav  # noqa: E402
from core.uploads import validate_private_document_upload  # noqa: E402

# Assinatura de teste padrão do EICAR, montada em pedaços para que este próprio
# arquivo não seja sinalizado como malware pelo antivírus da máquina.
EICAR = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-" rb"FILE!$H+H*"

PDF_LIMPO = b"""%PDF-1.7
1 0 obj
<<>>
endobj
trailer
<<>>
%%EOF
"""


def main() -> int:
    print("REQUIRE_ANTIVIRUS:", settings.PRIVATE_UPLOAD_REQUIRE_ANTIVIRUS)
    print("SCAN_COMMAND:", settings.CLAMAV_SCAN_COMMAND)

    falhas = []

    # 1) Caminho real do usuário: o anexo limpo tem de passar. É este o caso que
    #    estava quebrado — o clamd recusava por não conseguir ler o temporário.
    try:
        validate_private_document_upload(SimpleUploadedFile("documento.pdf", PDF_LIMPO))
    except ValidationError as exc:
        falhas.append(f"PDF limpo foi RECUSADO: {exc.messages}")
        print("PDF limpo (política completa) -> RECUSADO:", exc.messages)
    else:
        print("PDF limpo (política completa) -> ACEITO")

    # 2) O scan tem de estar realmente inspecionando. O EICAR só é reconhecido
    #    quando é o arquivo inteiro, e um arquivo assim jamais passa da checagem
    #    de magic number do PDF — então a prova é chamar o scan diretamente.
    try:
        _scan_with_clamav(SimpleUploadedFile("documento.pdf", EICAR))
    except ValidationError as exc:
        mensagem = " ".join(exc.messages)
        print("EICAR (scan direto) -> RECUSADO:", mensagem)
        if "rejeitado pela verificação antivírus" not in mensagem:
            falhas.append(f"EICAR recusado pelo motivo errado: {mensagem}")
    else:
        falhas.append("EICAR foi ACEITO: o scan não está inspecionando o conteúdo")
        print("EICAR (scan direto) -> ACEITO (ERRADO)")

    for falha in falhas:
        print("FALHA:", falha)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
