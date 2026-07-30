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

    def test_renderiza_tres_cv_pickers_single(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("usuarios:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-entity-picker="true"', count=3)
        self.assertContains(response, 'data-entity-picker-mode="single"', count=5)
        self.assertContains(response, 'data-entity-picker-renderer="select"', count=2)

    def test_cria_usuario_vinculado_a_area(self):
        self.client.force_login(self.admin)
        area = AreaTrabalho.objects.create(nome="DPCAP", sigla="DPCAP")

        response = self.client.post(
            reverse("usuarios:index"),
            {
                "action": "criar_usuario",
                "usuario-username": "adm.tsantos",
                "usuario-email": "adm.tsantos@pc.pr.gov.br",
                "usuario-nome_completo": "Tiago Santos",
                "usuario-password1": "SenhaForte123!",
                "usuario-password2": "SenhaForte123!",
                "usuario-area": str(area.pk),
                "usuario-papel": VinculoUsuarioArea.PAPEL_ADMIN,
            },
        )

        self.assertRedirects(response, reverse("usuarios:index"))
        user = get_user_model().objects.get(username="adm.tsantos")
        self.assertEqual(user.email, "adm.tsantos@pc.pr.gov.br")
        self.assertEqual(user.get_full_name(), "Tiago Santos")
        # Usuário criado não é admin do sistema; a única área vira a padrão.
        self.assertFalse(user.is_staff)
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
            },
        )

        self.assertRedirects(response, reverse("usuarios:index"))
        # Vínculo de usuário existente nasce ativo, sem alterar a área padrão dele.
        self.assertTrue(
            VinculoUsuarioArea.objects.filter(
                usuario=user,
                area=area,
                papel=VinculoUsuarioArea.PAPEL_EDITOR,
                area_padrao=False,
                ativo=True,
            ).exists()
        )

    def test_busca_filtra_areas_e_vinculos(self):
        self.client.force_login(self.admin)
        area_ascom = AreaTrabalho.objects.create(nome="Assessoria de Comunicacao", sigla="ASCOM")
        area_dpcap = AreaTrabalho.objects.create(nome="Divisao de Planejamento", sigla="DPCAP")
        user = get_user_model().objects.create_user(
            username="operador_ascom",
            password="123456",
            email="operador.ascom@pc.pr.gov.br",
        )
        VinculoUsuarioArea.objects.create(
            usuario=user,
            area=area_ascom,
            papel=VinculoUsuarioArea.PAPEL_EDITOR,
        )

        response = self.client.get(reverse("usuarios:index"), {"q": "ASCOM"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assessoria de Comunicacao")
        self.assertContains(response, "operador_ascom")
        self.assertNotContains(response, "Divisao de Planejamento")
        self.assertEqual(response.context["total_areas"], 2)
        self.assertEqual(response.context["total_vinculos"], 1)
