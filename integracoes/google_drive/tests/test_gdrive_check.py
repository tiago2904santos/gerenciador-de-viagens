"""`gdrive_check` é o que responde "o Drive está funcionando de verdade?".

Antes ele parava na configuração e na existência do token — os dois estados que
NÃO explicavam a falha vista em produção. Agora confere a pasta raiz e, com
`--e2e`, prova o caminho inteiro: sobe um arquivo, confirma que ele está
visível e apaga.
"""

from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from integracoes.google_drive import services

_ESCOPOS = " ".join(services._SCOPES)


def _cfg(**extra):
    base = {
        "MODO": "ativo",
        "CLIENT_ID": "id",
        "CLIENT_SECRET": "secret",
        "REDIRECT_URI": "https://exemplo/callback/",
        "PASTA_RAIZ_ID": "raiz",
    }
    base.update(extra)
    return base


def _credencial(**extra):
    from datetime import datetime, timezone

    padrao = {
        "atualizado_em": datetime(2026, 8, 25, tzinfo=timezone.utc),
        "token_expiry": None,
        "scope": _ESCOPOS,
        "refresh_token": "refresh",
        "pasta_raiz_id": "raiz",
    }
    padrao.update(extra)
    return mock.Mock(**padrao)


def _rodar(**kwargs):
    saida = StringIO()
    call_command("gdrive_check", stdout=saida, stderr=StringIO(), **kwargs)
    return saida.getvalue()


class GdriveCheckTests(SimpleTestCase):
    def setUp(self):
        services._reset_client()
        self.addCleanup(services._reset_client)

    @override_settings(GOOGLE_DRIVE={"MODO": "mock"})
    @mock.patch.object(services, "get_credenciais", return_value=None)
    def test_modo_mock_avisa_que_nada_chega_ao_drive(self, _creds):
        saida = _rodar()

        self.assertIn("Modo mock ativo", saida)
        self.assertIn("uploads não chegam ao Drive real", saida)

    @override_settings(GOOGLE_DRIVE=_cfg(CLIENT_ID="", CLIENT_SECRET=""))
    def test_ativo_sem_client_oauth_falha_apontando_o_env(self):
        with self.assertRaisesMessage(CommandError, "invalid_client"):
            _rodar()

    @override_settings(GOOGLE_DRIVE=_cfg())
    @mock.patch.object(services, "get_credenciais", return_value=None)
    def test_ativo_sem_credencial_falha(self, _creds):
        with self.assertRaisesMessage(CommandError, "Sem credencial OAuth"):
            _rodar()

    @override_settings(GOOGLE_DRIVE=_cfg())
    @mock.patch.object(services, "get_client")
    @mock.patch.object(services, "get_credenciais")
    def test_raiz_na_lixeira_reprova_o_diagnostico(self, get_credenciais, get_client):
        get_credenciais.return_value = _credencial()
        get_client.return_value.inspecionar_pasta.return_value = {
            "name": "VIAGENS",
            "trashed": True,
        }

        with self.assertRaisesMessage(CommandError, "LIXEIRA"):
            _rodar()

    @override_settings(GOOGLE_DRIVE=_cfg())
    @mock.patch.object(services, "get_client")
    @mock.patch.object(services, "get_credenciais")
    def test_credencial_sem_refresh_token_e_denunciada(self, get_credenciais, get_client):
        get_credenciais.return_value = _credencial(refresh_token="")
        get_client.return_value.inspecionar_pasta.return_value = {"name": "VIAGENS"}

        saida = _rodar()

        self.assertIn("SEM REFRESH TOKEN", saida)

    @override_settings(GOOGLE_DRIVE=_cfg())
    @mock.patch.object(services, "get_client")
    @mock.patch.object(services, "get_credenciais")
    def test_raiz_saudavel_sem_e2e_para_antes_de_escrever(self, get_credenciais, get_client):
        get_credenciais.return_value = _credencial()
        cliente = get_client.return_value
        cliente.inspecionar_pasta.return_value = {"name": "VIAGENS"}

        saida = _rodar()

        self.assertIn('Pasta raiz OK: "VIAGENS"', saida)
        self.assertIn("--e2e", saida)
        cliente.upload.assert_not_called()

    @override_settings(GOOGLE_DRIVE=_cfg())
    @mock.patch.object(services, "get_client")
    @mock.patch.object(services, "get_credenciais")
    def test_e2e_envia_confere_e_limpa(self, get_credenciais, get_client):
        get_credenciais.return_value = _credencial()
        cliente = get_client.return_value
        cliente.inspecionar_pasta.return_value = {"name": "VIAGENS"}
        cliente.upload.return_value = ("file-1", "https://drive/file-1")
        cliente.buscar_arquivo_por_nome.return_value = "file-1"

        saida = _rodar(e2e=True)

        self.assertIn("a integração está funcionando", saida)
        nome_enviado = cliente.upload.call_args.args[0]
        self.assertTrue(nome_enviado.startswith("_teste-integracao-"))
        self.assertEqual(cliente.upload.call_args.args[3], "raiz")
        cliente.excluir_arquivo.assert_called_once_with("file-1")

    @override_settings(GOOGLE_DRIVE=_cfg())
    @mock.patch.object(services, "get_client")
    @mock.patch.object(services, "get_credenciais")
    def test_e2e_denuncia_arquivo_que_sobe_mas_nao_aparece(self, get_credenciais, get_client):
        get_credenciais.return_value = _credencial()
        cliente = get_client.return_value
        cliente.inspecionar_pasta.return_value = {"name": "VIAGENS"}
        cliente.upload.return_value = ("file-1", "url")
        # Sintoma exato da pasta lixeirada: o upload devolve id, a busca (que
        # filtra `trashed = false`) não acha nada.
        cliente.buscar_arquivo_por_nome.return_value = None

        with self.assertRaisesMessage(CommandError, "NÃO foi encontrado"):
            _rodar(e2e=True)

        # Mesmo reprovando, não deixa lixo na pasta do usuário.
        cliente.excluir_arquivo.assert_called_once_with("file-1")
