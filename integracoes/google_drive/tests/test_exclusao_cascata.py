import hashlib
from datetime import date
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from documentos.models import DocumentoArtefato
from eventos.models import Evento, EventoAnexo
from integracoes.google_drive import services
from integracoes.google_drive.models import DriveArquivo, DriveArquivoExterno
from oficios.models import Oficio


def _pdf(name):
    raw = b"%PDF-1.4\n%%EOF\n" + name.encode()
    return ContentFile(raw, name=name), hashlib.sha256(raw).hexdigest()


@override_settings(GOOGLE_DRIVE={"MODO": "mock", "UPLOAD_EM_MOCK": True})
class ExclusaoEventoCascataTests(TestCase):
    """Excluir um Evento deve excluir os documentos vinculados (nunca só desvincular)."""

    def setUp(self):
        services._reset_client()
        self.evento = Evento.objects.create(
            titulo="Evento de teste", destino_cidade="Curitiba", data_inicio=date(2026, 7, 3),
        )
        self.oficio = Oficio.objects.create(evento=self.evento, assunto="Assunto teste")
        arquivo, hash_ = _pdf("oficio.pdf")
        self.artefato = DocumentoArtefato.objects.create(
            tipo="oficio", formato="pdf", oficio=self.oficio, evento=self.evento,
            hash_sha256=hash_, arquivo=arquivo,
        )

    def test_excluir_evento_exclui_oficio_e_artefato(self):
        oficio_pk, artefato_pk = self.oficio.pk, self.artefato.pk
        self.evento.delete()
        self.assertFalse(Oficio.objects.filter(pk=oficio_pk).exists())
        self.assertFalse(DocumentoArtefato.objects.filter(pk=artefato_pk).exists())

    def test_excluir_evento_move_artefato_para_lixeira_no_drive(self):
        self.artefato.refresh_from_db()
        file_id = self.artefato.drive_arquivo.file_id
        self.assertTrue(file_id)
        with patch("integracoes.google_drive.services._MockClient.mover_para_lixeira") as mock_lixeira:
            self.evento.delete()
        mock_lixeira.assert_any_call(file_id)

    def test_excluir_evento_move_pasta_do_evento_para_lixeira_no_drive(self):
        self.evento.refresh_from_db()
        pasta_id = self.evento.drive_folder_id
        self.assertTrue(pasta_id)
        with patch("integracoes.google_drive.services._MockClient.mover_para_lixeira") as mock_lixeira:
            self.evento.delete()
        mock_lixeira.assert_any_call(pasta_id)

    def test_excluir_evento_sem_dados_completos_nao_mexe_no_drive(self):
        """Evento que nunca teve dados suficientes (Etapa 1) nunca ganhou pasta
        própria — excluir não deve criar nem tentar trashear nada por ele."""
        evento_vazio = Evento.objects.create()
        self.assertEqual(evento_vazio.drive_folder_id, "")
        with patch("integracoes.google_drive.services._MockClient.mover_para_lixeira") as mock_lixeira, patch(
            "integracoes.google_drive.services._MockClient.get_or_create_pasta"
        ) as mock_create:
            evento_vazio.delete()
        mock_lixeira.assert_not_called()
        mock_create.assert_not_called()


@override_settings(GOOGLE_DRIVE={"MODO": "mock", "UPLOAD_EM_MOCK": True})
class ExclusaoDocumentoLimpaDriveTests(TestCase):
    """Excluir qualquer documento rastreado deve mover o arquivo correspondente no Drive para a lixeira."""

    def setUp(self):
        services._reset_client()
        self.evento = Evento.objects.create(titulo="Evento de teste")

    def test_excluir_artefato_move_arquivo_e_remove_registro_drive(self):
        arquivo, hash_ = _pdf("plano.pdf")
        artefato = DocumentoArtefato.objects.create(
            tipo="plano_trabalho", formato="pdf", evento=self.evento, hash_sha256=hash_, arquivo=arquivo,
        )
        artefato.refresh_from_db()
        file_id = artefato.drive_arquivo.file_id
        self.assertTrue(file_id)

        with patch("integracoes.google_drive.services._MockClient.mover_para_lixeira") as mock_lixeira:
            artefato.delete()
            mock_lixeira.assert_any_call(file_id)

        self.assertFalse(DriveArquivo.objects.filter(file_id=file_id).exists())

    def test_excluir_evento_anexo_move_arquivo_e_remove_registro_externo(self):
        anexo = EventoAnexo.objects.create(
            evento=self.evento, tipo=EventoAnexo.TIPO_CONVITE,
            arquivo=ContentFile(b"conteudo", name="convite.pdf"),
        )
        ct = ContentType.objects.get_for_model(EventoAnexo)
        reg = DriveArquivoExterno.objects.get(content_type=ct, object_id=anexo.pk, campo="arquivo")
        file_id = reg.file_id
        self.assertTrue(file_id)

        with patch("integracoes.google_drive.services._MockClient.mover_para_lixeira") as mock_lixeira:
            anexo.delete()
            mock_lixeira.assert_called_once_with(file_id)

        self.assertFalse(DriveArquivoExterno.objects.filter(pk=reg.pk).exists())

    def test_drive_desligado_nao_chama_api(self):
        with override_settings(GOOGLE_DRIVE={"MODO": "mock", "UPLOAD_EM_MOCK": False}):
            arquivo, hash_ = _pdf("plano2.pdf")
            artefato = DocumentoArtefato.objects.create(
                tipo="plano_trabalho", formato="pdf", evento=self.evento, hash_sha256=hash_, arquivo=arquivo,
            )
            DriveArquivo.objects.create(artefato=artefato, file_id="mock-plano-2", nome="plano2.pdf", mock=True)

            with patch("integracoes.google_drive.services._MockClient.mover_para_lixeira") as mock_lixeira:
                artefato.delete()
                mock_lixeira.assert_not_called()
