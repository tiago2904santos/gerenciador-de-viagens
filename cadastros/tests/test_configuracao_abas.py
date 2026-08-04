"""Etapa 1 da Central de Configurações — abas por URL e isolamento de forms."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import AssinaturaConfiguracao
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Servidor
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea


class ConfiguracaoAbasTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="config_abas")
        self.area = AreaTrabalho.objects.create(nome="Área Abas", sigla="ABAS")
        VinculoUsuarioArea.objects.create(
            usuario=self.user, area=self.area, area_padrao=True, ativo=True
        )
        self.client.force_login(self.user)

    def test_aba_padrao_e_instituicao_respondem_200(self):
        for url in (
            reverse("cadastros:configuracao"),
            reverse("cadastros:configuracao_aba", kwargs={"aba": "instituicao"}),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Dados da unidade e endereço")
                self.assertContains(response, 'aria-current="page"')
                self.assertContains(response, reverse("cadastros:configuracao"))
                self.assertNotContains(response, "Valores de diária")

    def test_abas_oficio_e_roteiros_respondem_200(self):
        response = self.client.get(
            reverse("cadastros:configuracao_aba", kwargs={"aba": "oficio"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assinantes e destinatário")
        self.assertContains(response, "Destinatário do Ofício")
        self.assertContains(response, "Assinante do Ofício")

        response = self.client.get(
            reverse("cadastros:configuracao_aba", kwargs={"aba": "roteiros"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Valores de diária")

    def test_slug_invalido_responde_404(self):
        response = self.client.get(
            reverse("cadastros:configuracao_aba", kwargs={"aba": "inexistente"})
        )
        self.assertEqual(response.status_code, 404)

    def test_aba_ativa_marcada_com_aria_current(self):
        response = self.client.get(
            reverse("cadastros:configuracao_aba", kwargs={"aba": "oficio"})
        )
        self.assertEqual(response.status_code, 200)
        oficio_url = reverse("cadastros:configuracao_aba", kwargs={"aba": "oficio"})
        self.assertContains(
            response,
            f'href="{oficio_url}"',
        )
        # O botão ativo carrega aria-current="page".
        self.assertRegex(
            response.content.decode(),
            rf'href="{oficio_url}"[^>]*aria-current="page"|aria-current="page"[^>]*href="{oficio_url}"',
        )

    def test_post_instituicao_nao_altera_assinantes(self):
        config = ConfiguracaoSistema.get_for_area(self.area)
        servidor = Servidor.objects.create(nome="Assinante Original", area=self.area)
        AssinaturaConfiguracao.objects.create(
            configuracao=config,
            tipo=AssinaturaConfiguracao.OFICIO,
            servidor=servidor,
            ativo=True,
        )

        url = reverse("cadastros:configuracao")
        response = self.client.post(
            url,
            {
                "form_id": "instituicao",
                "telefone": "41999990000",
                "email": "config@pc.pr.gov.br",
            },
        )
        self.assertRedirects(response, url)

        config.refresh_from_db()
        self.assertEqual(
            AssinaturaConfiguracao.objects.get(
                configuracao=config, tipo=AssinaturaConfiguracao.OFICIO
            ).servidor_id,
            servidor.pk,
        )

    def test_post_oficio_redireciona_para_aba_oficio(self):
        url = reverse("cadastros:configuracao_aba", kwargs={"aba": "oficio"})
        response = self.client.post(
            url,
            {
                "form_id": "oficio",
                "assinante_oficio": "",
                "assinante_justificativa": "",
                "assinante_plano_trabalho": "",
                "assinante_ordem_servico": "",
                "destinatario_oficio": "",
                "destinatario_oficio_nome": "",
                "destinatario_oficio_cargo": "",
                "destinatario_oficio_unidade": "",
            },
        )
        self.assertRedirects(response, url)
