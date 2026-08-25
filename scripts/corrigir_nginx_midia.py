"""Aplica na VPS o bloco de midia privada que o DEPLOY_VPS.md documenta.

A config de producao ficou na versao anterior a auditoria de 2026-07-27:

    location /media/ {
        alias /var/www/gerenciador-viagens/media/;
    }

Isso causa dois defeitos ao mesmo tempo. Falta `location /_protected_media/`,
entao o `X-Accel-Redirect` emitido por `core.private_media` nao encontra destino
no nginx, cai na regra padrao, volta para o Django e vira 404 -- todo arquivo
privado da "not found". E sobra `/media/` aberto, entao qualquer pessoa com a
URL baixa oficio, termo, diario ou assinatura sem passar por login nem por area.

Este script e idempotente: se `_protected_media` ja existir, nao faz nada.
Nao recarrega o nginx -- quem chama testa com `nginx -t` antes do reload.

Codigos de saida:
    0  aplicado, ou ja estava aplicado
    2  config divergente do esperado; nada foi tocado
"""

from __future__ import annotations

import shutil
import sys
import time

CAMINHO = "/etc/nginx/sites-enabled/gerenciador-viagens"

ANTIGO = """    location /media/ {
        alias /var/www/gerenciador-viagens/media/;
    }
"""

NOVO = """    # Nunca exponha /media/ diretamente. O Django autoriza o usuario/area e,
    # depois disso, delega a transferencia ao Nginx por X-Accel-Redirect.
    location /_protected_media/ {
        internal;
        alias /var/www/gerenciador-viagens/media/;
    }

    location /media/ {
        return 404;
    }
"""


def main() -> int:
    conteudo = open(CAMINHO, encoding="utf-8").read()

    if "location /_protected_media/" in conteudo:
        print("JA APLICADO: _protected_media ja existe; nada a fazer")
        return 0

    if ANTIGO not in conteudo:
        print("ABORTADO: bloco /media/ esperado nao encontrado; config divergente")
        return 2

    backup = "{}.bak-{}".format(CAMINHO, time.strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(CAMINHO, backup)
    print("backup:", backup)

    open(CAMINHO, "w", encoding="utf-8").write(conteudo.replace(ANTIGO, NOVO))
    print("config reescrita")
    return 0


if __name__ == "__main__":
    sys.exit(main())
