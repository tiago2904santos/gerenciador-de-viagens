from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from justificativas.models import ModeloJustificativa


class ModelosJustificativaCrudTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="j_test", password="x")
        self.client.force_login(self.user)

    def test_listagem_200(self):
        r = self.client.get(reverse("justificativas:index"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Modelos de justificativa")
        self.assertContains(r, "Buscar modelos de justificativa")

    def test_criar_e_lista(self):
        r = self.client.post(
            reverse("justificativas:modelo_novo"),
            data={"nome": "MODELO A", "texto": "Texto base", "is_padrao": "on"},
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(ModeloJustificativa.objects.filter(nome="MODELO A").exists())
        r2 = self.client.get(reverse("justificativas:index"))
        self.assertContains(r2, "MODELO A")
