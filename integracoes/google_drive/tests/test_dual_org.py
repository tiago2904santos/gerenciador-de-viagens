import hashlib
from datetime import date

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from cadastros.models import Cargo, Servidor
from documentos.models import DocumentoArtefato
from eventos.models import Evento
from oficios.models import Oficio
from prestacoes_contas.models import PrestacaoContas
from integracoes.google_drive import organizer, services
from integracoes.google_drive.models import DriveArquivo, DriveArquivoExterno


def _pdf(name="d.pdf"):
    raw = b"%PDF-1.4\n%%EOF\n" + name.encode()
    return ContentFile(raw, name=name), hashlib.sha256(raw).hexdigest()


@override_settings(GOOGLE_DRIVE={"MODO": "mock", "UPLOAD_EM_MOCK": True})
class DualOrganizationTests(TestCase):
    def setUp(self):
        services._reset_client()
        self.cargo = Cargo.objects.create(nome="Investigador")
        self.ana = Servidor.objects.create(nome="Ana", cargo=self.cargo, cpf="12345678901")
        self.evento = Evento.objects.create(
            tipo=Evento.TIPO_PCPR_COMUNIDADE, destino_cidade="Maringá", destino_uf="PR",
            data_inicio=date(2026, 7, 22), data_fim=date(2026, 7, 23),
        )
        self.oficio = Oficio.objects.create(
            numero=1, ano=2026, protocolo="123456789", motivo="m", evento=self.evento,
        )
        self.oficio.servidores.add(self.ana)

    def _art(self, tipo, *, evento=None, oficio=None, nome_drive="", name="d.pdf"):
        arquivo, digest = _pdf(name)
        return DocumentoArtefato.objects.create(
            tipo=tipo, formato="pdf", oficio=oficio, evento=evento,
            nome_drive=nome_drive, hash_sha256=digest, arquivo=arquivo,
        )

    def test_artefato_com_evento_cria_atalho_global(self):
        art = self._art("oficio", oficio=self.oficio)
        organizer.organizar_artefato(art)
        reg = DriveArquivo.objects.get(artefato=art)
        self.assertTrue(reg.atalho_id, "deveria ter criado atalho na pasta de tipo global")
        self.assertTrue(reg.atalho_pasta_id)

    def test_artefato_sem_evento_nao_cria_atalho(self):
        self.oficio.evento = None
        self.oficio.save()
        art = self._art("oficio", oficio=self.oficio)
        organizer.organizar_artefato(art)
        reg = DriveArquivo.objects.get(artefato=art)
        self.assertEqual(reg.atalho_id, "")

    def test_plano_usa_nome_drive(self):
        nome = "Plano de trabalho 05-2026 (Maringá).pdf"
        art = self._art("plano_trabalho", evento=self.evento, oficio=self.oficio, nome_drive=nome, name="plano.pdf")
        organizer.organizar_artefato(art)
        reg = DriveArquivo.objects.get(artefato=art)
        self.assertEqual(reg.nome, nome)
        self.assertTrue(reg.atalho_id)

    def test_idempotente_atalho_e_arquivo(self):
        art = self._art("oficio", oficio=self.oficio)
        organizer.organizar_artefato(art)
        primeiro = DriveArquivo.objects.get(artefato=art)
        atalho1 = primeiro.atalho_id
        organizer.organizar_artefato(art)
        self.assertEqual(DriveArquivo.objects.filter(artefato=art).count(), 1)
        self.assertEqual(DriveArquivo.objects.get(artefato=art).atalho_id, atalho1)

    def test_prestacao_cria_atalho_de_pasta_global(self):
        arquivo, _ = _pdf("despacho.pdf")
        prest = (
            PrestacaoContas.objects.filter(oficio=self.oficio, servidor=self.ana).first()
            or PrestacaoContas(oficio=self.oficio, servidor=self.ana)
        )
        prest.despacho_assinado = arquivo
        prest.save()
        organizer.organizar_prestacao(prest)
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(PrestacaoContas)
        self.assertTrue(
            DriveArquivoExterno.objects.filter(
                content_type=ct, object_id=prest.pk, campo="atalho_prestacao"
            ).exists()
        )
        # E o despacho em si foi enviado.
        self.assertTrue(
            DriveArquivoExterno.objects.filter(
                content_type=ct, object_id=prest.pk, campo="despacho_assinado"
            ).exists()
        )

    def test_planejar_mostra_pastas_de_tipo_sem_evento(self):
        self.oficio.evento = None
        self.oficio.save()
        self._art("ordem_servico", oficio=self.oficio, name="os.pdf")
        linhas = organizer.planejar_oficio(self.oficio)
        self.assertTrue(any(l.startswith("Ordens de serviço/") for l in linhas))
