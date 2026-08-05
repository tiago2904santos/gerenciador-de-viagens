import hashlib
from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from cadastros.models import Cargo, Servidor
from documentos.models import DocumentoArtefato
from eventos.models import Evento
from eventos.models import TipoEvento
from oficios.models import Oficio
from integracoes.google_drive import services
from integracoes.google_drive.models import (
    DriveArquivo,
    DriveCredenciais,
    DriveReorganizacaoJob,
)


# REORG_SINCRONO força a reorganização a rodar inline (sem thread) nos testes.
@override_settings(GOOGLE_DRIVE={"MODO": "mock", "UPLOAD_EM_MOCK": True, "REORG_SINCRONO": True})
class ReorganizarTudoViewTests(TestCase):
    def setUp(self):
        services._reset_client()
        self.user = get_user_model().objects.create_user(username="u_reorg", password="x" * 12)
        self.client.force_login(self.user)
        # Pasta raiz configurada (mock) — habilita o card e a ação.
        DriveCredenciais.objects.create(
            usuario=self.user,
            access_token="t", refresh_token="r", pasta_raiz_id="mock-raiz", pasta_raiz_nome="Raiz",
        )
        cargo = Cargo.objects.create(nome="Investigador")
        ana = Servidor.objects.create(nome="Ana", cargo=cargo, cpf="12345678901")
        self.evento = Evento.objects.create(
            destino_cidade="Maringá", destino_uf="PR",
            data_inicio=date(2026, 7, 22), data_fim=date(2026, 7, 23),
        )
        self.evento.tipos.add(TipoEvento.objects.get_or_create(nome="PCPR na Comunidade")[0])
        self.oficio = Oficio.objects.create(
            numero=1, ano=2026, protocolo="123456789", motivo="m", evento=self.evento,
        )
        self.oficio.servidores.add(ana)
        raw = b"%PDF-1.4\n%%EOF\n"
        DocumentoArtefato.objects.create(
            tipo="oficio", formato="pdf", oficio=self.oficio,
            hash_sha256=hashlib.sha256(raw).hexdigest(),
            arquivo=ContentFile(raw, name="oficio_feio.pdf"),
        )

    def test_card_aparece_quando_pode_reorganizar(self):
        resp = self.client.get(reverse("core:perfil"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Organização em massa")
        self.assertContains(resp, "Reorganizar tudo no Drive")

    def test_post_reorganiza_e_cria_drive_arquivo(self):
        resp = self.client.post(reverse("google_drive:reorganizar_tudo"))
        self.assertRedirects(resp, reverse("core:perfil"))
        reg = DriveArquivo.objects.get(artefato__oficio=self.oficio)
        self.assertEqual(
            reg.nome, "Ofício 01-2026 protocolo 12.345.678-9 Ana (Maringá).pdf"
        )

    def test_post_cria_job_e_conclui(self):
        self.client.post(reverse("google_drive:reorganizar_tudo"))
        job = DriveReorganizacaoJob.objects.order_by("-iniciado_em").first()
        self.assertIsNotNone(job)
        self.assertEqual(job.usuario, self.user)
        self.assertEqual(job.status, DriveReorganizacaoJob.STATUS_CONCLUIDA)
        self.assertIsNotNone(job.finalizado_em)

    def test_status_endpoint_reflete_job(self):
        self.client.post(reverse("google_drive:reorganizar_tudo"))
        resp = self.client.get(reverse("google_drive:status_reorganizacao"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["existe"])
        self.assertEqual(data["status"], "concluida")
        self.assertFalse(data["em_andamento"])

    def test_nao_inicia_se_ja_em_andamento(self):
        DriveReorganizacaoJob.objects.create(
            usuario=self.user,
            status=DriveReorganizacaoJob.STATUS_EM_ANDAMENTO,
        )
        resp = self.client.post(reverse("google_drive:reorganizar_tudo"))
        self.assertRedirects(resp, reverse("core:perfil"))
        # Não cria um segundo job em andamento.
        self.assertEqual(
            DriveReorganizacaoJob.objects.filter(
                status=DriveReorganizacaoJob.STATUS_EM_ANDAMENTO
            ).count(),
            1,
        )

    def test_previa_lista_caminhos(self):
        resp = self.client.get(reverse("google_drive:previa_reorganizacao"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["truncado"])
        self.assertTrue(
            any("Ofício 01-2026 protocolo 12.345.678-9 Ana (Maringá).pdf" in linha for linha in data["linhas"])
        )

    def test_get_index_sem_pasta_nao_mostra_card(self):
        DriveCredenciais.objects.update(pasta_raiz_id="")
        services._reset_client()
        resp = self.client.get(reverse("core:perfil"))
        self.assertNotContains(resp, "Organização em massa")
