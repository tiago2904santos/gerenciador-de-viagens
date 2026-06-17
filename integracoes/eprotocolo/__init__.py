"""Pacote de integração com o eProtocolo (Paraná).

Isola toda a comunicação externa. As views do app ``protocolos`` nunca devem
importar ``client`` diretamente — elas conversam com ``protocolos.services``,
que por sua vez chama ``integracoes.eprotocolo.services``.

Camadas:
    client.py      → transporte HTTP (auth, headers, timeout, erros → exceptions)
    services.py    → funções de alto nível por endpoint
    mappers.py     → documentos internos → payloads do eProtocolo
    schemas.py     → dataclasses/constantes de domínio
    exceptions.py  → hierarquia de erros
    mocks.py       → respostas determinísticas para dev/testes/sem credenciais
    settings.py    → leitura de configuração e helpers (eprotocolo_esta_configurado)
"""
