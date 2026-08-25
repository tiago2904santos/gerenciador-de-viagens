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

import os
import shutil
import sys
import time

CAMINHO = "/etc/nginx/sites-enabled/gerenciador-viagens"

# O backup NAO pode morar em sites-enabled: o nginx inclui `sites-enabled/*`,
# entao um arquivo .bak ali vira um segundo server block com os mesmos nomes.
# O sintoma e traicoeiro -- `nginx -t` passa, so avisa "conflicting server name",
# e a config antiga continua atendendo. Custou uma rodada errada nesta sessao.
DIR_BACKUP = "/etc/nginx/backups-midia"

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


def limpar_backups_em_sites_enabled() -> None:
    """Tira de `sites-enabled` qualquer .bak que esteja sendo lido como config."""
    diretorio = os.path.dirname(CAMINHO)
    os.makedirs(DIR_BACKUP, exist_ok=True)
    for nome in sorted(os.listdir(diretorio)):
        if ".bak-" not in nome:
            continue
        origem = os.path.join(diretorio, nome)
        destino = os.path.join(DIR_BACKUP, nome)
        shutil.move(origem, destino)
        print("backup movido para fora de sites-enabled:", destino)


def main() -> int:
    limpar_backups_em_sites_enabled()

    conteudo = open(CAMINHO, encoding="utf-8").read()

    if "location /_protected_media/" in conteudo:
        print("JA APLICADO: _protected_media ja existe; nada a fazer")
        return 0

    if ANTIGO not in conteudo:
        print("ABORTADO: bloco /media/ esperado nao encontrado; config divergente")
        return 2

    os.makedirs(DIR_BACKUP, exist_ok=True)
    backup = os.path.join(
        DIR_BACKUP,
        "gerenciador-viagens.bak-{}".format(time.strftime("%Y%m%d-%H%M%S")),
    )
    shutil.copy2(CAMINHO, backup)
    print("backup:", backup)

    open(CAMINHO, "w", encoding="utf-8").write(conteudo.replace(ANTIGO, NOVO))
    print("config reescrita")
    return 0


if __name__ == "__main__":
    sys.exit(main())
