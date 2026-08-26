from datetime import datetime, timedelta, timezone
from unittest import mock

from django.test import SimpleTestCase, override_settings

from integracoes.google_drive import services


def _com_ttl(segundos):
    """Reaplica GOOGLE_DRIVE trocando só a validade do cache de pastas."""
    from django.conf import settings

    return override_settings(
        GOOGLE_DRIVE={**settings.GOOGLE_DRIVE, "PASTA_CACHE_TTL_SECONDS": segundos}
    )


def _client(files=None, drives=None):
    client = services._RealClient.__new__(services._RealClient)
    client._svc = mock.Mock()
    client._svc.files.return_value = files or mock.Mock()
    client._svc.drives.return_value = drives or mock.Mock()
    client._cache = {}
    return client


class RealClientInitializationTests(SimpleTestCase):
    @mock.patch.object(services, "get_credenciais", return_value=None)
    def test_exige_credencial_oauth(self, _get_credenciais):
        with self.assertRaisesMessage(RuntimeError, "nenhuma credencial OAuth"):
            services._RealClient()

    @mock.patch("googleapiclient.discovery.build")
    @mock.patch("google_auth_httplib2.AuthorizedHttp")
    @mock.patch("httplib2.Http")
    @mock.patch.object(services, "_credenciais_cls")
    @mock.patch.object(services, "_cfg", return_value={"CLIENT_ID": "id", "CLIENT_SECRET": "secret", "HTTP_TIMEOUT_SECONDS": "12"})
    @mock.patch.object(services, "get_credenciais")
    def test_renova_token_expirado_e_constroi_servico(
        self, get_credenciais, _cfg, credenciais_cls, http_cls, authorized_http, build
    ):
        stored = mock.Mock(
            access_token="old",
            refresh_token="refresh",
            token_expiry=datetime.now(tz=timezone.utc) - timedelta(minutes=1),
        )
        get_credenciais.return_value = stored
        credentials = credenciais_cls.return_value.return_value

        client = services._RealClient(usuario=mock.sentinel.usuario)

        # Quem grava o token novo agora é a própria credencial, no `refresh`.
        credentials.refresh.assert_called_once()
        self.assertIs(credentials.registro, stored)
        http_cls.assert_called_once_with(timeout=12.0)
        build.assert_called_once_with(
            "drive", "v3", http=authorized_http.return_value, cache_discovery=False
        )
        self.assertIs(client._svc, build.return_value)

    @mock.patch("googleapiclient.discovery.build")
    @mock.patch("google_auth_httplib2.AuthorizedHttp")
    @mock.patch("httplib2.Http")
    @mock.patch.object(services, "_credenciais_cls")
    @mock.patch.object(services, "_cfg", return_value={"CLIENT_ID": "id", "CLIENT_SECRET": "secret"})
    @mock.patch.object(services, "get_credenciais")
    def test_renova_token_que_vence_dentro_da_margem(
        self, get_credenciais, _cfg, credenciais_cls, _http_cls, _authorized_http, _build
    ):
        # Ainda válido, mas por menos que a margem: um job longo cruzaria o
        # vencimento no meio da execução.
        get_credenciais.return_value = mock.Mock(
            access_token="old",
            refresh_token="refresh",
            token_expiry=datetime.now(tz=timezone.utc) + timedelta(minutes=1),
        )

        services._RealClient()

        credenciais_cls.return_value.return_value.refresh.assert_called_once()

    @mock.patch("googleapiclient.discovery.build")
    @mock.patch("google_auth_httplib2.AuthorizedHttp")
    @mock.patch("httplib2.Http")
    @mock.patch.object(services, "_credenciais_cls")
    @mock.patch.object(services, "_cfg", return_value={"CLIENT_ID": "id", "CLIENT_SECRET": "secret"})
    @mock.patch.object(services, "get_credenciais")
    def test_nao_renova_token_com_folga(
        self, get_credenciais, _cfg, credenciais_cls, _http_cls, _authorized_http, _build
    ):
        get_credenciais.return_value = mock.Mock(
            access_token="ok",
            refresh_token="refresh",
            token_expiry=datetime.now(tz=timezone.utc) + timedelta(hours=1),
        )

        services._RealClient()

        credenciais_cls.return_value.return_value.refresh.assert_not_called()

    @mock.patch.object(services, "get_credenciais")
    def test_credencial_sem_refresh_token_pede_reconexao(self, get_credenciais):
        get_credenciais.return_value = mock.Mock(access_token="a", refresh_token="  ")

        with self.assertRaisesMessage(services.DriveReauthError, "não tem refresh token"):
            services._RealClient()


class CredenciaisPersistentesTests(SimpleTestCase):
    """O token renovado pelo google-auth precisa sobreviver ao processo."""

    def _creds(self, registro):
        creds = services._credenciais_cls()(
            token="antigo",
            refresh_token="refresh",
            token_uri=services._TOKEN_URI,
            client_id="id",
            client_secret="secret",
            scopes=list(services._SCOPES),
        )
        creds.registro = registro
        return creds

    def test_refresh_grava_token_novo_no_banco(self):
        registro = mock.Mock(access_token="antigo", token_expiry=None)
        creds = self._creds(registro)
        expiry = datetime.now(tz=timezone.utc) + timedelta(hours=1)

        def _renovar(self, _request):
            self.token = "novo"
            self.expiry = expiry.replace(tzinfo=None)

        with mock.patch("google.oauth2.credentials.Credentials.refresh", _renovar):
            creds.refresh(mock.sentinel.request)

        self.assertEqual(registro.access_token, "novo")
        registro.save.assert_called_once_with(
            update_fields=["access_token", "token_expiry", "atualizado_em"]
        )

    def test_invalid_grant_vira_pedido_de_reconexao(self):
        from google.auth.exceptions import RefreshError

        creds = self._creds(mock.Mock())

        with mock.patch(
            "google.oauth2.credentials.Credentials.refresh",
            side_effect=RefreshError("invalid_grant: Token has been expired or revoked."),
        ):
            with self.assertRaisesMessage(services.DriveReauthError, "Reconecte a conta"):
                creds.refresh(mock.sentinel.request)

    def test_falha_ao_gravar_nao_derruba_a_chamada(self):
        registro = mock.Mock()
        registro.save.side_effect = RuntimeError("credencial apagada")
        creds = self._creds(registro)

        def _renovar(self, _request):
            self.token = "novo"

        with mock.patch("google.oauth2.credentials.Credentials.refresh", _renovar):
            with mock.patch.object(services, "capture") as capture:
                creds.refresh(mock.sentinel.request)

        capture.assert_called_once()


class RealClientFileOperationTests(SimpleTestCase):
    @mock.patch("googleapiclient.http.MediaIoBaseUpload")
    def test_upload_envia_metadata_e_retorna_id_e_url(self, media_cls):
        files = mock.Mock()
        files.create.return_value.execute.return_value = {"id": "file-1", "webViewLink": "url"}
        client = _client(files)

        result = client.upload("relatorio.pdf", b"pdf", "application/pdf", "folder-1")

        self.assertEqual(result, ("file-1", "url"))
        files.create.assert_called_once_with(
            body={"name": "relatorio.pdf", "parents": ["folder-1"]},
            media_body=media_cls.return_value,
            fields="id,webViewLink",
            supportsAllDrives=True,
        )

    def test_get_or_create_pasta_reusa_api_e_cache(self):
        files = mock.Mock()
        files.list.return_value.execute.return_value = {"files": [{"id": "folder-1"}]}
        client = _client(files)

        with _com_ttl(300):
            self.assertEqual(client.get_or_create_pasta("Eventos", "root"), "folder-1")
            self.assertEqual(client.get_or_create_pasta("Eventos", "root"), "folder-1")
        files.list.assert_called_once()
        files.create.assert_not_called()

    def test_cache_de_pasta_expira_e_reconsulta_o_drive(self):
        """`NOVO-20260825-205015-e2fe5114f230`: cache eterno mandava arquivo para pasta morta."""
        files = mock.Mock()
        files.list.return_value.execute.side_effect = [
            {"files": [{"id": "folder-antiga"}]},
            {"files": [{"id": "folder-atual"}]},
        ]
        client = _client(files)

        with _com_ttl(300):
            self.assertEqual(client.get_or_create_pasta("Eventos", "root"), "folder-antiga")
            # Passou da validade: o worker não pode seguir escrevendo no ID velho.
            with mock.patch.object(
                services.time, "monotonic", return_value=client._cache[("root", "Eventos")][1] + 301
            ):
                self.assertEqual(client.get_or_create_pasta("Eventos", "root"), "folder-atual")

        self.assertEqual(files.list.call_count, 2)

    def test_inspecionar_pasta_pede_lixeira_e_permissao(self):
        files = mock.Mock()
        files.get.return_value.execute.return_value = {"id": "raiz", "trashed": True}
        client = _client(files)

        self.assertEqual(client.inspecionar_pasta("raiz"), {"id": "raiz", "trashed": True})
        campos = files.get.call_args.kwargs["fields"]
        self.assertIn("trashed", campos)
        self.assertIn("canAddChildren", campos)

    def test_get_or_create_pasta_cria_quando_busca_vazia(self):
        files = mock.Mock()
        files.list.return_value.execute.return_value = {"files": []}
        files.create.return_value.execute.return_value = {"id": "new-folder"}
        client = _client(files)

        self.assertEqual(client.get_or_create_pasta("Eventos"), "new-folder")
        files.create.assert_called_once_with(
            body={"name": "Eventos", "mimeType": services._FOLDER_MIME},
            fields="id",
            supportsAllDrives=True,
        )

    def test_listagens_preservam_parametros_de_drives_compartilhados(self):
        files = mock.Mock()
        files.list.return_value.execute.return_value = {"files": [{"id": "1", "name": "A"}]}
        drives = mock.Mock()
        drives.list.return_value.execute.return_value = {
            "drives": [{"id": "2", "name": "z"}, {"id": "1", "name": "A"}]
        }
        client = _client(files, drives)

        self.assertEqual(client.listar_pastas("pai"), [{"id": "1", "name": "A"}])
        self.assertEqual(client.listar_compartilhados_comigo(), [{"id": "1", "name": "A"}])
        self.assertEqual([item["name"] for item in client.listar_drives_compartilhados()], ["A", "z"])
        self.assertTrue(all(call.kwargs["supportsAllDrives"] for call in files.list.call_args_list))

    def test_mover_renomear_remove_pais_antigos(self):
        files = mock.Mock()
        files.get.return_value.execute.return_value = {"parents": ["old-1", "old-2"]}
        client = _client(files)

        self.assertEqual(client.mover_renomear("file", "novo", "destino"), "file")

        files.update.assert_called_once_with(
            fileId="file",
            body={"name": "novo"},
            fields="id",
            supportsAllDrives=True,
            addParents="destino",
            removeParents="old-1,old-2",
        )

    def test_criar_e_identificar_pasta(self):
        files = mock.Mock()
        files.create.return_value.execute.return_value = {"id": "folder", "name": "Eventos"}
        files.get.return_value.execute.return_value = {"name": "Eventos"}
        client = _client(files)

        self.assertEqual(client.criar_pasta("Eventos", "pai"), {"id": "folder", "name": "Eventos"})
        self.assertEqual(client.nome_pasta("folder"), "Eventos")
        files.create.assert_called_once_with(
            body={"name": "Eventos", "mimeType": services._FOLDER_MIME, "parents": ["pai"]},
            fields="id,name",
            supportsAllDrives=True,
        )

    def test_atalho_existente_e_reusado_ou_criado(self):
        files = mock.Mock()
        files.create.return_value.execute.return_value = {"id": "shortcut-new"}
        client = _client(files)
        client.mover_renomear = mock.Mock(return_value="shortcut-old")

        self.assertEqual(
            client.criar_ou_atualizar_atalho("Atalho", "target", "pai", "shortcut-old"),
            "shortcut-old",
        )
        files.create.assert_not_called()

        self.assertEqual(
            client.criar_ou_atualizar_atalho("Atalho", "target", "pai"), "shortcut-new"
        )
        files.create.assert_called_once_with(
            body={
                "name": "Atalho",
                "mimeType": services._SHORTCUT_MIME,
                "parents": ["pai"],
                "shortcutDetails": {"targetId": "target"},
            },
            fields="id",
            supportsAllDrives=True,
        )

    @mock.patch("googleapiclient.http.MediaIoBaseUpload")
    def test_atualizar_conteudo_pode_mover_arquivo(self, _media_cls):
        files = mock.Mock()
        files.update.return_value.execute.return_value = {"id": "file", "webViewLink": "url"}
        client = _client(files)
        client.mover_renomear = mock.Mock(return_value="file")

        self.assertEqual(
            client.atualizar_conteudo("file", "novo.pdf", b"pdf", "application/pdf", "dest"),
            ("file", "url"),
        )
        client.mover_renomear.assert_called_once_with("file", "novo.pdf", "dest")

    def test_buscas_escapam_nome_e_separam_arquivo_de_pasta(self):
        files = mock.Mock()
        files.list.return_value.execute.side_effect = [
            {"files": [{"id": "arquivo"}]},
            {"files": [{"id": "pasta"}]},
            {"files": [{"id": "a", "name": "A"}]},
        ]
        client = _client(files)

        self.assertEqual(client.buscar_arquivo_por_nome("d'água", "pai"), "arquivo")
        self.assertEqual(client.buscar_pasta_por_nome("d'água", "pai"), "pasta")
        self.assertEqual(client.listar_arquivos("pai"), [{"id": "a", "name": "A"}])
        queries = [call.kwargs["q"] for call in files.list.call_args_list]
        self.assertIn("d\\'água", queries[0])
        self.assertIn("mimeType !=", queries[0])
        self.assertIn("mimeType =", queries[1])

    def test_excluir_e_lixeira_nao_propagam_falha_remota(self):
        files = mock.Mock()
        files.delete.return_value.execute.side_effect = RuntimeError("fora")
        files.update.return_value.execute.side_effect = RuntimeError("fora")
        client = _client(files)

        with mock.patch.object(services, "capture") as capture:
            client.excluir_arquivo("file")
            client.mover_para_lixeira("file")

        self.assertEqual(capture.call_count, 2)


class ExpiryParaGoogleAuthTests(SimpleTestCase):
    """google-auth compara `expiry` com `utcnow()` e ignora tzinfo."""

    def test_converte_para_utc_antes_de_tirar_o_fuso(self):
        from datetime import timezone as tz

        saopaulo = tz(timedelta(hours=-3))
        vencimento = datetime(2026, 8, 25, 21, 0, tzinfo=saopaulo)

        convertido = services._expiry_para_google_auth(vencimento)

        self.assertIsNone(convertido.tzinfo)
        self.assertEqual(convertido, datetime(2026, 8, 26, 0, 0))

    def test_valores_naive_e_vazio_passam_direto(self):
        naive = datetime(2026, 8, 25, 21, 0)
        self.assertEqual(services._expiry_para_google_auth(naive), naive)
        self.assertIsNone(services._expiry_para_google_auth(None))
