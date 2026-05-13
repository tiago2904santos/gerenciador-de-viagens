from __future__ import annotations

import hashlib

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import Client
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from assinaturas.models import AssinaturaDigital
from assinaturas.models import PedidoAssinaturaDocumento
from cadastros.models import AssinaturaConfiguracao
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Servidor
from documentos.models import DocumentoArtefato
from documentos.services.types import DocumentoTipo


def _pdf():
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R/Resources<<>>>>endobj\n"
        b"4 0 obj<</Length 21>>stream\nBT /F1 12 Tf ET\nendstream\nendobj\n"
        b"xref\n0 5\n0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000214 00000 n \n"
        b"trailer<</Size 5/Root 1 0 R>>\n"
        b"startxref\n310\n"
        b"%%EOF\n"
    )


@override_settings(DOCUMENTOS_PERSIST_ARTEFATOS=True)
class PedidoAssinaturaDocumentoViewTests(TestCase):
    def setUp(self):
        raw = _pdf()
        digest = hashlib.sha256(raw).hexdigest()
        self.servidor = Servidor.objects.create(nome="CHEFIA TESTE", cpf="12345678901")
        cfg = ConfiguracaoSistema.get_singleton()
        AssinaturaConfiguracao.objects.update_or_create(
            configuracao=cfg,
            tipo=AssinaturaConfiguracao.TIPO_OFICIO,
            ordem=1,
            defaults={"servidor": self.servidor, "ativo": True},
        )
        self.art = DocumentoArtefato.objects.create(
            tipo=DocumentoTipo.OFICIO.value,
            formato="pdf",
            servidor=self.servidor,
            hash_sha256=digest,
            arquivo=ContentFile(raw, name="a.pdf"),
        )
        self.user = get_user_model().objects.create_user(username="sig_v", password="p" * 12)

    def test_get_legacy_exige_login(self):
        url = reverse("assinaturas:assinatura-assinar-artefato", kwargs={"artefato_id": self.art.pk})
        response = Client().get(url)
        self.assertEqual(response.status_code, 302)

    def test_gerar_link_cria_pedido_com_assinante_configurado(self):
        client = Client()
        client.force_login(self.user)
        url = reverse("assinaturas:gerar-link-assinatura", kwargs={"artefato_id": self.art.pk})
        response = client.get(url)
        self.assertEqual(response.status_code, 302)
        pedido = PedidoAssinaturaDocumento.objects.get()
        self.assertEqual(pedido.artefato, self.art)
        self.assertEqual(pedido.assinante_servidor, self.servidor)
        self.assertEqual(pedido.nome_assinante_snapshot, "CHEFIA TESTE")
        self.assertEqual(pedido.cpf_assinante_snapshot, "12345678901")
        self.assertEqual(pedido.email_assinante_snapshot, "")
        self.assertEqual(pedido.status, PedidoAssinaturaDocumento.STATUS_PENDENTE)

    def test_gerar_link_sem_assinante_configurado_nao_cria_pedido(self):
        AssinaturaConfiguracao.objects.all().delete()
        client = Client()
        client.force_login(self.user)
        url = reverse("assinaturas:gerar-link-assinatura", kwargs={"artefato_id": self.art.pk})
        response = client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PedidoAssinaturaDocumento.objects.exists())

    def test_token_valido_abre_pagina_publica_e_marca_visualizada(self):
        client = Client()
        client.force_login(self.user)
        client.get(reverse("assinaturas:gerar-link-assinatura", kwargs={"artefato_id": self.art.pk}))
        pedido = PedidoAssinaturaDocumento.objects.get()

        response = Client().get(reverse("assinaturas:assinatura-token", kwargs={"token": pedido.token}), HTTP_USER_AGENT="UA")

        self.assertEqual(response.status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, PedidoAssinaturaDocumento.STATUS_VISUALIZADA)
        self.assertTrue(pedido.visualizado_em)
        self.assertEqual(pedido.user_agent_visualizacao, "UA")

    def test_tela_pedido_nao_tem_inputs_manuais_de_assinante(self):
        client = Client()
        client.force_login(self.user)
        client.get(reverse("assinaturas:gerar-link-assinatura", kwargs={"artefato_id": self.art.pk}))
        pedido = PedidoAssinaturaDocumento.objects.get()

        response = client.get(reverse("assinaturas:assinatura-token", kwargs={"token": pedido.token}))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn('name="nome_assinante"', html)
        self.assertNotIn('name="cpf_assinante"', html)
        self.assertNotIn('name="email_assinante"', html)
        self.assertIn('name="sig_x"', html)
        self.assertIn('name="sig_page"', html)
        self.assertNotIn("sidebar", html.lower())
        self.assertNotIn("wizard_stepper", html)
        self.assertNotIn("Dados da assinatura", html)
        self.assertIn("signature-document-shell", html)
        self.assertIn("assinatura-pdf-editor", html)
        self.assertIn("Ajustar largura", html)
        self.assertIn("DOCUMENTO A SER ASSINADO ELETRONICAMENTE", html)
        self.assertIn("Confirmar assinatura", html)
        self.assertIn("Recusar assinatura", html)
        self.assertContains(response, "CHEFIA TESTE")

    def test_post_token_usa_snapshot_e_redireciona_sucesso(self):
        client = Client()
        client.force_login(self.user)
        client.get(reverse("assinaturas:gerar-link-assinatura", kwargs={"artefato_id": self.art.pk}))
        pedido = PedidoAssinaturaDocumento.objects.get()

        response = Client().post(
            reverse("assinaturas:assinatura-token-confirmar", kwargs={"token": pedido.token}),
            {
                "ciencia": "1",
                "sig_x": "0.37",
                "sig_y": "0.8",
                "sig_w": "0.253",
                "sig_h": "0.068",
                "sig_page": "-1",
                "nome_assinante": "Nome Ignorado",
                "cpf_assinante": "00000000000",
                "email_assinante": "ignorado@example.test",
            },
            REMOTE_ADDR="127.0.0.9",
            HTTP_USER_AGENT="ASSINATURA-UA",
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/assinaturas/sucesso/", response.headers.get("Location", ""))
        pedido.refresh_from_db()
        self.art.refresh_from_db()
        self.assertEqual(pedido.status, PedidoAssinaturaDocumento.STATUS_ASSINADO)
        self.assertTrue(pedido.assinatura_id)
        self.assertEqual(pedido.posicao_etiqueta_json["box_x"], 0.37)
        self.assertEqual(pedido.ip_assinatura, "127.0.0.9")
        self.assertEqual(pedido.user_agent, "ASSINATURA-UA")
        self.assertTrue(self.art.arquivo_assinado.name)
        assinatura = AssinaturaDigital.objects.get()
        self.assertEqual(assinatura.nome_assinante, "CHEFIA TESTE")
        self.assertEqual(assinatura.cpf_assinante, "12345678901")
        self.assertNotEqual(assinatura.nome_assinante, "Nome Ignorado")

    def test_rota_legacy_pedidos_token_redireciona_para_pagina_publica(self):
        client = Client()
        client.force_login(self.user)
        client.get(reverse("assinaturas:gerar-link-assinatura", kwargs={"artefato_id": self.art.pk}))
        pedido = PedidoAssinaturaDocumento.objects.get()

        response = Client().get(reverse("assinaturas:assinar-pedido", kwargs={"token": pedido.token}))

        self.assertEqual(response.status_code, 302)
        self.assertIn(f"/assinaturas/assinar/{pedido.token}/", response.headers["Location"])

    def test_token_recusado_bloqueia_assinatura_posterior(self):
        client = Client()
        client.force_login(self.user)
        client.get(reverse("assinaturas:gerar-link-assinatura", kwargs={"artefato_id": self.art.pk}))
        pedido = PedidoAssinaturaDocumento.objects.get()

        response = Client().post(
            reverse("assinaturas:assinatura-token-recusar", kwargs={"token": pedido.token}),
            {"motivo": "Nao concordo"},
        )

        self.assertEqual(response.status_code, 403)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, PedidoAssinaturaDocumento.STATUS_RECUSADA)
        self.assertTrue(pedido.recusado_em)
        self.assertEqual(pedido.motivo_recusa, "Nao concordo")

        blocked = Client().post(
            reverse("assinaturas:assinatura-token-confirmar", kwargs={"token": pedido.token}),
            {"ciencia": "1"},
        )
        self.assertEqual(blocked.status_code, 403)
