from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.testing import area_de_teste, vincular_area
from eventos.models import Evento
from oficios.models import Oficio


class CriarOficioDaEtapaDoEventoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="evento_oficio")
        vincular_area(self.user)
        self.client.force_login(self.user)
        self.evento = Evento.objects.create(area=area_de_teste(), titulo="Evento com ofício")
        self.etapa_url = reverse(
            "eventos:guiado_etapa", kwargs={"pk": self.evento.pk, "etapa": 3}
        )

    def test_botao_novo_oficio_submete_post_com_o_evento(self):
        resposta = self.client.get(self.etapa_url)
        criar_url = resposta.context["create_urls"]["oficio"]

        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()
        self.assertIn(f'<form method="post" action="{criar_url}">', html)
        self.assertNotIn(f'href="{criar_url}"', html)
        self.assertNotContains(resposta, f'href="{criar_url}"')

    def test_post_do_botao_cria_oficio_vinculado_e_abre_o_cadastro(self):
        criar_url = reverse("oficios:novo") + f"?evento={self.evento.pk}"

        resposta = self.client.post(criar_url)

        oficio = Oficio.objects.get()
        self.assertEqual(oficio.evento, self.evento)
        self.assertRedirects(
            resposta,
            reverse("oficios:dados_viajantes", kwargs={"pk": oficio.pk}),
            fetch_redirect_response=False,
        )
