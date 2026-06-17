"""Client HTTP do eProtocolo.

Responsável apenas pelo transporte: autenticação (OAuth2 client credentials /
JWT), headers obrigatórios (``Authorization`` + ``consumerId``), timeout,
conversão de status HTTP em exceptions próprias e logging técnico que NUNCA
vaza credenciais.

Os métodos genéricos (``get``/``post``/``put``/``delete``) são usados pelos
services. Quando o ambiente está em modo mock (sem credenciais ou
``EPROTOCOLO_AMBIENTE=mock``), o client não toca a rede — quem decide isso é a
camada de services, mas o client também se protege levantando
``EProtocoloNaoConfiguradoError`` se for chamado sem configuração.
"""

from __future__ import annotations

import logging
import threading
import time

import requests

from . import settings as cfg
from .exceptions import (
    EProtocoloError,
    EProtocoloNaoConfiguradoError,
    EProtocoloTimeoutError,
    EProtocoloUnavailableError,
    excecao_para_status,
)


logger = logging.getLogger("integracoes.eprotocolo")

# Cabeçalhos/campos que jamais devem aparecer em logs.
_CAMPOS_SENSIVEIS = {
    "authorization", "client_secret", "clientsecret", "client_id",
    "consumerid", "consumer_id", "access_token", "token", "senha", "password",
}


def mascarar_dados(valor):
    """Remove/oculta dados sensíveis (token, secret, CPF...) antes de logar/persistir."""
    return _mascarar(valor)


def _mascarar(valor):
    """Remove/oculta dados sensíveis de dicionários antes de logar."""
    if isinstance(valor, dict):
        limpo = {}
        for chave, item in valor.items():
            if str(chave).strip().lower() in _CAMPOS_SENSIVEIS:
                limpo[chave] = "***"
            else:
                limpo[chave] = _mascarar(item)
        return limpo
    if isinstance(valor, (list, tuple)):
        return [_mascarar(item) for item in valor]
    return valor


class _TokenCache:
    """Cache simples de token em memória, thread-safe, com expiração."""

    def __init__(self):
        self._lock = threading.Lock()
        self._token = None
        self._expira_em = 0.0

    def get(self):
        with self._lock:
            if self._token and time.monotonic() < self._expira_em:
                return self._token
            return None

    def set(self, token: str, expira_em_segundos: int):
        with self._lock:
            self._token = token
            # margem de segurança de 30s
            self._expira_em = time.monotonic() + max(0, expira_em_segundos - 30)

    def clear(self):
        with self._lock:
            self._token = None
            self._expira_em = 0.0


class EProtocoloClient:
    """Transporte HTTP isolado para o eProtocolo."""

    def __init__(self, config: dict | None = None, session: requests.Session | None = None):
        self.config = config or cfg.get_config()
        self._session = session or requests.Session()
        self._token_cache = _TokenCache()

    # -- autenticação ------------------------------------------------------
    def _obter_token(self) -> str:
        token = self._token_cache.get()
        if token:
            return token

        token_url = (self.config.get("TOKEN_URL") or "").strip()
        client_id = (self.config.get("CLIENT_ID") or "").strip()
        client_secret = (self.config.get("CLIENT_SECRET") or "").strip()
        if not (token_url and client_id and client_secret):
            raise EProtocoloNaoConfiguradoError()

        logger.info("eProtocolo: solicitando token de acesso (client_credentials).")
        try:
            resposta = self._session.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                timeout=self.config.get("TIMEOUT", 30),
                verify=self.config.get("VERIFY_SSL", True),
            )
        except requests.Timeout as exc:
            raise EProtocoloTimeoutError() from exc
        except requests.RequestException as exc:
            raise EProtocoloUnavailableError(str(exc)) from exc

        if resposta.status_code >= 400:
            raise excecao_para_status(resposta.status_code, "Falha ao obter token de acesso.")

        dados = resposta.json()
        token = dados.get("access_token")
        if not token:
            raise EProtocoloError("Resposta de token sem 'access_token'.")
        self._token_cache.set(token, int(dados.get("expires_in", 300) or 300))
        return token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._obter_token()}",
            "consumerId": (self.config.get("CONSUMER_ID") or "").strip(),
            "Accept": "application/json",
        }

    # -- requisição base ---------------------------------------------------
    def _url(self, path: str) -> str:
        base = (self.config.get("BASE_URL") or "").strip().rstrip("/")
        if not base:
            raise EProtocoloNaoConfiguradoError()
        return f"{base}/{path.lstrip('/')}"

    def request(self, metodo: str, path: str, *, params=None, json=None, data=None, files=None):
        url = self._url(path)
        headers = self._headers()
        inicio = time.monotonic()
        try:
            resposta = self._session.request(
                metodo.upper(),
                url,
                params=params,
                json=json,
                data=data,
                files=files,
                headers=headers,
                timeout=self.config.get("TIMEOUT", 30),
                verify=self.config.get("VERIFY_SSL", True),
            )
        except requests.Timeout as exc:
            logger.warning("eProtocolo timeout: %s %s", metodo, path)
            raise EProtocoloTimeoutError() from exc
        except requests.RequestException as exc:
            logger.warning("eProtocolo erro de conexão: %s %s (%s)", metodo, path, exc)
            raise EProtocoloUnavailableError(str(exc)) from exc

        duracao_ms = int((time.monotonic() - inicio) * 1000)
        logger.info(
            "eProtocolo %s %s → %s (%sms) req=%s",
            metodo.upper(), path, resposta.status_code, duracao_ms, _mascarar(json or data or {}),
        )

        if resposta.status_code >= 400:
            corpo = self._json_seguro(resposta)
            raise excecao_para_status(
                resposta.status_code,
                f"eProtocolo respondeu {resposta.status_code} em {metodo.upper()} {path}.",
                payload=corpo,
            )
        return self._json_seguro(resposta)

    @staticmethod
    def _json_seguro(resposta):
        try:
            return resposta.json()
        except ValueError:
            return {"_raw": resposta.text}

    # -- métodos genéricos -------------------------------------------------
    def get(self, path, params=None):
        return self.request("GET", path, params=params)

    def post(self, path, json=None, files=None, data=None):
        return self.request("POST", path, json=json, files=files, data=data)

    def put(self, path, json=None):
        return self.request("PUT", path, json=json)

    def delete(self, path, json=None):
        return self.request("DELETE", path, json=json)


def get_client(config: dict | None = None) -> EProtocoloClient:
    """Fábrica do client (facilita injeção/substituição em testes)."""
    return EProtocoloClient(config=config)
