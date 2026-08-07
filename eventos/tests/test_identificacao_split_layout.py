"""Caracteriza o layout de Identificação na etapa 1 do evento guiado."""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from eventos.models import Evento
from core.testing import area_de_teste
from core.testing import vincular_area


class IdentificacaoSplitLayoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ident-split", password="123456")
        self.client.force_login(self.user)
        vincular_area(self.user)
        self.evento = Evento.objects.create(area=area_de_teste(), 
            titulo="Evento split",
            data_inicio=date(2026, 8, 10),
            data_fim=date(2026, 8, 12),
        )

    def test_modelo_e_motivo_ficam_fora_da_identificacao(self):
        url = reverse("eventos:guiado_etapa", kwargs={"pk": self.evento.pk, "etapa": 1})
        html = self.client.get(url).content.decode("utf-8")

        ident_id = html.find('id="evento-card-identificacao-d"')
        motivo_id = html.find('id="evento-card-motivo-d"')
        dados_id = html.find('id="evento-card-dados-d"')
        self.assertGreater(ident_id, -1)
        self.assertGreater(motivo_id, ident_id)
        self.assertGreater(dados_id, motivo_id)

        # class= vem antes do id= no <section>; recua até a abertura da tag.
        ident_start = html.rfind("<section", 0, ident_id)
        motivo_start = html.rfind("<section", 0, motivo_id)
        dados_start = html.rfind("<section", 0, dados_id)

        ident_chunk = html[ident_start:motivo_start]
        motivo_chunk = html[motivo_start:dados_start]

        self.assertIn("cv-form-block--split", ident_chunk)
        self.assertIn("evento-identificacao-split", ident_chunk)
        self.assertIn('name="tipos"', ident_chunk)
        self.assertNotIn("modelo_motivo", ident_chunk)
        self.assertNotIn('name="motivo"', ident_chunk)

        self.assertIn("modelo_motivo", motivo_chunk)
        self.assertIn('name="motivo"', motivo_chunk)
        self.assertNotIn('name="tipos"', motivo_chunk)
