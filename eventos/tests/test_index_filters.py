from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.testing import area_de_teste
from core.testing import vincular_area
from eventos.models import Evento


class EventoIndexFiltersTests(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_user(
            username="eventos_multifiltro",
            password="SenhaSegura123!",
        )
        vincular_area(usuario)
        self.client.force_login(usuario)

    def test_multiselect_combina_categorias_e_substitui_abas(self):
        hoje = timezone.localdate()
        futuro = Evento.objects.create(
            area=area_de_teste(),
            titulo="Evento futuro",
            data_inicio=hoje + timedelta(days=5),
            data_fim=hoje + timedelta(days=6),
        )
        cancelado = Evento.objects.create(
            area=area_de_teste(),
            titulo="Evento cancelado",
            status=Evento.STATUS_CANCELADO,
            data_inicio=hoje + timedelta(days=10),
            data_fim=hoje + timedelta(days=11),
        )
        Evento.objects.create(
            area=area_de_teste(),
            titulo="Evento atual fora do filtro",
            data_inicio=hoje,
            data_fim=hoje,
        )

        query = urlencode(
            [("aba", "futuras"), ("aba", "cancelados")],
            doseq=True,
        )
        resposta = self.client.get(f"{reverse('eventos:index')}?{query}")

        self.assertEqual(resposta.status_code, 200)
        ids = {evento.pk for evento in resposta.context["page_obj"].object_list}
        self.assertEqual(ids, {futuro.pk, cancelado.pk})
        self.assertEqual(resposta.context["abas_selecionadas"], ["futuras", "cancelados"])
        self.assertEqual(
            resposta.context["page_querystring"],
            "aba=futuras&aba=cancelados",
        )

        html = resposta.content.decode()
        self.assertIn('name="aba"', html)
        self.assertIn('multiple', html)
        self.assertIn('aria-label="Filtrar eventos por situação"', html)
        self.assertIn("data-server-filter-form", html)
        self.assertIn("data-server-filter-search", html)
        self.assertIn("data-server-filter-control", html)
        self.assertIn("js/shell.bundle.js", html)
        self.assertNotIn(">Buscar</span>", html)
        self.assertNotIn('aria-label="Abas de eventos"', html)
        self.assertNotIn('list-page__tabs', html)

    def test_sem_parametro_mostra_todos_os_eventos(self):
        hoje = timezone.localdate()
        futuro = Evento.objects.create(
            area=area_de_teste(),
            titulo="Evento futuro",
            data_inicio=hoje + timedelta(days=5),
            data_fim=hoje + timedelta(days=6),
        )
        atual = Evento.objects.create(
            area=area_de_teste(),
            titulo="Evento atual",
            data_inicio=hoje,
            data_fim=hoje,
        )
        cancelado = Evento.objects.create(
            area=area_de_teste(),
            titulo="Evento cancelado",
            status=Evento.STATUS_CANCELADO,
            data_inicio=hoje + timedelta(days=10),
            data_fim=hoje + timedelta(days=11),
        )

        resposta = self.client.get(reverse("eventos:index"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["abas_selecionadas"], [])
        ids = {evento.pk for evento in resposta.context["page_obj"].object_list}
        self.assertEqual(ids, {futuro.pk, atual.pk, cancelado.pk})
        self.assertFalse(
            any(opcao["selected"] for opcao in resposta.context["status_filter_options"])
        )
