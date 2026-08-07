from datetime import date

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from eventos.models import Evento
from core.testing import area_de_teste
from core.testing import vincular_area


class EventoListPerformanceTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="eventos_performance",
            password="SenhaSegura123!",
        )
        vincular_area(user)
        self.client.force_login(user)

    def test_lista_pagina_e_mantem_orcamento_de_queries(self):
        Evento.objects.bulk_create(
            [
                Evento(
                    area=area_de_teste(),
                    titulo=f"Evento {numero}",
                    data_inicio=date(2026, 6, 1),
                    data_fim=date(2026, 6, 2),
                )
                for numero in range(25)
            ],
        )

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("eventos:index") + "?aba=atuais")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["page_obj"].object_list), 20)
        self.assertLessEqual(
            len(queries),
            30,
            msg="\n".join(query["sql"] for query in queries.captured_queries),
        )
