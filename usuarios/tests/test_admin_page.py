from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea


class UsuariosAdminPageTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="admin_usuarios",
            password="123456",
            is_staff=True,
        )

    def test_pagina_exige_usuario_administrador(self):
        response = self.client.get(reverse("usuarios:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

        comum = get_user_model().objects.create_user(username="usuario_comum", password="123456")
        self.client.force_login(comum)

        response = self.client.get(reverse("usuarios:index"))

        self.assertEqual(response.status_code, 403)

    def test_cria_area_pela_pagina(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("usuarios:index"),
            {
                "action": "criar_area",
                "area-nome": "Assessoria de Comunicacao Social",
                "area-sigla": "ASCOM",
                "area-ativa": "on",
            },
        )

        self.assertRedirects(response, reverse("usuarios:index"))
        self.assertTrue(AreaTrabalho.objects.filter(sigla="ASCOM").exists())

    def test_cria_usuario_vinculado_a_area(self):
        self.client.force_login(self.admin)
        area = AreaTrabalho.objects.create(nome="DPCAP", sigla="DPCAP")

        response = self.client.post(
            reverse("usuarios:index"),
            {
                "action": "criar_usuario",
                "usuario-username": "adm.tsantos",
                "usuario-email": "adm.tsantos@pc.pr.gov.br",
                "usuario-first_name": "Tiago",
                "usuario-last_name": "Santos",
                "usuario-password1": "SenhaForte123!",
                "usuario-password2": "SenhaForte123!",
                "usuario-area": str(area.pk),
                "usuario-papel": VinculoUsuarioArea.PAPEL_ADMIN,
                "usuario-area_padrao": "on",
            },
        )

        self.assertRedirects(response, reverse("usuarios:index"))
        user = get_user_model().objects.get(username="adm.tsantos")
        self.assertEqual(user.email, "adm.tsantos@pc.pr.gov.br")
        self.assertTrue(
            VinculoUsuarioArea.objects.filter(
                usuario=user,
                area=area,
                papel=VinculoUsuarioArea.PAPEL_ADMIN,
                area_padrao=True,
                ativo=True,
            ).exists()
        )

    def test_vincula_usuario_existente_a_area(self):
        self.client.force_login(self.admin)
        user = get_user_model().objects.create_user(username="operador", password="123456")
        area = AreaTrabalho.objects.create(nome="ASCOM", sigla="ASCOM")

        response = self.client.post(
            reverse("usuarios:index"),
            {
                "action": "vincular_usuario",
                "vinculo-usuario": str(user.pk),
                "vinculo-area": str(area.pk),
                "vinculo-papel": VinculoUsuarioArea.PAPEL_EDITOR,
                "vinculo-area_padrao": "on",
                "vinculo-ativo": "on",
            },
        )

        self.assertRedirects(response, reverse("usuarios:index"))
        self.assertTrue(
            VinculoUsuarioArea.objects.filter(
                usuario=user,
                area=area,
                papel=VinculoUsuarioArea.PAPEL_EDITOR,
                area_padrao=True,
                ativo=True,
            ).exists()
        )
