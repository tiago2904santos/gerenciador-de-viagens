"""A pasta raiz precisa ser um destino válido antes de qualquer envio.

`NOVO-20260825-205014-1843068b6d33`. Medido em produção em 07/07/2026: a raiz
configurada (`VIAGENS`) estava na lixeira do Drive. Como o Drive aceita criar
filhos dentro de uma pasta lixeirada, e como as buscas do organizador filtram
`trashed = false` (logo não reencontram nada lá dentro), o sistema recriava a
árvore inteira a cada envio e reportava sucesso — com todos os documentos
invisíveis para o usuário.
"""

from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from integracoes.google_drive import organizer, services


def _cfg_mock(**extra):
    return {"MODO": "mock", "UPLOAD_EM_MOCK": True, **extra}


class EstadoPastaRaizTests(SimpleTestCase):
    def setUp(self):
        services._reset_client()
        self.addCleanup(services._reset_client)

    @override_settings(GOOGLE_DRIVE=_cfg_mock())
    @mock.patch.object(services, "get_credenciais", return_value=None)
    def test_sem_raiz_escolhida_o_estado_aponta_a_configuracao(self, _creds):
        estado = services.estado_pasta_raiz()

        self.assertFalse(estado.ok)
        self.assertFalse(estado.configurada)
        self.assertIn("Nenhuma pasta raiz escolhida", estado.motivo)

    @override_settings(GOOGLE_DRIVE=_cfg_mock(PASTA_RAIZ_ID="raiz"))
    @mock.patch.object(services, "get_credenciais", return_value=None)
    def test_raiz_saudavel(self, _creds):
        estado = services.estado_pasta_raiz()

        self.assertTrue(estado.ok)
        self.assertEqual(estado.pasta_id, "raiz")
        self.assertEqual(services.validar_pasta_raiz(), "raiz")

    @override_settings(GOOGLE_DRIVE=_cfg_mock(PASTA_RAIZ_ID="raiz"))
    @mock.patch.object(services, "get_credenciais", return_value=None)
    def test_raiz_na_lixeira_reprova_com_motivo_legivel(self, _creds):
        cliente = services.get_client()
        with mock.patch.object(
            cliente, "inspecionar_pasta", return_value={"name": "VIAGENS", "trashed": True}
        ):
            estado = services.estado_pasta_raiz()

            self.assertFalse(estado.ok)
            self.assertIn("LIXEIRA", estado.motivo)
            self.assertIn("VIAGENS", estado.motivo)
            with self.assertRaises(services.DriveRaizInvalidaError):
                services.validar_pasta_raiz()

    @override_settings(GOOGLE_DRIVE=_cfg_mock(PASTA_RAIZ_ID="raiz"))
    @mock.patch.object(services, "get_credenciais", return_value=None)
    def test_raiz_sem_permissao_de_escrita_reprova(self, _creds):
        cliente = services.get_client()
        meta = {
            "name": "Compartilhada",
            "trashed": False,
            "mimeType": services._FOLDER_MIME,
            "capabilities": {"canAddChildren": False},
        }
        with mock.patch.object(cliente, "inspecionar_pasta", return_value=meta):
            estado = services.estado_pasta_raiz()

        self.assertFalse(estado.ok)
        self.assertIn("permissão de escrita", estado.motivo)

    @override_settings(GOOGLE_DRIVE=_cfg_mock(PASTA_RAIZ_ID="raiz"))
    @mock.patch.object(services, "get_credenciais", return_value=None)
    def test_raiz_que_nao_e_pasta_reprova(self, _creds):
        cliente = services.get_client()
        meta = {"name": "planilha.xlsx", "trashed": False, "mimeType": "application/vnd.ms-excel"}
        with mock.patch.object(cliente, "inspecionar_pasta", return_value=meta):
            estado = services.estado_pasta_raiz()

        self.assertFalse(estado.ok)
        self.assertIn("não é uma pasta", estado.motivo)

    @override_settings(GOOGLE_DRIVE=_cfg_mock(PASTA_RAIZ_ID="raiz"))
    @mock.patch.object(services, "get_credenciais", return_value=None)
    def test_erro_de_rede_nao_escapa_do_diagnostico(self, _creds):
        cliente = services.get_client()
        with mock.patch.object(
            cliente, "inspecionar_pasta", side_effect=RuntimeError("timeout")
        ):
            with mock.patch.object(services, "capture") as capture:
                estado = services.estado_pasta_raiz()

        self.assertFalse(estado.ok)
        self.assertIn("timeout", estado.motivo)
        capture.assert_called_once()

    @override_settings(GOOGLE_DRIVE=_cfg_mock(PASTA_RAIZ_ID="raiz", PASTA_CACHE_TTL_SECONDS=300))
    @mock.patch.object(services, "get_credenciais", return_value=None)
    def test_estado_e_cacheado_dentro_da_validade(self, _creds):
        cliente = services.get_client()
        with mock.patch.object(
            cliente, "inspecionar_pasta", return_value={"name": "VIAGENS", "trashed": False}
        ) as inspecionar:
            services.estado_pasta_raiz()
            services.estado_pasta_raiz()
            self.assertEqual(inspecionar.call_count, 1)

            # `usar_cache=False` é o caminho do diagnóstico: precisa ver o agora.
            services.estado_pasta_raiz(usar_cache=False)
            self.assertEqual(inspecionar.call_count, 2)


@override_settings(GOOGLE_DRIVE=_cfg_mock(PASTA_RAIZ_ID="raiz"))
class OrganizerRecusaRaizInvalidaTests(TestCase):
    """O portão está em `_raiz()`, por onde passa todo destino do organizador."""

    def setUp(self):
        services._reset_client()
        self.addCleanup(services._reset_client)

    def test_raiz_na_lixeira_interrompe_em_vez_de_encher_a_lixeira(self):
        cliente = services.get_client()
        with mock.patch.object(
            cliente, "inspecionar_pasta", return_value={"name": "VIAGENS", "trashed": True}
        ):
            with mock.patch.object(cliente, "get_or_create_pasta") as criar:
                with self.assertRaises(services.DriveRaizInvalidaError):
                    organizer._raiz()

        criar.assert_not_called()

    def test_raiz_saudavel_libera_o_caminho(self):
        self.assertEqual(organizer._raiz(), "raiz")

    @override_settings(GOOGLE_DRIVE=_cfg_mock())
    def test_sem_raiz_configurada_mantem_o_comportamento_antigo(self):
        """Instalação sem raiz escolhida monta a árvore na raiz da conta, como antes."""
        self.assertIsNone(organizer._raiz())
