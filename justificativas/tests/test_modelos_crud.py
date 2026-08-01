from urllib.parse import urlencode

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

    def test_listagem_exibe_quick_add_e_botao_voltar(self):
        r = self.client.get(reverse("justificativas:modelos_index"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="quick-add-modelo-justificativa"')
        self.assertContains(r, "Novo modelo")
        self.assertContains(r, 'name="nome"')
        self.assertContains(r, 'name="texto"')
        self.assertContains(r, "cv-floating-action")
        self.assertContains(r, "Voltar para as justificativas")
        self.assertContains(r, reverse("justificativas:index"))

    def test_quick_add_cria_modelo_e_redireciona_para_lista(self):
        r = self.client.post(
            reverse("justificativas:modelos_index"),
            data={"nome": "MODELO QUICK ADD", "texto": "Texto base", "is_padrao": "on"},
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(ModeloJustificativa.objects.filter(nome="MODELO QUICK ADD").exists())
        r2 = self.client.get(reverse("justificativas:modelos_index"))
        self.assertContains(r2, "MODELO QUICK ADD")

    def test_quick_add_preserva_next_no_redirecionamento(self):
        wizard_url = reverse("oficios:index")
        r = self.client.post(
            f"{reverse('justificativas:modelos_index')}?next={wizard_url}",
            data={"nome": "MODELO COM NEXT", "texto": "Texto base", "is_padrao": ""},
        )
        self.assertEqual(r.status_code, 302)
        expected = f"{reverse('justificativas:modelos_index')}?{urlencode({'next': wizard_url})}"
        self.assertEqual(r.url, expected)

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
        self.assertContains(response, "Ofício vinculado")
        self.assertContains(response, "termo-oficio-lista")
        self.assertContains(response, "Adicionar ofício")
        self.assertContains(response, reverse("justificativas:modelos_index"))

    def test_oficios_summary_ordena_pelo_ultimo_criado(self):
        antigo = Oficio.objects.create(numero=150, ano=2026, data_criacao="2026-08-01")
        recente = Oficio.objects.create(numero=5, ano=2026, data_criacao="2026-05-01")
        Oficio.objects.filter(pk=antigo.pk).update(created_at="2026-07-01 12:00:00+00:00")
        Oficio.objects.filter(pk=recente.pk).update(created_at="2026-08-01 18:00:00+00:00")

        response = self.client.get(reverse("justificativas:index"))
        summaries = response.context["oficios_summary"]
        ordered = sorted(summaries.values(), key=lambda item: item["order"])
        self.assertEqual([item["id"] for item in ordered[:2]], [recente.pk, antigo.pk])

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
