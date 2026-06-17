"""Testes da camada de treinamento do eProtocolo (mock HTTP, sem credenciais reais).

Cobrem: configuração mock/treinamento, comandos check/ping, mapeamento validado
do Ofício, dry-run de homologação, validação de PDF, mascaramento de segredos e
ausência de token nos logs.
"""

from __future__ import annotations

from io import StringIO
from unittest import mock

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from integracoes.eprotocolo import mappers
from integracoes.eprotocolo import services as epro
from integracoes.eprotocolo import settings as cfg
from integracoes.eprotocolo.client import EProtocoloClient
from integracoes.eprotocolo.exceptions import (
    EProtocoloAuthError,
    EProtocoloForbiddenError,
    EProtocoloNotFoundError,
    EProtocoloTimeoutError,
    EProtocoloValidationError,
)

from oficios.models import Oficio


CONFIG_TREINAMENTO = {
    "AMBIENTE": "treinamento",
    "BASE_URL": "https://treino.exemplo/spi-servicos",
    "TOKEN_URL": "https://treino.exemplo/token",
    "CLIENT_ID": "client-treino",
    "CLIENT_SECRET": "secret-treino",
    "CONSUMER_ID": "consumer-treino",
    "TIMEOUT": 5,
    "VERIFY_SSL": True,
    "COD_ORGAO_PADRAO": "100",
    "COD_LOCAL_ORIGEM_PADRAO": "200",
    "COD_ASSUNTO_VIAGEM": "300",
    "COD_ESPECIE_OFICIO": "400",
}

CONFIG_TREINAMENTO_SEM_CRED = {
    "AMBIENTE": "treinamento",
    "BASE_URL": "",
    "TOKEN_URL": "",
    "CLIENT_ID": "",
    "CLIENT_SECRET": "",
    "CONSUMER_ID": "",
}


class FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.text = ""

    def json(self):
        return self._json


class FakeSession:
    def __init__(self, request_response=None, request_exc=None):
        self.request_response = request_response or FakeResponse(200, {})
        self.request_exc = request_exc
        self.calls = []

    def post(self, url, **kwargs):  # token endpoint
        self.calls.append(("POST_TOKEN", url, kwargs))
        return FakeResponse(200, {"access_token": "jwt-treino", "expires_in": 300})

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if self.request_exc is not None:
            raise self.request_exc
        return self.request_response


def _patch_client(session):
    """Faz services.get_client() devolver um client com a FakeSession dada."""
    return mock.patch.object(
        epro, "get_client",
        return_value=EProtocoloClient(config=cfg.get_config(), session=session),
    )


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
class ConfiguracaoTreinamentoTests(SimpleTestCase):
    def test_mock_por_padrao_nas_settings_de_teste(self):
        self.assertTrue(cfg.em_modo_mock())
        self.assertFalse(cfg.eprotocolo_esta_configurado())

    @override_settings(EPROTOCOLO=CONFIG_TREINAMENTO)
    def test_treinamento_com_credenciais_e_real(self):
        self.assertTrue(cfg.is_treinamento())
        self.assertTrue(cfg.is_real())
        self.assertFalse(cfg.is_producao())
        self.assertFalse(cfg.em_modo_mock())
        self.assertTrue(cfg.eprotocolo_esta_configurado())

    @override_settings(EPROTOCOLO=CONFIG_TREINAMENTO_SEM_CRED)
    def test_treinamento_sem_credenciais_cai_em_mock(self):
        self.assertTrue(cfg.is_treinamento())
        self.assertTrue(cfg.em_modo_mock())
        self.assertFalse(cfg.eprotocolo_esta_configurado())
        self.assertTrue(cfg.campos_faltantes())

    def test_mascarar_segredo(self):
        self.assertEqual(cfg.mascarar_segredo("abcdefgh"), "abcd****")
        self.assertEqual(cfg.mascarar_segredo(""), "(não configurado)")
        self.assertEqual(cfg.mascarar_segredo("ab"), "**")

    @override_settings(EPROTOCOLO=CONFIG_TREINAMENTO)
    def test_validar_configuracao_ok(self):
        info = cfg.validar_configuracao()
        self.assertTrue(info["ok"])
        self.assertTrue(info["modo_real"])
        self.assertFalse(info["producao"])
        self.assertEqual(info["client_id"], "clie****")
        self.assertEqual(info["campos_faltantes"], [])


# ---------------------------------------------------------------------------
# Comando: eprotocolo_check
# ---------------------------------------------------------------------------
class CheckCommandTests(SimpleTestCase):
    def test_check_mock_status_ok(self):
        out = StringIO()
        call_command("eprotocolo_check", stdout=out)
        texto = out.getvalue()
        self.assertIn("Ambiente: mock", texto)
        self.assertIn("configuração mínima OK", texto)

    @override_settings(EPROTOCOLO=CONFIG_TREINAMENTO_SEM_CRED)
    def test_check_treinamento_incompleto(self):
        out = StringIO()
        call_command("eprotocolo_check", stdout=out)
        texto = out.getvalue()
        self.assertIn("configuração incompleta", texto)

    @override_settings(EPROTOCOLO=CONFIG_TREINAMENTO)
    def test_check_nunca_exibe_secret(self):
        out = StringIO()
        call_command("eprotocolo_check", "--escopos", stdout=out)
        texto = out.getvalue()
        self.assertNotIn("secret-treino", texto)
        self.assertIn("Client Secret: configurado", texto)
        self.assertIn("spiserv.protocolos.incluir", texto)


# ---------------------------------------------------------------------------
# Comando: eprotocolo_ping
# ---------------------------------------------------------------------------
class PingCommandTests(SimpleTestCase):
    def test_ping_mock(self):
        out = StringIO()
        call_command("eprotocolo_ping", stdout=out)
        texto = out.getvalue()
        self.assertIn("Token OK", texto)
        self.assertIn("mock", texto)

    @override_settings(EPROTOCOLO=CONFIG_TREINAMENTO)
    def test_ping_real_sucesso_mockado(self):
        session = FakeSession(FakeResponse(200, {"orgaos": []}))
        out = StringIO()
        with _patch_client(session):
            call_command("eprotocolo_ping", stdout=out)
        self.assertIn("Integração acessível", out.getvalue())

    @override_settings(EPROTOCOLO=CONFIG_TREINAMENTO)
    def test_ping_403_da_dica(self):
        session = FakeSession(FakeResponse(403))
        out, err = StringIO(), StringIO()
        with _patch_client(session):
            call_command("eprotocolo_ping", stdout=out, stderr=err)
        self.assertIn("403", err.getvalue())


# ---------------------------------------------------------------------------
# Serviços reais (mock HTTP) — erros traduzidos
# ---------------------------------------------------------------------------
@override_settings(EPROTOCOLO=CONFIG_TREINAMENTO)
class ServicosReaisErrosTests(SimpleTestCase):
    def test_auth_error(self):
        session = FakeSession(FakeResponse(401))
        with _patch_client(session):
            with self.assertRaises(EProtocoloAuthError):
                epro.testar_conexao()

    def test_forbidden(self):
        session = FakeSession(FakeResponse(403))
        with _patch_client(session):
            with self.assertRaises(EProtocoloForbiddenError):
                epro.listar_orgaos()

    def test_not_found(self):
        session = FakeSession(FakeResponse(404))
        with _patch_client(session):
            with self.assertRaises(EProtocoloNotFoundError):
                epro.listar_assuntos()

    def test_timeout(self):
        session = FakeSession(request_exc=requests.Timeout())
        with _patch_client(session):
            with self.assertRaises(EProtocoloTimeoutError):
                epro.listar_especies()

    def test_listar_orgaos_usa_path_v3(self):
        session = FakeSession(FakeResponse(200, {"orgaos": []}))
        with _patch_client(session):
            epro.listar_orgaos()
        metodo, url, _ = session.calls[-1]
        self.assertEqual(metodo, "GET")
        self.assertTrue(url.endswith("/v3/orgaos"))

    def test_token_nunca_aparece_em_log(self):
        session = FakeSession(FakeResponse(200, {"orgaos": []}))
        with _patch_client(session):
            with self.assertLogs("integracoes.eprotocolo", level="INFO") as captura:
                epro.testar_conexao()
        texto = "\n".join(captura.output)
        self.assertNotIn("jwt-treino", texto)
        self.assertNotIn("secret-treino", texto)


# ---------------------------------------------------------------------------
# Mapper validado do Ofício
# ---------------------------------------------------------------------------
class MapperOficioValidadoTests(TestCase):
    def setUp(self):
        self.oficio = Oficio.objects.create(numero=42, ano=2026, assunto="Viagem treino")

    @override_settings(EPROTOCOLO=CONFIG_TREINAMENTO)
    def test_payload_valido_com_codigos(self):
        payload = mappers.mapear_oficio_para_payload_eprotocolo(self.oficio)
        self.assertEqual(payload["numeroDocumento"], 42)
        self.assertEqual(payload["codOrgao"], "100")
        self.assertEqual(payload["codEspecie"], "400")

    @override_settings(EPROTOCOLO=CONFIG_TREINAMENTO_SEM_CRED)
    def test_payload_sem_codigos_levanta_validation(self):
        with self.assertRaises(EProtocoloValidationError):
            mappers.mapear_oficio_para_payload_eprotocolo(self.oficio)

    @override_settings(EPROTOCOLO=CONFIG_TREINAMENTO)
    def test_oficio_sem_numero_levanta_validation(self):
        oficio = Oficio.objects.create(ano=2026, assunto="Sem número")
        with self.assertRaises(EProtocoloValidationError):
            mappers.mapear_oficio_para_payload_eprotocolo(oficio)


# ---------------------------------------------------------------------------
# Comando: eprotocolo_homologar (dry-run + guardas)
# ---------------------------------------------------------------------------
class HomologarCommandTests(TestCase):
    def setUp(self):
        self.oficio = Oficio.objects.create(numero=7, ano=2026, assunto="Homolog")

    @override_settings(EPROTOCOLO=CONFIG_TREINAMENTO)
    def test_dry_run_valida_sem_chamar_api(self):
        out = StringIO()
        with mock.patch(
            "protocolos.services.resolver_pdf_documento",
            return_value=(b"%PDF-1.4 fake", "oficio.pdf", "OFICIO"),
        ):
            call_command("eprotocolo_homologar", "--oficio", str(self.oficio.pk),
                         "--dry-run", stdout=out)
        texto = out.getvalue()
        self.assertIn("Payload válido: sim", texto)
        self.assertIn("MD5:", texto)
        self.assertIn("Operação real: não", texto)

    @override_settings(EPROTOCOLO=CONFIG_TREINAMENTO)
    def test_dry_run_pdf_invalido_falha(self):
        with mock.patch(
            "protocolos.services.resolver_pdf_documento",
            return_value=(b"isto nao e pdf", "oficio.pdf", "OFICIO"),
        ):
            with self.assertRaises(CommandError):
                call_command("eprotocolo_homologar", "--oficio", str(self.oficio.pk),
                             "--dry-run", stdout=StringIO())

    def test_oficio_inexistente_falha(self):
        with self.assertRaises(CommandError):
            call_command("eprotocolo_homologar", "--oficio", "999999",
                         "--dry-run", stdout=StringIO())

    @override_settings(EPROTOCOLO={**CONFIG_TREINAMENTO, "AMBIENTE": "producao"})
    def test_real_bloqueado_fora_de_treinamento(self):
        with mock.patch(
            "protocolos.services.resolver_pdf_documento",
            return_value=(b"%PDF-1.4 fake", "oficio.pdf", "OFICIO"),
        ):
            with self.assertRaises(CommandError):
                call_command("eprotocolo_homologar", "--oficio", str(self.oficio.pk),
                             "--real", "--sim", stdout=StringIO())
