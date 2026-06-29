import hashlib
from datetime import date

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from cadastros.models import Cargo, Servidor
from documentos.models import DocumentoArtefato
from eventos.models import Evento
from oficios.models import Oficio
from integracoes.google_drive import organizer, services
from integracoes.google_drive.models import DriveArquivo


def _pdf(name):
    raw = b"%PDF-1.4\n%%EOF\n" + name.encode()
    return ContentFile(raw, name=name), hashlib.sha256(raw).hexdigest()


@override_settings(GOOGLE_DRIVE={"MODO": "mock", "UPLOAD_EM_MOCK": True})
class OrganizerTests(TestCase):
    def setUp(self):
        services._reset_client()
        self.cargo = Cargo.objects.create(nome="Investigador")
        self.ana = Servidor.objects.create(nome="Ana", cargo=self.cargo, cpf="12345678901")
        self.bruno = Servidor.objects.create(nome="Bruno", cargo=self.cargo, cpf="98765432100")
        self.evento = Evento.objects.create(
            tipo=Evento.TIPO_PCPR_COMUNIDADE,
            destino_cidade="Maringá",
            destino_uf="PR",
            data_inicio=date(2026, 7, 22),
            data_fim=date(2026, 7, 23),
        )
        self.oficio = Oficio.objects.create(
            numero=1, ano=2026, protocolo="123456789", motivo="m", evento=self.evento,
        )
        self.oficio.servidores.add(self.ana, self.bruno)

    def _artefato(self, tipo, servidor=None, name="doc.pdf"):
        arquivo, digest = _pdf(name)
        return DocumentoArtefato.objects.create(
            tipo=tipo, formato="pdf", oficio=self.oficio, servidor=servidor,
            hash_sha256=digest, arquivo=arquivo,
        )

    def test_artefato_oficio_recebe_nome_bonito(self):
        art = self._artefato("oficio", name="oficio_feio_123.pdf")
        result = organizer.organizar_artefato(art)
        self.assertIsNotNone(result)
        reg = DriveArquivo.objects.get(artefato=art)
        self.assertEqual(
            reg.nome, "Ofício 01-2026 protocolo 12.345.678-9 Ana e Bruno (Maringá).pdf"
        )

    def test_termo_usa_servidor_do_artefato(self):
        art = self._artefato("termo_autorizacao", servidor=self.ana, name="termo.pdf")
        organizer.organizar_artefato(art)
        reg = DriveArquivo.objects.get(artefato=art)
        self.assertEqual(
            reg.nome, "Termo de autorização 01-2026 protocolo 12.345.678-9 Ana (Maringá).pdf"
        )

    def test_idempotente_nao_duplica(self):
        art = self._artefato("oficio")
        organizer.organizar_artefato(art)
        organizer.organizar_artefato(art)
        self.assertEqual(DriveArquivo.objects.filter(artefato=art).count(), 1)

    def test_planejar_oficio_monta_arvore(self):
        self._artefato("oficio")
        linhas = organizer.planejar_oficio(self.oficio)
        self.assertIn(
            "Eventos/PCPR na Comunidade - Maringá - 22 a 23 jul 2026/"
            "Ofício 01 protocolo 12.345.678-9 Ana e Bruno/"
            "Ofício 01-2026 protocolo 12.345.678-9 Ana e Bruno (Maringá).pdf",
            linhas,
        )

    def test_oficio_sem_evento_vai_para_avulsos(self):
        self.oficio.evento = None
        self.oficio.save()
        art = self._artefato("oficio")
        organizer.organizar_artefato(art)
        linhas = organizer.planejar_oficio(self.oficio)
        self.assertTrue(any(linha.startswith("Avulsos/") for linha in linhas))
