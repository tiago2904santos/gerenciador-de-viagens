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
        """Três blocos, nesta ordem, com cada campo no seu.

        Os blocos do v2 (2026-08-18) não carregam mais `id` — o que os separa é o
        TÍTULO, que é também o que a pessoa vê. Por isso a busca passou a ser
        pelo título, e não pelo `id="evento-card-*-d"` do sistema antigo.

        O que se prova continua sendo o mesmo: identificação é um bloco `split`
        com o tipo e só ele; modelo e motivo vêm depois, num bloco próprio.
        """
        url = reverse("eventos:guiado_etapa", kwargs={"pk": self.evento.pk, "etapa": 1})
        html = self.client.get(url).content.decode("utf-8")

        ident_id = html.find(">Identificação<")
        motivo_id = html.find(">Motivo<")
        dados_id = html.find(">Período e destinos<")
        self.assertGreater(ident_id, -1, "bloco de identificação sumiu da etapa 1")
        self.assertGreater(motivo_id, ident_id)
        self.assertGreater(dados_id, motivo_id)

        # A abertura da <section> do bloco vem antes do título dele.
        ident_start = html.rfind("<section", 0, ident_id)
        motivo_start = html.rfind("<section", 0, motivo_id)
        dados_start = html.rfind("<section", 0, dados_id)

        ident_chunk = html[ident_start:motivo_start]
        motivo_chunk = html[motivo_start:dados_start]

        self.assertIn("form-block--split", ident_chunk)
        self.assertIn('name="tipos"', ident_chunk)
        self.assertNotIn("modelo_motivo", ident_chunk)
        self.assertNotIn('name="motivo"', ident_chunk)

        self.assertIn("modelo_motivo", motivo_chunk)
        self.assertIn('name="motivo"', motivo_chunk)
        self.assertNotIn('name="tipos"', motivo_chunk)
