import hashlib
from datetime import date

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from cadastros.models import Cargo, Servidor
from documentos.models import DocumentoArtefato
from eventos.models import Evento
from eventos.models import TipoEvento
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
            destino_cidade="Maringá",
            destino_uf="PR",
            data_inicio=date(2026, 7, 22),
            data_fim=date(2026, 7, 23),
        )
        self.evento.tipos.add(TipoEvento.objects.get_or_create(nome="PCPR na Comunidade")[0])
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
        """O CANÔNICO (arquivo real) fica sempre na pasta global do tipo, tenha
        evento ou não — dentro de Eventos/ existe apenas um atalho."""
        self._artefato("oficio")
        linhas = organizer.planejar_oficio(self.oficio)
        self.assertIn(
            "Ofícios/Ofício 01 protocolo 12.345.678-9 Ana e Bruno (Maringá)/"
            "Ofício 01-2026 protocolo 12.345.678-9 Ana e Bruno (Maringá).pdf",
            linhas,
        )

    def test_os_e_plano_canonicos_ficam_na_pasta_global_do_tipo(self):
        """OS e plano: o CANÔNICO vive em Ordens de serviço/Planos de trabalho
        (pasta global) — dentro do evento existe só um atalho, no nível do
        evento (não dentro da pasta do ofício)."""
        art_os = self._artefato("ordem_servico", name="os.pdf")
        art_plano = self._artefato("plano_trabalho", name="plano.pdf")
        linhas = organizer.planejar_oficio(self.oficio)
        self.assertTrue(any(l.startswith("Ordens de serviço/") for l in linhas), linhas)
        self.assertTrue(any(l.startswith("Planos de trabalho/") for l in linhas), linhas)

        organizer.organizar_artefato(art_os)
        reg_os = DriveArquivo.objects.get(artefato=art_os)
        self.assertTrue(reg_os.atalho_id)
        client = services.get_client()
        pasta_evento_id = organizer._pasta_evento_folder(client, self.evento)
        self.assertEqual(reg_os.atalho_pasta_id, pasta_evento_id)

    def test_oficio_sem_evento_vai_para_pasta_de_tipo(self):
        self.oficio.evento = None
        self.oficio.save()
        art = self._artefato("oficio")
        organizer.organizar_artefato(art)
        linhas = organizer.planejar_oficio(self.oficio)
        self.assertTrue(any(linha.startswith("Ofícios/") for linha in linhas))
        self.assertFalse(any("Avulsos" in linha for linha in linhas))
