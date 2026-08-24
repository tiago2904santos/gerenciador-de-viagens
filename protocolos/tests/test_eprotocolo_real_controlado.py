from __future__ import annotations

from io import StringIO
from unittest import mock

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from integracoes.eprotocolo import services as epro
from integracoes.eprotocolo import settings as cfg
from integracoes.eprotocolo.client import EProtocoloClient, mascarar_dados
from integracoes.eprotocolo.exceptions import EProtocoloAuthError
from integracoes.eprotocolo.exceptions import EProtocoloConfigError
from integracoes.eprotocolo.exceptions import EProtocoloNotFoundError
from integracoes.eprotocolo.exceptions import EProtocoloTimeoutError
from integracoes.eprotocolo.exceptions import EProtocoloValidationError
from protocolos import services as proto_services
from protocolos.models import Protocolo


CONFIG_REAL_CONTROLADO = {
    "AMBIENTE": "real_controlado",
    "BASE_URL": "https://real.exemplo/spi-servicos",
    "TOKEN_URL": "https://real.exemplo/token",
    "CLIENT_ID": "client-real",
    "CLIENT_SECRET": "secret-real",
    "CONSUMER_ID": "consumer-real",
    "TIMEOUT": 5,
    "VERIFY_SSL": True,
    "REAL_READONLY": True,
    "REAL_MUTATIONS_ENABLED": False,
}

CONFIG_MUTACOES = {
    **CONFIG_REAL_CONTROLADO,
    "REAL_READONLY": False,
    "REAL_MUTATIONS_ENABLED": True,
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
    def __init__(self, responses=None, request_exc=None):
        self.responses = list(responses or [FakeResponse(200, {})])
        self.request_exc = request_exc
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST_TOKEN", url, kwargs))
        return FakeResponse(200, {"access_token": "jwt-real", "expires_in": 300})

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if self.request_exc is not None:
            raise self.request_exc
        if len(self.responses) > 1:
            return self.responses.pop(0)
        return self.responses[0]


def _patch_client(session):
    return mock.patch.object(
        epro,
        "get_client",
        return_value=EProtocoloClient(config=cfg.get_config(), session=session),
    )


class ConfigRealControladoTests(SimpleTestCase):
    @override_settings(EPROTOCOLO=CONFIG_REAL_CONTROLADO)
    def test_real_controlado_configurado(self):
        info = cfg.validar_configuracao()
        self.assertTrue(cfg.is_real_controlado())
        self.assertTrue(cfg.is_real())
        self.assertFalse(cfg.em_modo_mock())
        self.assertTrue(info["read_only"])
        self.assertFalse(info["mutations_enabled"])

    @override_settings(EPROTOCOLO=CONFIG_REAL_CONTROLADO)
    def test_check_real_nao_exibe_secret(self):
        out = StringIO()
        call_command("eprotocolo_check_real", stdout=out)
        texto = out.getvalue()
        self.assertIn("Ambiente: real_controlado", texto)
        self.assertIn("Read-only: ativo", texto)
        self.assertIn("Mutacoes reais: bloqueadas", texto)
        self.assertNotIn("secret-real", texto)
        self.assertNotIn("consumer-real", texto)
        self.assertIn("Status: configuracao minima OK", texto)

    def test_mascarar_cpf_em_payload(self):
        limpo = mascarar_dados({"cpfResponsavelAtual": "11144477735"})
        self.assertEqual(limpo["cpfResponsavelAtual"], "111.***.***-35")


@override_settings(EPROTOCOLO=CONFIG_REAL_CONTROLADO)
class ComandosReadOnlyTests(TestCase):
    def test_ping_real_sucesso(self):
        session = FakeSession([FakeResponse(200, {"orgaos": []})])
        out = StringIO()
        with _patch_client(session):
            call_command("eprotocolo_ping_real", stdout=out)
        texto = out.getvalue()
        self.assertIn("Token OK", texto)
        self.assertIn("Integracao real acessivel", texto)
        self.assertIn("Nenhuma alteracao feita no eProtocolo", texto)

    def test_ping_real_403_da_dica(self):
        session = FakeSession([FakeResponse(403)])
        with _patch_client(session):
            with self.assertRaises(CommandError):
                call_command("eprotocolo_ping_real", stdout=StringIO(), stderr=StringIO())

    def test_consultar_real_somente_consulta(self):
        session = FakeSession(
            [
                FakeResponse(200, {
                    "numero": "24.123.456-7",
                    "situacao": "EM_TRAMITACAO",
                    "nomeLocalAtual": "Setor A",
                    "cpfResponsavelAtual": "11144477735",
                    "nomeResponsavelAtual": "Fulano",
                }),
                FakeResponse(200, {"documentos": [{"codigoDocumento": "DOC1", "nomeArquivo": "teste.pdf"}]}),
                FakeResponse(200, {"documentos": []}),
                FakeResponse(200, {"tramitacoes": []}),
                FakeResponse(200, {"movimentacoes": []}),
                FakeResponse(200, {"pendencias": []}),
                FakeResponse(200, {"assinaturas": []}),
            ]
        )
        out = StringIO()
        with _patch_client(session):
            call_command("eprotocolo_consultar_real", "--protocolo", "24.123.456-7", stdout=out)
        texto = out.getvalue()
        self.assertIn("Protocolo consultado: 24.123.456-7", texto)
        self.assertIn("Documentos encontrados: 1", texto)
        self.assertIn("111.***.***-35", texto)
        self.assertIn("Alteracoes no eProtocolo: nenhuma", texto)
        self.assertFalse(Protocolo.objects.filter(numero="24.123.456-7").exists())

    def test_importar_real_cria_espelho_sem_duplicar(self):
        responses = [
            FakeResponse(200, {
                "numero": "24.123.456-7",
                "situacao": "EM_TRAMITACAO",
                "codLocalAtual": "10",
                "nomeLocalAtual": "Setor A",
            }),
            FakeResponse(200, {"documentos": [{"codigoDocumento": "DOC1", "nomeArquivo": "teste.pdf"}]}),
            FakeResponse(200, {"documentos": []}),
            FakeResponse(200, {"tramitacoes": [{"codLocalPara": "10", "dataTramitacao": "2026-06-17T12:00:00Z"}]}),
            FakeResponse(200, {"movimentacoes": [{"tipo": "CRIACAO", "descricao": "Criado"}]}),
            FakeResponse(200, {"pendencias": [{"codigoPendencia": "P1", "tipo": "ASSINATURA"}]}),
            FakeResponse(200, {"assinaturas": []}),
        ]
        session = FakeSession(responses)
        with _patch_client(session):
            protocolo = proto_services.importar_protocolo_real("24.123.456-7")
            protocolo = proto_services.importar_protocolo_real("24.123.456-7")
        self.assertEqual(protocolo.origem_tipo, Protocolo.ORIGEM_EPROTOCOLO_REAL)
        self.assertEqual(protocolo.documentos.count(), 1)
        self.assertEqual(protocolo.tramitacoes.count(), 1)
        self.assertEqual(protocolo.movimentacoes.count(), 1)
        self.assertEqual(protocolo.pendencias.count(), 1)


class GuardasMutacaoRealTests(TestCase):
    @override_settings(EPROTOCOLO=CONFIG_REAL_CONTROLADO)
    def test_mutacao_bloqueada_em_readonly(self):
        protocolo = Protocolo.objects.create(numero="24.1.1-1")
        with self.assertRaises(EProtocoloConfigError):
            proto_services.anexar_documento(
                protocolo,
                tipo="ANEXO",
                nome_arquivo="a.pdf",
                conteudo=b"%PDF-1.4",
                real=True,
                confirmado=True,
            )

    @override_settings(EPROTOCOLO=CONFIG_MUTACOES)
    def test_mutacao_bloqueada_sem_flag_real(self):
        with self.assertRaises(EProtocoloConfigError):
            cfg.garantir_operacao_real_permitida(
                "tramitar", protocolo="24.1.1-1", real=False, confirmado=True
            )

    @override_settings(EPROTOCOLO=CONFIG_MUTACOES)
    def test_mutacao_bloqueada_sem_confirmacao(self):
        with self.assertRaises(EProtocoloConfigError):
            cfg.garantir_operacao_real_permitida(
                "tramitar", protocolo="24.1.1-1", real=True, confirmado=False
            )

    @override_settings(EPROTOCOLO=CONFIG_MUTACOES)
    def test_mutacao_bloqueada_em_lote(self):
        with self.assertRaises(EProtocoloConfigError):
            cfg.garantir_operacao_real_permitida(
                "tramitar", protocolo="24.1.1-1", real=True, confirmado=True, quantidade=2
            )


@override_settings(EPROTOCOLO=CONFIG_REAL_CONTROLADO)
class ErrosReaisTests(SimpleTestCase):
    def test_401(self):
        session = FakeSession([FakeResponse(401)])
        with _patch_client(session):
            with self.assertRaises(EProtocoloAuthError):
                epro.testar_conexao()

    def test_404(self):
        session = FakeSession([FakeResponse(404)])
        with _patch_client(session):
            with self.assertRaises(EProtocoloNotFoundError):
                epro.consultar_protocolo("24.1.1-1")

    def test_422(self):
        session = FakeSession([FakeResponse(422, {"erro": "payload"})])
        with _patch_client(session):
            with self.assertRaises(EProtocoloValidationError):
                epro.consultar_protocolo("24.1.1-1")

    def test_timeout(self):
        session = FakeSession(request_exc=requests.Timeout())
        with _patch_client(session):
            with self.assertRaises(EProtocoloTimeoutError):
                epro.consultar_protocolo("24.1.1-1")
