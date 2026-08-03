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

    def test_todas_as_paginas_da_administracao_exigem_administrador(self):
        comum = get_user_model().objects.create_user(username="outro_comum", password="123456")
        self.client.force_login(comum)

        for nome in (
            "usuarios:index",
            "usuarios:areas_index",
            "usuarios:usuario_create",
            "usuarios:area_create",
            "usuarios:vinculo_create",
        ):
            with self.subTest(rota=nome):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 403)

    def test_cria_area_pela_pagina(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("usuarios:area_create"),
            {
                "area-nome": "Assessoria de Comunicacao Social",
                "area-sigla": "ASCOM",
                "area-ativa": "on",
            },
        )

        self.assertRedirects(response, reverse("usuarios:areas_index"))
        self.assertTrue(AreaTrabalho.objects.filter(sigla="ASCOM").exists())

    def test_renderiza_cv_pickers_single_nos_formularios(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("usuarios:usuario_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-entity-picker="true"', count=1)

        response = self.client.get(reverse("usuarios:vinculo_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-entity-picker="true"', count=2)

    def test_cria_usuario_vinculado_a_area(self):
        self.client.force_login(self.admin)
        area = AreaTrabalho.objects.create(nome="DPCAP", sigla="DPCAP")

        response = self.client.post(
            reverse("usuarios:usuario_create"),
            {
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
            reverse("usuarios:vinculo_create"),
            {
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

    def test_busca_filtra_a_lista_de_areas(self):
        self.client.force_login(self.admin)
        AreaTrabalho.objects.create(nome="Assessoria de Comunicacao", sigla="ASCOM")
        AreaTrabalho.objects.create(nome="Divisao de Planejamento", sigla="DPCAP")

        response = self.client.get(reverse("usuarios:areas_index"), {"q": "ASCOM"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assessoria de Comunicacao")
        self.assertNotContains(response, "Divisao de Planejamento")
        # O contador do alternador conta o total, não o resultado filtrado.
        self.assertEqual(response.context["total_areas"], 2)

    def test_busca_filtra_a_lista_de_usuarios_pela_area(self):
        self.client.force_login(self.admin)
        area_ascom = AreaTrabalho.objects.create(nome="Assessoria de Comunicacao", sigla="ASCOM")
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
        # A conta chega pela sigla da área, não pelo próprio nome. A asserção é
        # sobre as linhas: o nome do usuário logado aparece na barra lateral.
        titulos = [row["title"] for row in response.context["rows"]]
        self.assertEqual(titulos, ["operador_ascom"])

    def test_usuario_com_duas_areas_aparece_em_uma_linha_so(self):
        self.client.force_login(self.admin)
        diop = AreaTrabalho.objects.create(nome="Diretoria de Operacoes", sigla="DIOP")
        gabin = AreaTrabalho.objects.create(nome="Gabinete", sigla="GABIN")
        user = get_user_model().objects.create_user(
            username="m.oliveira",
            password="123456",
            first_name="Marcos",
            last_name="Oliveira",
        )
        VinculoUsuarioArea.objects.create(
            usuario=user, area=diop, papel=VinculoUsuarioArea.PAPEL_ADMIN, area_padrao=True
        )
        VinculoUsuarioArea.objects.create(
            usuario=user, area=gabin, papel=VinculoUsuarioArea.PAPEL_LEITOR
        )

        response = self.client.get(reverse("usuarios:index"))

        linhas = [row for row in response.context["rows"] if row["title"] == "Marcos Oliveira"]
        self.assertEqual(len(linhas), 1)
        # Área padrão primeiro, e só ela marcada.
        self.assertEqual(
            [(fato["label"], fato["value"]) for fato in linhas[0]["facts"]],
            [("DIOP", "Administrador (padrão)"), ("GABIN", "Leitor")],
        )

    def test_busca_por_area_nao_duplica_usuario_com_duas_areas(self):
        self.client.force_login(self.admin)
        for sigla in ("DIOP", "DIOPE"):
            area = AreaTrabalho.objects.create(nome=f"Area {sigla}", sigla=sigla)
            VinculoUsuarioArea.objects.create(
                usuario=self.admin, area=area, papel=VinculoUsuarioArea.PAPEL_EDITOR
            )

        response = self.client.get(reverse("usuarios:index"), {"q": "DIOP"})

        titulos = [row["title"] for row in response.context["rows"]]
        self.assertEqual(titulos.count("admin_usuarios"), 1)

    def test_alternador_leva_de_usuarios_para_areas(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("usuarios:index"))

        abas = response.context["abas"]
        self.assertEqual([aba["label"] for aba in abas], ["Usuários", "Áreas"])
        self.assertTrue(abas[0]["is_active"])
        self.assertEqual(abas[1]["url"], reverse("usuarios:areas_index"))
