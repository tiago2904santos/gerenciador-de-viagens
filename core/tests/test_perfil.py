from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class PerfilUsuarioTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="usuario_perfil",
            password="SenhaAtual123!",
            email="antigo@pc.pr.gov.br",
        )

    def test_perfil_exige_login(self):
        response = self.client.get(reverse("core:perfil"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_perfil_renderiza_para_usuario_logado(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("core:perfil"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/perfil.html")
        self.assertContains(response, "Meu perfil")
        self.assertContains(response, "Sair do sistema")

    def test_atualiza_dados_do_perfil(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("core:perfil"),
            {
                "action": "atualizar_perfil",
                "perfil-first_name": "Tiago",
                "perfil-last_name": "Santos",
                "perfil-email": "adm.tsantos@pc.pr.gov.br",
            },
        )

        self.assertRedirects(response, reverse("core:perfil"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Tiago")
        self.assertEqual(self.user.last_name, "Santos")
        self.assertEqual(self.user.email, "adm.tsantos@pc.pr.gov.br")

    def test_altera_senha_e_mantem_sessao(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("core:perfil"),
            {
                "action": "alterar_senha",
                "senha-old_password": "SenhaAtual123!",
                "senha-new_password1": "NovaSenha123!",
                "senha-new_password2": "NovaSenha123!",
            },
        )

        self.assertRedirects(response, reverse("core:perfil"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NovaSenha123!"))
        response = self.client.get(reverse("core:perfil"))
        self.assertEqual(response.status_code, 200)

    def test_logout_pela_pagina_de_perfil(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("core:logout"))

        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse("core:perfil"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])
