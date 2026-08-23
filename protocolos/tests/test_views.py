"""Views da Central de Protocolos — fatia 1 da restauração (UI v2, modo mock).

O que estas suítes guardam:

1. **Sem credenciais, nada quebra** — toda tela carrega em modo mock, que é o
   estado de qualquer máquina recém-clonada.
2. **O ciclo de protocolar fecha pelas views**: escolher um ofício → protocolo
   criado com GFK e número mock determinístico → documento enviado → sync
   refletindo os mocks. É o caminho que a demonstração percorre.
3. **A fachada não fala com o client real** — em mock, nenhuma view encosta em
   `EProtocoloClient`.
4. **A fronteira do módulo**: `views.py` importa apenas forms/selectors/
   services/permissions — a versão antiga tinha `ContentType.objects` na view,
   que a catraca de ORM do projeto conta.

As ações de assinatura, tramitação e conclusão voltam na fatia 2, junto com
seus testes (removidos daqui, não perdidos: `git show 6f5046c7` os guarda).
"""

from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from oficios.models import Oficio
from protocolos import services
from protocolos.models import Protocolo, ProtocoloDocumento
from usuarios.models import AreaTrabalho, VinculoUsuarioArea

PDF = b"%PDF-1.4\n%%EOF\n"


class BaseViewTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="op", password="x12345678")
        self.client.force_login(self.user)
        self.area = AreaTrabalho.objects.create(nome="Área Teste", sigla="AT")
        # `Oficio.objects` é escopado pela área ATIVA do usuário (BE-09); sem o
        # vínculo o seletor de ofícios protocolaveis viria vazio.
        VinculoUsuarioArea.objects.create(usuario=self.user, area=self.area)

    def criar_oficio(self, numero=5, **kwargs):
        return Oficio.objects.create(area=self.area, numero=numero, ano=2026, **kwargs)


class ListaDetalheTests(BaseViewTest):
    def test_exige_login(self):
        self.client.logout()
        resp = self.client.get(reverse("protocolos:index"))
        self.assertEqual(resp.status_code, 302)

    def test_lista_carrega_sem_credenciais_sem_erro(self):
        resp = self.client.get(reverse("protocolos:index"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Central de Protocolos")

    def test_lista_mock_exibe_protocolos_demo_e_banner(self):
        resp = self.client.get(reverse("protocolos:index"))
        self.assertContains(resp, "24.123.456-7")
        self.assertContains(resp, "Modo demonstração")
        # A busca é a do servidor, com os ganchos do motor compartilhado.
        self.assertContains(resp, "data-server-filter-form")
        self.assertContains(resp, "data-server-filter-search")

    def test_lista_filtra_por_status(self):
        services.garantir_protocolos_demo_treinamento()
        resp = self.client.get(reverse("protocolos:index"), {"status": "concluido"})
        self.assertEqual(resp.status_code, 200)

    def test_detalhe_carrega_com_paineis_v2(self):
        protocolo = services.vincular_protocolo_manual("24.10.10-1", assunto="Diárias")
        resp = self.client.get(reverse("protocolos:detail", args=[protocolo.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "24.10.10-1")
        self.assertContains(resp, "Sincronizar")
        self.assertContains(resp, "Enviar documento")

    def test_detalhe_inexistente_404(self):
        resp = self.client.get(reverse("protocolos:detail", args=[999999]))
        self.assertEqual(resp.status_code, 404)


class CriacaoTests(BaseViewTest):
    def test_tela_de_criacao_lista_oficios_protocolaveis(self):
        oficio = self.criar_oficio(numero=11)
        resp = self.client.get(reverse("protocolos:protocolo_create"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Protocolar ofício")
        self.assertContains(resp, "Vincular protocolo existente")
        self.assertContains(resp, str(oficio))

    def test_oficio_ja_protocolado_sai_da_lista(self):
        oficio = self.criar_oficio(numero=12)
        services.criar_protocolo_a_partir_de_documento(oficio)
        resp = self.client.get(reverse("protocolos:protocolo_create"))
        # Pelo rótulo, não por `value="{pk}"`: pk pequeno colide com qualquer
        # outro value="1" da página (o hidden de enviar_documento, por exemplo).
        self.assertNotContains(resp, str(oficio))

    def test_vincular_manual_cria_e_redireciona(self):
        resp = self.client.post(
            reverse("protocolos:protocolo_create"),
            {"numero": "24.99.88-7", "assunto": "Manual", "descricao": ""},
        )
        protocolo = Protocolo.objects.get(numero="249988" + "7")
        self.assertRedirects(resp, reverse("protocolos:detail", args=[protocolo.pk]))

    def test_protocolar_oficio_fecha_o_ciclo_mock(self):
        """O caminho da demonstração, inteiro, pelas views."""
        oficio = self.criar_oficio(numero=13)
        ct_id = resp_ct = self.client.get(reverse("protocolos:protocolo_create"))
        # o content_type vai no hidden do form; aqui lemos do contexto
        ct_id = resp_ct.context["oficio_content_type_id"]

        resp = self.client.post(
            reverse("protocolos:vincular"),
            {"content_type_id": ct_id, "oficio": oficio.pk, "enviar_documento": "1"},
        )
        protocolo = Protocolo.objects.exclude(numero="").latest("pk")
        self.assertRedirects(resp, reverse("protocolos:detail", args=[protocolo.pk]))
        self.assertEqual(protocolo.origem_object, oficio)
        self.assertTrue(protocolo.modo_mock)
        self.assertTrue(protocolo.logs.exists())

        # Número mock é determinístico: criar de novo a partir do mesmo seed
        # geraria o mesmo formato NN.NNN.NNN-D.
        self.assertRegex(protocolo.numero_display, r"\d{2}\.\d{3}\.\d{3}-\d")

    def test_vincular_sem_origem_valida_volta_para_criacao(self):
        resp = self.client.post(
            reverse("protocolos:vincular"),
            {"content_type_id": "", "oficio": ""},
        )
        self.assertRedirects(resp, reverse("protocolos:protocolo_create"))


class AcoesTests(BaseViewTest):
    def setUp(self):
        super().setUp()
        self.protocolo = services.vincular_protocolo_manual("24.11.22-3", assunto="Ações")

    def test_enviar_documento_upload(self):
        resp = self.client.post(
            reverse("protocolos:enviar_documento", args=[self.protocolo.pk]),
            {
                "tipo_documento": "ANEXO",
                "arquivo": SimpleUploadedFile("doc.pdf", PDF, content_type="application/pdf"),
            },
        )
        self.assertRedirects(resp, reverse("protocolos:detail", args=[self.protocolo.pk]))
        doc = self.protocolo.documentos.get()
        self.assertEqual(doc.tipo_documento, ProtocoloDocumento.TIPO_ANEXO)
        self.assertTrue(doc.md5)

    def test_enviar_sem_arquivo_e_sem_geracao_reprova(self):
        resp = self.client.post(
            reverse("protocolos:enviar_documento", args=[self.protocolo.pk]),
            {"tipo_documento": "ANEXO"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Envie um PDF ou marque a geração automática")

    def test_atualizar_sincroniza_e_volta_ao_detalhe(self):
        resp = self.client.post(reverse("protocolos:atualizar", args=[self.protocolo.pk]))
        self.assertRedirects(resp, reverse("protocolos:detail", args=[self.protocolo.pk]))
        self.protocolo.refresh_from_db()
        self.assertIsNotNone(self.protocolo.ultima_sincronizacao_em)

    def test_atualizar_recusa_get(self):
        resp = self.client.get(reverse("protocolos:atualizar", args=[self.protocolo.pk]))
        self.assertEqual(resp.status_code, 405)


class ModoMockNaoChamaClientTests(BaseViewTest):
    def test_acoes_mock_nao_chamam_client_real(self):
        oficio = self.criar_oficio(numero=21)
        with mock.patch("integracoes.eprotocolo.services.get_client") as client_factory:
            ct_id = self.client.get(reverse("protocolos:protocolo_create")).context[
                "oficio_content_type_id"
            ]
            self.client.post(
                reverse("protocolos:vincular"),
                {"content_type_id": ct_id, "oficio": oficio.pk, "enviar_documento": "1"},
            )
            protocolo = Protocolo.objects.exclude(numero="").latest("pk")
            self.client.post(reverse("protocolos:atualizar", args=[protocolo.pk]))
        client_factory.assert_not_called()


class FronteiraDoModuloTests(TestCase):
    def test_views_importam_apenas_a_fachada(self):
        """A versão antiga tinha `ContentType.objects` na view — a catraca de
        ORM do projeto conta cada acesso de manager em `views.py`, e é por isso
        que a resolução de content type mora em `selectors`."""
        from pathlib import Path

        from django.conf import settings

        fonte = (Path(settings.BASE_DIR) / "protocolos" / "views.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn(".objects.", fonte)
        self.assertNotIn("ContentType", fonte)
