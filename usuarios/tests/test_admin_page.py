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
        area = AreaTrabalho.objects.create(nome="ASCOM", sigla="ASCOM")
        user = get_user_model().objects.create_user(username="alvo", password="123456")
        vinculo = VinculoUsuarioArea.objects.create(
            usuario=user,
            area=area,
            papel=VinculoUsuarioArea.PAPEL_EDITOR,
        )

        rotas = [
            reverse("usuarios:index"),
            reverse("usuarios:areas_index"),
            reverse("usuarios:usuario_create"),
            reverse("usuarios:area_create"),
            reverse("usuarios:vinculo_create"),
            reverse("usuarios:usuario_update", args=[user.pk]),
            reverse("usuarios:usuario_delete", args=[user.pk]),
            reverse("usuarios:area_update", args=[area.pk]),
            reverse("usuarios:area_delete", args=[area.pk]),
            reverse("usuarios:vinculo_create_na_area", args=[area.pk]),
            reverse("usuarios:vinculo_delete", args=[vinculo.pk]),
        ]
        for url in rotas:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_cria_area_pela_pagina(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("usuarios:areas_index"),
            {
                "area-nome": "Assessoria de Comunicacao Social",
                "area-sigla": "ASCOM",
                "area-ativa": "on",
            },
        )

        self.assertRedirects(response, reverse("usuarios:areas_index"))
        self.assertTrue(AreaTrabalho.objects.filter(sigla="ASCOM").exists())

    def test_rota_nova_area_redireciona_para_lista(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("usuarios:area_create"))
        self.assertRedirects(response, reverse("usuarios:areas_index"))

    def test_lista_de_areas_tem_quick_add(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("usuarios:areas_index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="quick-add-area"')
        self.assertContains(response, "Cadastrar área")

    def test_lista_de_areas_abre_gerenciador(self):
        self.client.force_login(self.admin)
        area = AreaTrabalho.objects.create(nome="Assessoria", sigla="ASCOM")

        response = self.client.get(reverse("usuarios:areas_index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("usuarios:area_update", args=[area.pk]))
        self.assertContains(response, reverse("usuarios:area_delete", args=[area.pk]))
        self.assertContains(response, 'data-overlay-target="delete-confirm-modal"')
        # A classe legada `icon-btn--delete` saiu na migração da tela para o v2
        # (2026-08-18). O que este teste protege — a linha oferece exclusão — é
        # cobrado pela asserção acima, no gatilho do diálogo.
        self.assertContains(response, "Excluir área?")

    def test_exclui_area_pela_lista(self):
        self.client.force_login(self.admin)
        area = AreaTrabalho.objects.create(nome="Area vazia", sigla="Z")

        response = self.client.post(reverse("usuarios:area_delete", args=[area.pk]))

        self.assertRedirects(response, reverse("usuarios:areas_index"))
        self.assertFalse(AreaTrabalho.objects.filter(pk=area.pk).exists())

    def test_nao_permite_excluir_area_com_usuarios(self):
        self.client.force_login(self.admin)
        area = AreaTrabalho.objects.create(nome="Assessoria", sigla="ASCOM")
        user = get_user_model().objects.create_user(username="operador", password="123456")
        VinculoUsuarioArea.objects.create(
            usuario=user,
            area=area,
            papel=VinculoUsuarioArea.PAPEL_EDITOR,
        )

        response = self.client.post(reverse("usuarios:area_delete", args=[area.pk]))

        self.assertRedirects(response, reverse("usuarios:areas_index"))
        self.assertTrue(AreaTrabalho.objects.filter(pk=area.pk).exists())

    def test_gerenciador_atualiza_area_e_vincula_usuario(self):
        self.client.force_login(self.admin)
        area = AreaTrabalho.objects.create(nome="Assessoria", sigla="ASCOM")
        user = get_user_model().objects.create_user(
            username="operador",
            password="123456",
            first_name="Operador",
        )

        response = self.client.get(reverse("usuarios:area_update", args=[area.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dados da área")
        self.assertContains(response, "Usuários da área")

        response = self.client.post(
            reverse("usuarios:area_update", args=[area.pk]),
            {
                "area-nome": "Assessoria de Comunicacao",
                "area-sigla": "ASCOM",
                "area-ativa": "on",
            },
        )
        self.assertRedirects(response, reverse("usuarios:area_update", args=[area.pk]))
        area.refresh_from_db()
        self.assertEqual(area.nome, "Assessoria de Comunicacao")

        response = self.client.post(
            reverse("usuarios:vinculo_create_na_area", args=[area.pk]),
            {
                "vinculo-usuario": str(user.pk),
                "vinculo-area": str(area.pk),
                "vinculo-papel": VinculoUsuarioArea.PAPEL_EDITOR,
            },
        )
        self.assertRedirects(response, reverse("usuarios:area_update", args=[area.pk]))
        vinculo = VinculoUsuarioArea.objects.get(usuario=user, area=area)
        self.assertEqual(vinculo.papel, VinculoUsuarioArea.PAPEL_EDITOR)

        response = self.client.get(reverse("usuarios:area_update", args=[area.pk]))
        self.assertContains(response, "Operador")
        self.assertContains(response, reverse("usuarios:vinculo_delete", args=[vinculo.pk]))

        response = self.client.post(reverse("usuarios:vinculo_delete", args=[vinculo.pk]))
        self.assertRedirects(response, reverse("usuarios:area_update", args=[area.pk]))
        self.assertFalse(VinculoUsuarioArea.objects.filter(pk=vinculo.pk).exists())

    def test_gerenciador_troca_o_perfil_de_quem_ja_esta_na_area(self):
        """O mesmo POST que vincula também edita: a unique diz que é um registro só."""
        self.client.force_login(self.admin)
        area = AreaTrabalho.objects.create(nome="Assessoria", sigla="ASCOM")
        user = get_user_model().objects.create_user(
            username="operador", password="123456", first_name="Operador"
        )
        vinculo = VinculoUsuarioArea.objects.create(
            usuario=user, area=area, papel=VinculoUsuarioArea.PAPEL_LEITOR
        )

        response = self.client.get(reverse("usuarios:area_update", args=[area.pk]))
        self.assertContains(response, 'data-row-edit-modal="vincular-usuario-modal"')
        self.assertContains(response, "vinculo-papel")

        response = self.client.post(
            reverse("usuarios:vinculo_create_na_area", args=[area.pk]),
            {
                "vinculo-usuario": str(user.pk),
                "vinculo-area": str(area.pk),
                "vinculo-papel": VinculoUsuarioArea.PAPEL_ADMIN,
            },
        )

        self.assertRedirects(response, reverse("usuarios:area_update", args=[area.pk]))
        self.assertEqual(VinculoUsuarioArea.objects.filter(usuario=user, area=area).count(), 1)
        vinculo.refresh_from_db()
        self.assertEqual(vinculo.papel, VinculoUsuarioArea.PAPEL_ADMIN)

    def test_gerenciador_pagina_vinculos_de_cinco_em_cinco(self):
        self.client.force_login(self.admin)
        area = AreaTrabalho.objects.create(nome="Assessoria", sigla="ASCOM")
        for indice in range(7):
            VinculoUsuarioArea.objects.create(
                usuario=get_user_model().objects.create_user(
                    username=f"conta{indice}", password="123456"
                ),
                area=area,
                papel=VinculoUsuarioArea.PAPEL_EDITOR,
            )

        response = self.client.get(reverse("usuarios:area_update", args=[area.pk]))

        self.assertEqual(len(response.context["rows"]), 5)
        self.assertEqual(response.context["page_obj"].paginator.num_pages, 2)
        self.assertContains(response, "pagination__controls")

        response = self.client.get(reverse("usuarios:area_update", args=[area.pk]), {"page": 2})

        self.assertEqual(len(response.context["rows"]), 2)

    def test_gerenciador_nao_pagina_com_cinco_ou_menos(self):
        self.client.force_login(self.admin)
        area = AreaTrabalho.objects.create(nome="Assessoria", sigla="ASCOM")
        for indice in range(5):
            VinculoUsuarioArea.objects.create(
                usuario=get_user_model().objects.create_user(
                    username=f"conta{indice}", password="123456"
                ),
                area=area,
                papel=VinculoUsuarioArea.PAPEL_EDITOR,
            )

        response = self.client.get(reverse("usuarios:area_update", args=[area.pk]))

        self.assertEqual(len(response.context["rows"]), 5)
        self.assertNotContains(response, "pagination__controls")

    def test_renderiza_cv_pickers_single_nos_formularios(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("usuarios:index"))
        self.assertEqual(response.status_code, 200)
        # Quick-add e modal: área é search-picker; perfil é select (poucas opções).
        self.assertContains(response, 'data-entity-picker="true"', count=2)
        self.assertContains(response, 'id="quick-add-usuario"')
        self.assertContains(response, 'id="vincular-usuario-modal"')
        self.assertContains(response, "form-stack")
        self.assertContains(response, "modal__message")
        self.assertContains(response, 'id="id_vinculo-area"')
        self.assertContains(response, 'id="id_vinculo-papel"')
        self.assertContains(response, "Buscar área...")
        self.assertNotContains(response, "Buscar perfil...")
        self.assertContains(response, 'data-entity-picker-renderer="select"', count=2)

    def test_cria_usuario_vinculado_a_area(self):
        self.client.force_login(self.admin)
        area = AreaTrabalho.objects.create(nome="DPCAP", sigla="DPCAP")

        response = self.client.post(
            reverse("usuarios:index"),
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

    def test_rota_novo_usuario_redireciona_para_lista(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("usuarios:usuario_create"))
        self.assertRedirects(response, reverse("usuarios:index"))

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

    def test_lista_de_usuarios_tem_modal_de_vinculo_no_card(self):
        self.client.force_login(self.admin)
        user = get_user_model().objects.create_user(username="operador", password="123456")

        response = self.client.get(reverse("usuarios:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "record-row__vincular")
        # `icon-btn--link` era a classe legada do botão e saiu com a migração
        # (2026-08-18). A de comportamento — `record-row__vincular`, que o
        # `usuarios-admin.js` procura — sobreviveu, e é a asserção acima.
        self.assertContains(response, 'data-overlay-target="vincular-usuario-modal"')
        self.assertContains(response, f'data-vincular-usuario-id="{user.pk}"')
        self.assertContains(response, f'data-vincular-url="{reverse("usuarios:vinculo_create")}"')
        self.assertContains(response, 'id="vincular-usuario-modal"')
        self.assertContains(response, 'name="vinculo-usuario"')
        self.assertContains(response, 'data-quick-edit')
        self.assertContains(response, reverse("usuarios:usuario_update", args=[user.pk]))
        self.assertContains(response, reverse("usuarios:usuario_delete", args=[user.pk]))
        self.assertContains(response, 'data-overlay-target="delete-confirm-modal"')
        # A classe legada `icon-btn--delete` saiu na migração da tela para o v2
        # (2026-08-18). O que este teste protege — a linha oferece exclusão — é
        # cobrado pela asserção acima, no gatilho do diálogo.
        self.assertContains(response, "Excluir usuário?")
        # A própria conta logada não oferece exclusão.
        self.assertNotContains(
            response,
            reverse("usuarios:usuario_delete", args=[self.admin.pk]),
        )
        self.assertNotContains(response, "usuario-qa-permissoes")
        self.assertNotContains(response, "usuario-is_active")
        self.assertNotContains(response, "usuario-is_staff")
        self.assertNotContains(response, "floating-action--stacked")

    def test_exclui_usuario_pela_lista(self):
        self.client.force_login(self.admin)
        user = get_user_model().objects.create_user(username="para_excluir", password="123456")

        response = self.client.post(reverse("usuarios:usuario_delete", args=[user.pk]))

        self.assertRedirects(response, reverse("usuarios:index"))
        self.assertFalse(get_user_model().objects.filter(pk=user.pk).exists())

    def test_nao_permite_excluir_a_propria_conta(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse("usuarios:usuario_delete", args=[self.admin.pk]))

        self.assertRedirects(response, reverse("usuarios:index"))
        self.assertTrue(get_user_model().objects.filter(pk=self.admin.pk).exists())

    def test_edita_usuario_pelo_quick_add(self):
        self.client.force_login(self.admin)
        user = get_user_model().objects.create_user(
            username="operador",
            password="123456",
            first_name="Operador",
            email="operador@pc.pr.gov.br",
        )

        response = self.client.get(reverse("usuarios:usuario_update", args=[user.pk]))
        self.assertRedirects(response, reverse("usuarios:index"))

        response = self.client.post(
            reverse("usuarios:usuario_update", args=[user.pk]),
            {
                "usuario-username": "operador.editado",
                "usuario-email": "operador.editado@pc.pr.gov.br",
                "usuario-nome_completo": "Operador Editado",
            },
        )

        self.assertRedirects(response, reverse("usuarios:index"))
        user.refresh_from_db()
        self.assertEqual(user.username, "operador.editado")
        self.assertEqual(user.get_full_name(), "Operador Editado")
        self.assertEqual(user.email, "operador.editado@pc.pr.gov.br")

    def test_rota_de_vinculo_get_redireciona_para_lista(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("usuarios:vinculo_create"))
        self.assertRedirects(response, reverse("usuarios:index"))

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
