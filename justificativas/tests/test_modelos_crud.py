from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from justificativas.models import Justificativa
from justificativas.models import ModeloJustificativa
from oficios.models import Oficio


class ModelosJustificativaCrudTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="j_test", password="x")
        self.client.force_login(self.user)

    def test_listagem_200(self):
        r = self.client.get(reverse("justificativas:modelos_index"))
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
        r2 = self.client.get(reverse("justificativas:modelos_index"))
        self.assertContains(r2, "MODELO A")


class JustificativasQuickAddTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="j_quick", password="x")
        self.client.force_login(self.user)

    def test_index_renderiza_quick_add(self):
        response = self.client.get(reverse("justificativas:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "quick-add-justificativa")
        self.assertContains(response, "Cadastrar justificativa")
        self.assertContains(response, "OFICIOS DA JUSTIFICATIVA")
        self.assertContains(response, reverse("justificativas:modelos_index"))

    def test_quick_add_cria_justificativa_para_varios_oficios(self):
        oficio_a = Oficio.objects.create(numero=1, ano=2026, data_criacao="2026-05-10")
        oficio_b = Oficio.objects.create(numero=2, ano=2026, data_criacao="2026-05-10")
        modelo = ModeloJustificativa.objects.create(nome="PADRAO", texto="Texto modelo")

        response = self.client.post(
            reverse("justificativas:index"),
            data={
                "oficios": [str(oficio_a.pk), str(oficio_b.pk)],
                "modelo": str(modelo.pk),
                "texto": "Texto aplicado em lote",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Justificativa.objects.count(), 2)
        self.assertTrue(
            Justificativa.objects.filter(
                oficio=oficio_a,
                modelo=modelo,
                texto="Texto aplicado em lote",
                status=Justificativa.STATUS_FINALIZADA,
            ).exists(),
        )
        self.assertTrue(Justificativa.objects.filter(oficio=oficio_b).exists())
