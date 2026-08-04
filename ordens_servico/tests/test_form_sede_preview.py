from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Cidade
from cadastros.models import Estado


class OrdemServicoFormSedePreviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester_os_sede",
            password="123456",
        )
        self.client.force_login(self.user)
        self.estado = Estado.objects.create(nome="Parana", sigla="PR")
        self.cidade = Cidade.objects.create(nome="Curitiba", estado=self.estado, uf="PR")

    @mock.patch("cadastros.services.resolver_sede_ids_desde_configuracao")
    def test_form_expoe_sede_das_configuracoes_na_previa_de_destinos(self, m_resolver):
        m_resolver.return_value = (self.estado.pk, self.cidade.pk, "")
        response = self.client.get(reverse("ordens_servico:nova"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["sede_config_label"], self.cidade.nome)
        self.assertContains(response, f'data-sede-label="{self.cidade.nome}"')
