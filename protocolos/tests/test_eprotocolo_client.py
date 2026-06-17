"""Testes do client/serviços de integração eProtocolo (com mock HTTP)."""

from __future__ import annotations

import requests
from django.test import SimpleTestCase, override_settings

from integracoes.eprotocolo import services as epro
from integracoes.eprotocolo import settings as cfg
from integracoes.eprotocolo.client import EProtocoloClient, mascarar_dados
from integracoes.eprotocolo.exceptions import (
    EProtocoloAuthError,
    EProtocoloForbiddenError,
    EProtocoloNaoConfiguradoError,
    EProtocoloNotFoundError,
    EProtocoloTimeoutError,
    EProtocoloUnavailableError,
    EProtocoloValidationError,
)


CONFIG_REAL = {
    "AMBIENTE": "homologacao",
    "BASE_URL": "https://api.exemplo/eprotocolo",
    "TOKEN_URL": "https://api.exemplo/token",
    "CLIENT_ID": "cid",
    "CLIENT_SECRET": "secret",
    "CONSUMER_ID": "consumer",
    "TIMEOUT": 5,
    "VERIFY_SSL": True,
}


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        if self._json is None:
            raise ValueError("sem json")
        return self._json


class FakeSession:
    """Sessão fake: 1ª chamada de token, depois responde conforme programado."""

    def __init__(self, request_response=None, request_exc=None):
        self.request_response = request_response
        self.request_exc = request_exc
        self.calls = []

    def post(self, url, **kwargs):  # token endpoint
        self.calls.append(("POST_TOKEN", url, kwargs))
        return FakeResponse(200, {"access_token": "jwt-xyz", "expires_in": 300})

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if self.request_exc is not None:
            raise self.request_exc
        return self.request_response


def make_client(request_response=None, request_exc=None):
    session = FakeSession(request_response=request_response, request_exc=request_exc)
    return EProtocoloClient(config=CONFIG_REAL, session=session), session


class ConfiguracaoTests(SimpleTestCase):
    def test_modo_mock_por_padrao(self):
        # Sem credenciais nas settings de teste → mock.
        self.assertTrue(cfg.em_modo_mock())
        self.assertFalse(cfg.eprotocolo_esta_configurado())

    @override_settings(EPROTOCOLO=CONFIG_REAL)
    def test_configurado_com_credenciais(self):
        self.assertTrue(cfg.eprotocolo_esta_configurado())
        self.assertFalse(cfg.em_modo_mock())

    @override_settings(EPROTOCOLO={**CONFIG_REAL, "AMBIENTE": "mock"})
    def test_ambiente_mock_forca_mock_mesmo_com_credenciais(self):
        self.assertTrue(cfg.em_modo_mock())


class ClientSemCredenciaisTests(SimpleTestCase):
    def test_client_sem_config_levanta_nao_configurado(self):
        client = EProtocoloClient(config={}, session=FakeSession())
        with self.assertRaises(EProtocoloNaoConfiguradoError):
            client.get("/protocolo/123")


class ClientErrosHTTPTests(SimpleTestCase):
    def test_200_retorna_json(self):
        client, _ = make_client(FakeResponse(200, {"numero": "1"}))
        self.assertEqual(client.get("/protocolo/1"), {"numero": "1"})

    def test_400_validacao(self):
        client, _ = make_client(FakeResponse(400, {"erro": "x"}))
        with self.assertRaises(EProtocoloValidationError):
            client.get("/protocolo/1")

    def test_401_auth(self):
        client, _ = make_client(FakeResponse(401))
        with self.assertRaises(EProtocoloAuthError):
            client.get("/protocolo/1")

    def test_403_forbidden(self):
        client, _ = make_client(FakeResponse(403))
        with self.assertRaises(EProtocoloForbiddenError):
            client.get("/protocolo/1")

    def test_404_not_found(self):
        client, _ = make_client(FakeResponse(404))
        with self.assertRaises(EProtocoloNotFoundError):
            client.get("/protocolo/1")

    def test_500_indisponivel(self):
        client, _ = make_client(FakeResponse(500))
        with self.assertRaises(EProtocoloUnavailableError):
            client.get("/protocolo/1")

    def test_timeout(self):
        client, _ = make_client(request_exc=requests.Timeout())
        with self.assertRaises(EProtocoloTimeoutError):
            client.get("/protocolo/1")

    def test_erro_conexao(self):
        client, _ = make_client(request_exc=requests.ConnectionError())
        with self.assertRaises(EProtocoloUnavailableError):
            client.get("/protocolo/1")

    def test_headers_incluem_authorization_e_consumer(self):
        client, session = make_client(FakeResponse(200, {}))
        client.get("/protocolo/1")
        # a última chamada é o request (não o token)
        _, _, kwargs = session.calls[-1]
        headers = kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer jwt-xyz")
        self.assertEqual(headers["consumerId"], "consumer")


class AuthErroTokenTests(SimpleTestCase):
    def test_token_401_propaga_auth_error(self):
        class TokenFailSession(FakeSession):
            def post(self, url, **kwargs):
                return FakeResponse(401)

        client = EProtocoloClient(config=CONFIG_REAL, session=TokenFailSession())
        with self.assertRaises(EProtocoloAuthError):
            client.get("/protocolo/1")


class MascaramentoTests(SimpleTestCase):
    def test_mascara_campos_sensiveis(self):
        bruto = {
            "Authorization": "Bearer abc",
            "client_secret": "shh",
            "consumerId": "c",
            "dados": {"token": "t", "nome": "Fulano"},
        }
        limpo = mascarar_dados(bruto)
        self.assertEqual(limpo["Authorization"], "***")
        self.assertEqual(limpo["client_secret"], "***")
        self.assertEqual(limpo["consumerId"], "***")
        self.assertEqual(limpo["dados"]["token"], "***")
        self.assertEqual(limpo["dados"]["nome"], "Fulano")


class ServicosModoMockTests(SimpleTestCase):
    def test_criar_protocolo_mock(self):
        resultado = epro.criar_protocolo({"assunto": "Viagem"})
        self.assertTrue(resultado.sucesso)
        self.assertTrue(resultado.mock)
        self.assertTrue(resultado.dados["numero"])

    def test_md5(self):
        self.assertEqual(
            epro.calcular_md5(b"abc"),
            "900150983cd24fb0d6963f7d28e17f72",
        )

    def test_enviar_documento_mock_calcula_md5(self):
        resultado = epro.enviar_documento("24.1.1-1", b"conteudo-pdf", "doc.pdf")
        self.assertTrue(resultado.mock)
        self.assertEqual(resultado.dados["md5"], epro.calcular_md5(b"conteudo-pdf"))
        self.assertEqual(resultado.dados["tamanhoBytes"], len(b"conteudo-pdf"))
