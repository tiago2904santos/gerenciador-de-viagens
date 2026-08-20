from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from eventos.models import Evento
from integracoes.google_drive.models import DriveSyncStatus
from core.testing import area_de_teste
from core.testing import vincular_area


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
        self.assertContains(response, "Conta e segurança")
        self.assertContains(response, "Dados pessoais")
        self.assertContains(response, "Sair do sistema")
        # O casco virou `form-page` em 2026-08-19: as três classes do sistema
        # antigo (`document-form-page`, `travel-document-wizard__form` e o
        # `page-shell` em volta) saíram com o `flow_base`. O que a tela precisa
        # ter continua sendo o painel e o marcador da própria página.
        self.assertContains(response, "form-page")
        self.assertContains(response, "perfil-form-page")
        self.assertNotContains(response, "Resumo da conta")

    def test_perfil_nao_faz_n_mais_um_nas_pendencias_do_drive(self):
        self.client.force_login(self.user)
        vincular_area(self.user)
        content_type = ContentType.objects.get_for_model(Evento)
        eventos = Evento.objects.bulk_create(
            [Evento(area=area_de_teste(), titulo=f"Evento {index}") for index in range(20)],
        )
        DriveSyncStatus.objects.bulk_create(
            [
                DriveSyncStatus(
                    usuario=self.user,
                    content_type=content_type,
                    object_id=str(evento.pk),
                    ultimo_erro="timeout",
                )
                for evento in eventos
            ],
        )

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("core:perfil"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["drive_total_pendencias"], 20)
        self.assertLessEqual(len(queries), 25)

    def test_sidebar_exibe_acesso_ao_perfil_e_logout(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("core:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/perfil/"')
        self.assertContains(response, 'action="/logout/"')

    def test_atualiza_dados_do_perfil(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("core:perfil"),
            {
                "action": "atualizar_perfil",
                "perfil-username": "usuario_perfil",
                "perfil-nome_completo": "Tiago Dos Santos",
                "perfil-email": "adm.tsantos@pc.pr.gov.br",
            },
        )

        self.assertRedirects(response, reverse("core:perfil"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.get_full_name(), "Tiago Dos Santos")
        self.assertEqual(self.user.first_name, "Tiago")
        self.assertEqual(self.user.last_name, "Dos Santos")
        self.assertEqual(self.user.email, "adm.tsantos@pc.pr.gov.br")

    def test_atualiza_nome_de_usuario(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("core:perfil"),
            {
                "action": "atualizar_perfil",
                "perfil-username": "novo_login",
                "perfil-nome_completo": "Tiago Dos Santos",
                "perfil-email": "adm.tsantos@pc.pr.gov.br",
            },
        )

        self.assertRedirects(response, reverse("core:perfil"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "novo_login")

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
