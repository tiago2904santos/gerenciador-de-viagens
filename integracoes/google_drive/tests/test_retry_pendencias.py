import hashlib
from datetime import date
from unittest.mock import patch

from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.base import ContentFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from cadastros.models import Cargo, Servidor
from core import middleware as core_middleware
from documentos.models import DocumentoArtefato
from eventos.models import Evento, TipoEvento
from oficios.models import Oficio
from integracoes.google_drive import organizer, services, status
from integracoes.google_drive.models import DriveSyncStatus


def _pdf(name):
    raw = b"%PDF-1.4\n%%EOF\n" + name.encode()
    return ContentFile(raw, name=name), hashlib.sha256(raw).hexdigest()


def _request_com_mensagens():
    """Simula uma request real (com sessão/mensagens) na thread local, como o
    CurrentRequestMiddleware faria durante um request HTTP de verdade."""
    request = RequestFactory().get("/")
    request.session = {}
    storage = FallbackStorage(request)
    request._messages = storage
    return request, storage


class ExecutarERastrearTests(TestCase):
    """Testa status.executar_e_rastrear isoladamente (sem Django signals)."""

    def setUp(self):
        cargo = Cargo.objects.create(nome="Investigador")
        self.servidor = Servidor.objects.create(nome="Ana", cargo=cargo, cpf="12345678901")

    def test_falha_cria_pendencia_e_incrementa_tentativas(self):
        def falha(obj):
            raise RuntimeError("Drive fora do ar")

        with self.assertRaises(RuntimeError):
            status.executar_e_rastrear(falha, self.servidor)
        pendencia = DriveSyncStatus.objects.get()
        self.assertEqual(pendencia.tentativas, 1)
        self.assertIn("Drive fora do ar", pendencia.ultimo_erro)

        with self.assertRaises(RuntimeError):
            status.executar_e_rastrear(falha, self.servidor)
        pendencia.refresh_from_db()
        self.assertEqual(pendencia.tentativas, 2)

    def test_sucesso_apaga_pendencia_existente(self):
        status.registrar_falha(self.servidor, RuntimeError("boom"))
        self.assertEqual(DriveSyncStatus.objects.count(), 1)

        status.executar_e_rastrear(lambda obj: None, self.servidor)
        self.assertEqual(DriveSyncStatus.objects.count(), 0)


@override_settings(GOOGLE_DRIVE={"MODO": "mock", "UPLOAD_EM_MOCK": True})
class SignalRetryTests(TestCase):
    """Testa o caminho assíncrono do signal de artefato."""

    def setUp(self):
        services._reset_client()
        cargo = Cargo.objects.create(nome="Investigador")
        self.ana = Servidor.objects.create(nome="Ana", cargo=cargo, cpf="12345678901")
        self.evento = Evento.objects.create(
            destino_cidade="Maringá", destino_uf="PR",
            data_inicio=date(2026, 7, 22), data_fim=date(2026, 7, 23),
        )
        self.evento.tipos.add(TipoEvento.objects.get_or_create(nome="PCPR na Comunidade")[0])
        self.oficio = Oficio.objects.create(
            numero=1, ano=2026, protocolo="123456789", motivo="m", evento=self.evento,
        )
        self.oficio.servidores.add(self.ana)

    def test_criacao_agenda_upload_sem_chamar_drive_sincrono(self):
        arquivo, digest = _pdf("doc.pdf")
        request, storage = _request_com_mensagens()

        core_middleware._local.request = request
        try:
            with patch.object(
                organizer, "organizar_artefato"
            ) as organizar_mock, patch(
                "integracoes.google_drive.tasks.processar_artefato.delay"
            ) as delay_mock:
                with self.captureOnCommitCallbacks(execute=True):
                    art = DocumentoArtefato.objects.create(
                        tipo="oficio", formato="pdf", oficio=self.oficio,
                        hash_sha256=digest, arquivo=arquivo,
                    )
        finally:
            core_middleware._local.request = None

        organizar_mock.assert_not_called()
        delay_mock.assert_called_once_with(art.pk, usuario_id=None)
        self.assertEqual(DriveSyncStatus.objects.count(), 0)
        self.assertEqual(list(storage), [])

    def test_fila_indisponivel_registra_pendencia_e_avisa(self):
        arquivo, digest = _pdf("doc.pdf")
        request, storage = _request_com_mensagens()

        core_middleware._local.request = request
        try:
            with patch(
                "integracoes.google_drive.tasks.processar_artefato.delay",
                side_effect=ConnectionRefusedError("sem broker"),
            ), patch(
                "integracoes.google_drive.organizer.organizar_artefato"
            ) as organizar_mock:
                with self.captureOnCommitCallbacks(execute=True):
                    art = DocumentoArtefato.objects.create(
                        tipo="oficio", formato="pdf", oficio=self.oficio,
                        hash_sha256=digest, arquivo=arquivo,
                    )
        finally:
            core_middleware._local.request = None

        organizar_mock.assert_not_called()
        pendencia = DriveSyncStatus.objects.get()
        self.assertEqual(pendencia.tentativas, 1)
        self.assertIn("sem broker", pendencia.ultimo_erro)

        mensagens = [str(m) for m in storage]
        self.assertTrue(any("ficou pendente" in m for m in mensagens))

    def test_sucesso_nao_cria_pendencia_nem_mensagem(self):
        arquivo, digest = _pdf("doc.pdf")
        request, storage = _request_com_mensagens()

        core_middleware._local.request = request
        try:
            with patch("integracoes.google_drive.tasks.processar_artefato.delay"):
                with self.captureOnCommitCallbacks(execute=True):
                    DocumentoArtefato.objects.create(
                        tipo="oficio", formato="pdf", oficio=self.oficio,
                        hash_sha256=digest, arquivo=arquivo,
                    )
        finally:
            core_middleware._local.request = None

        self.assertEqual(DriveSyncStatus.objects.count(), 0)
        self.assertEqual(list(storage), [])

    def test_fila_indisponivel_nao_derruba_o_save(self):
        """Se nem o Celery consegue enfileirar (broker fora do ar), o objeto
        continua salvo e só fica marcado como pendência."""
        arquivo, digest = _pdf("doc.pdf")
        request, _storage = _request_com_mensagens()

        core_middleware._local.request = request
        try:
            with patch(
                "integracoes.google_drive.tasks.processar_artefato.delay",
                side_effect=ConnectionRefusedError("sem broker"),
            ):
                with self.captureOnCommitCallbacks(execute=True):
                    art = DocumentoArtefato.objects.create(
                        tipo="oficio", formato="pdf", oficio=self.oficio,
                        hash_sha256=digest, arquivo=arquivo,
                    )
        finally:
            core_middleware._local.request = None

        self.assertTrue(DocumentoArtefato.objects.filter(pk=art.pk).exists())
        self.assertEqual(DriveSyncStatus.objects.count(), 1)


@override_settings(GOOGLE_DRIVE={"MODO": "mock", "UPLOAD_EM_MOCK": True, "REORG_SINCRONO": True})
class PainelPendenciasViewTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        services._reset_client()
        self.user = get_user_model().objects.create_user(username="u_pend", password="x" * 12)
        self.client.force_login(self.user)
        cargo = Cargo.objects.create(nome="Investigador")
        ana = Servidor.objects.create(nome="Ana", cargo=cargo, cpf="12345678901")
        evento = Evento.objects.create(
            destino_cidade="Maringá", destino_uf="PR",
            data_inicio=date(2026, 7, 22), data_fim=date(2026, 7, 23),
        )
        evento.tipos.add(TipoEvento.objects.get_or_create(nome="PCPR na Comunidade")[0])
        self.oficio = Oficio.objects.create(
            numero=1, ano=2026, protocolo="123456789", motivo="m", evento=evento,
        )
        self.oficio.servidores.add(ana)
        arquivo, digest = _pdf("doc.pdf")
        self.art = DocumentoArtefato.objects.create(
            tipo="oficio", formato="pdf", oficio=self.oficio,
            hash_sha256=digest, arquivo=arquivo,
        )
        status.registrar_falha(self.art, RuntimeError("Drive fora do ar"), usuario=self.user)

    def test_card_de_pendencias_aparece_na_tela(self):
        resp = self.client.get(reverse("core:perfil"))
        self.assertContains(resp, "Pendências")
        self.assertContains(resp, "Tentar novamente agora")

    def test_reprocessar_agenda_tasks_pendentes(self):
        with patch(
            "integracoes.google_drive.tasks.processar_artefato.delay"
        ) as delay_mock:
            resp = self.client.post(reverse("google_drive:reprocessar_pendencias"))
        self.assertRedirects(resp, reverse("core:perfil"))
        # object_id fica salvo como string em DriveSyncStatus (pk pode ser UUID ou int).
        delay_mock.assert_called_once_with(str(self.art.pk), usuario_id=self.user.pk)
