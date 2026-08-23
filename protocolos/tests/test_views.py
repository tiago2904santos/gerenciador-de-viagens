"""Testes de views da Central de Protocolos (modo mock)."""

from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from oficios.models import Oficio
from protocolos import services
from protocolos.models import Protocolo


class BaseViewTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="op", password="x12345678")
        self.client.force_login(self.user)


class ListaDetalheTests(BaseViewTest):
    def test_lista_carrega(self):
        resp = self.client.get(reverse("protocolos:index"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Central de Protocolos")

    def test_lista_carrega_sem_credenciais_sem_erro(self):
        # Garante que ausência de credenciais não gera 500.
        resp = self.client.get(reverse("protocolos:index"))
        self.assertEqual(resp.status_code, 200)

    def test_detalhe_carrega(self):
        protocolo = services.vincular_protocolo_manual("24.10.10-1", assunto="X")
        resp = self.client.get(reverse("protocolos:detail", args=[protocolo.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "24.10.10-1")

    def test_detalhe_inexistente_404(self):
        resp = self.client.get(reverse("protocolos:detail", args=[999999]))
        self.assertEqual(resp.status_code, 404)

    def test_lista_mock_exibe_protocolos_demo(self):
        resp = self.client.get(reverse("protocolos:index"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "24.123.456-7")
        self.assertContains(resp, "Oficio no 012/2026")
        self.assertContains(resp, "Ambiente: Treinamento")

    def test_detalhe_demo_exibe_secoes_operacionais(self):
        services.garantir_protocolos_demo_treinamento()
        protocolo = Protocolo.objects.get(numero="24.123.456-7")
        resp = self.client.get(reverse("protocolos:detail", args=[protocolo.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Documentos")
        self.assertContains(resp, "Assinaturas")
        self.assertContains(resp, "Pendencias")
        self.assertContains(resp, "Tramitacoes")
        self.assertContains(resp, "Movimentacoes")
        self.assertContains(resp, "Logs de integracao")
        self.assertContains(resp, "Nenhuma acao foi enviada ao eProtocolo real")


class CriacaoVinculoTests(BaseViewTest):
    def test_get_novo(self):
        resp = self.client.get(reverse("protocolos:novo"))
        self.assertEqual(resp.status_code, 200)

    def test_post_novo_cria_manual(self):
        # O número é normalizado para dígitos (convenção do sistema, como em Oficio.protocolo).
        resp = self.client.post(reverse("protocolos:novo"), {
            "numero": "24.205.205-2", "assunto": "Manual", "descricao": "Teste",
        })
        self.assertEqual(resp.status_code, 302)
        protocolo = Protocolo.objects.get(numero="242052052")
        self.assertEqual(protocolo.numero_display, "24.205.205-2")

    def test_vincular_get_confirmacao(self):
        oficio = Oficio.objects.create(numero=5, ano=2026)
        ct = ContentType.objects.get_for_model(Oficio)
        resp = self.client.get(reverse("protocolos:vincular"), {
            "content_type_id": ct.id, "object_id": oficio.pk,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Gerar protocolo")

    def test_vincular_post_cria_de_documento(self):
        oficio = Oficio.objects.create(numero=6, ano=2026)
        ct = ContentType.objects.get_for_model(Oficio)
        resp = self.client.post(reverse("protocolos:vincular"), {
            "content_type_id": ct.id, "object_id": oficio.pk, "enviar_documento": "0",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            Protocolo.objects.filter(origem_content_type=ct, origem_object_id=oficio.pk).exists()
        )


class AcoesTests(BaseViewTest):
    def setUp(self):
        super().setUp()
        self.protocolo = services.vincular_protocolo_manual("24.30.30-3")

    def test_atualizar_get_confirma_post_sincroniza(self):
        url = reverse("protocolos:atualizar", args=[self.protocolo.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.protocolo.refresh_from_db()
        self.assertIsNotNone(self.protocolo.ultima_sincronizacao_em)

    def test_movimentacoes_e_logs(self):
        self.assertEqual(
            self.client.get(reverse("protocolos:movimentacoes", args=[self.protocolo.pk])).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse("protocolos:logs", args=[self.protocolo.pk])).status_code, 200
        )

    def test_solicitar_assinatura_post(self):
        resp = self.client.post(reverse("protocolos:solicitar_assinatura", args=[self.protocolo.pk]), {
            "cpf": "111.444.777-35", "nome": "Fulano",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(self.protocolo.assinaturas.exists())

    def test_tramitar_post(self):
        resp = self.client.post(reverse("protocolos:tramitar", args=[self.protocolo.pk]), {
            "cod_local_para": "0002", "nome_local_para": "Setor B", "parecer": "ok",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(self.protocolo.tramitacoes.exists())

    def test_acoes_mock_nao_chamam_client_real(self):
        with mock.patch("integracoes.eprotocolo.services.get_client", side_effect=AssertionError("API real")):
            self.client.post(reverse("protocolos:atualizar", args=[self.protocolo.pk]))
            self.client.post(reverse("protocolos:solicitar_assinatura", args=[self.protocolo.pk]), {
                "cpf": "111.444.777-35", "nome": "Fulano",
            })
            self.client.post(reverse("protocolos:tramitar", args=[self.protocolo.pk]), {
                "cod_local_para": "0002", "nome_local_para": "Setor B", "parecer": "ok",
            })
            self.client.post(reverse("protocolos:concluir", args=[self.protocolo.pk]))

    def test_enviar_documento_mock_nao_chama_client_real(self):
        arquivo = SimpleUploadedFile(
            "teste.pdf",
            b"%PDF-1.4 conteudo demo",
            content_type="application/pdf",
        )
        with mock.patch("integracoes.eprotocolo.services.get_client", side_effect=AssertionError("API real")):
            resp = self.client.post(reverse("protocolos:enviar_documento", args=[self.protocolo.pk]), {
                "tipo_documento": "ANEXO",
                "arquivo": arquivo,
                "nome_arquivo": "teste.pdf",
            })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(self.protocolo.documentos.exists())


class BlocoCompactoTagTests(BaseViewTest):
    def test_bloco_em_documento_sem_protocolo_nao_renderiza_componente(self):
        from django.template import Context, Template
        oficio = Oficio.objects.create(numero=7, ano=2026)
        tpl = Template("{% load protocolos_tags %}{% bloco_protocolo oficio %}")
        html = tpl.render(Context({"oficio": oficio}))
        self.assertNotIn("Integracao eProtocolo", html)
        self.assertNotIn("Gerar protocolo", html)
        self.assertNotIn("Vincular existente", html)

    def test_bloco_em_documento_com_protocolo_nao_renderiza_componente(self):
        from django.template import Context, Template
        oficio = Oficio.objects.create(numero=8, ano=2026)
        services.criar_protocolo_a_partir_de_documento(oficio)
        tpl = Template("{% load protocolos_tags %}{% bloco_protocolo oficio %}")
        html = tpl.render(Context({"oficio": oficio}))
        self.assertNotIn("Integracao eProtocolo", html)
        self.assertNotIn("Ver protocolo", html)
