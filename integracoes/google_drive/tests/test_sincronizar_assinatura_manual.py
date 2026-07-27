import hashlib
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from cadastros.models import Cargo, Servidor
from documentos.models import DocumentoArtefato
from oficios.models import Oficio
from integracoes.google_drive import organizer, services
from integracoes.google_drive.models import DriveArquivo


def _pdf(name):
    raw = b"%PDF-1.4\n%%EOF\n" + name.encode()
    return ContentFile(raw, name=name), hashlib.sha256(raw).hexdigest()


@override_settings(GOOGLE_DRIVE={"MODO": "mock", "UPLOAD_EM_MOCK": True})
class SincronizarConteudoAssinadoTests(TestCase):
    def setUp(self):
        services._reset_client()
        self.cargo = Cargo.objects.create(nome="Cargo Sync")
        self.ana = Servidor.objects.create(nome="Ana Sync", cargo=self.cargo, cpf="11122233344")
        self.oficio = Oficio.objects.create(numero=2, ano=2026, protocolo="223456789", motivo="m")
        self.oficio.servidores.add(self.ana)

    def _artefato(self):
        arquivo, digest = _pdf("termo.pdf")
        with self.captureOnCommitCallbacks(execute=True):
            return DocumentoArtefato.objects.create(
                tipo="termo_autorizacao",
                formato="pdf",
                oficio=self.oficio,
                servidor=self.ana,
                hash_sha256=digest,
                arquivo=arquivo,
            )

    def test_cria_no_drive_quando_ainda_nao_organizado(self):
        art = self._artefato()
        result = organizer.sincronizar_conteudo_assinado(art)
        self.assertIsNotNone(result)
        self.assertTrue(DriveArquivo.objects.filter(artefato=art).exists())

    def test_forca_atualizar_conteudo_em_vez_de_so_renomear(self):
        """Quando já existe um DriveArquivo "real" (não-mock), anexar assinado deve
        reenviar o conteúdo (``atualizar_conteudo``) em vez de só renomear/ignorar —
        o comportamento normal do organizer assume que artefato já organizado não
        muda de conteúdo, o que deixaria de valer aqui."""
        art = self._artefato()
        # A criação do artefato já disparou o signal e organizou (mock) automaticamente;
        # aqui simulamos que aquele upload foi "real" (não-mock), com um file_id fixo.
        reg = DriveArquivo.objects.get(artefato=art)
        reg.file_id = "existing-file-id"
        reg.mock = False
        reg.save(update_fields=["file_id", "mock"])

        art.arquivo_assinado.save("assinado.pdf", ContentFile(b"%PDF-1.4\nASSINADO\n%%EOF\n"), save=True)

        with patch.object(
            services._MockClient, "atualizar_conteudo", autospec=True,
        ) as m_atualizar:
            m_atualizar.return_value = ("existing-file-id", "https://drive/existing")
            organizer.sincronizar_conteudo_assinado(art)

        m_atualizar.assert_called_once()
        _self, file_id_arg, *_rest = m_atualizar.call_args.args
        self.assertEqual(file_id_arg, "existing-file-id")

    def test_prefere_arquivo_assinado_ao_ler_conteudo(self):
        art = self._artefato()
        art.arquivo_assinado.save("assinado.pdf", ContentFile(b"%PDF-1.4\nASSINADO\n%%EOF\n"), save=True)
        organizer.organizar_artefato(art)
        reg = DriveArquivo.objects.get(artefato=art)
        self.assertTrue(reg.file_id)
