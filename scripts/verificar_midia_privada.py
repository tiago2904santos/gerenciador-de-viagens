"""Prova que um arquivo privado chega ao usuario pelo caminho real, com nginx no meio.

Nao basta ver `location /_protected_media/` no arquivo de config: o
`X-Accel-Redirect` so funciona se o `alias` bater com o `MEDIA_ROOT` e se o
nginx conseguir ler o arquivo. Este script pede o documento pela URL publica,
com um cookie de sessao autenticado, e conta o que voltou.

A sessao criada aqui e temporaria e removida no final, mesmo em caso de erro.

Uso na VPS, com o venv ativo e o .env carregado:

    python scripts/verificar_midia_privada.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if not os.environ.get("DJANGO_SETTINGS_MODULE"):
    raise SystemExit("DJANGO_SETTINGS_MODULE nao definido; carregue o .env antes.")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.sessions.backends.db import SessionStore  # noqa: E402
from django.urls import reverse  # noqa: E402

from eventos.models import EventoDocumentoSolicitacao  # noqa: E402


def host_publico() -> str:
    for host in settings.ALLOWED_HOSTS:
        if host and not host.startswith(".") and host not in {"127.0.0.1", "localhost"}:
            return host
    return "127.0.0.1"


def main() -> int:
    anexo = EventoDocumentoSolicitacao.objects.order_by("-pk").first()
    if anexo is None:
        print("nenhum anexo de solicitacao cadastrado; nada a verificar")
        return 0

    print("anexo pk=%s evento=%s" % (anexo.pk, anexo.evento_id))
    print("arquivo:", repr(anexo.arquivo.name))
    existe = anexo.arquivo.storage.exists(anexo.arquivo.name) if anexo.arquivo.name else False
    print("existe em disco:", existe)

    usuario = get_user_model().objects.filter(is_superuser=True, is_active=True).first()
    if usuario is None:
        print("nenhum superusuario ativo; nao da para autenticar")
        return 1

    sessao = SessionStore()
    sessao["_auth_user_id"] = str(usuario.pk)
    sessao["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
    sessao["_auth_user_hash"] = usuario.get_session_auth_hash()
    sessao.create()

    caminho = reverse(
        "eventos:solicitacao_anexo_conteudo",
        args=[anexo.evento_id, anexo.pk],
    )
    url = "https://%s%s" % (host_publico(), caminho)
    print("GET", caminho)

    try:
        saida = subprocess.run(
            [
                "curl", "-s", "-o", "/tmp/verif-midia.bin",
                "-w", "status=%{http_code} bytes=%{size_download} tipo=%{content_type}",
                "--max-time", "20",
                "--cookie", "%s=%s" % (settings.SESSION_COOKIE_NAME, sessao.session_key),
                url,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        print(saida.stdout.strip() or saida.stderr.strip())
        cabecalho = b""
        try:
            with open("/tmp/verif-midia.bin", "rb") as arquivo:
                cabecalho = arquivo.read(8)
        except OSError:
            pass
        print("primeiros bytes:", cabecalho)
        ok = b"%PDF" in cabecalho and "status=200" in saida.stdout
        print("RESULTADO:", "OK -- PDF entregue" if ok else "FALHOU")
        return 0 if ok else 1
    finally:
        sessao.delete()
        print("sessao temporaria removida")
        try:
            os.remove("/tmp/verif-midia.bin")
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
