from django.test import TestCase

from eventos.models import Evento
from eventos.services import build_evento_document_seed
from core.testing import area_de_teste


class BuildEventoDocumentSeedMotivoTests(TestCase):
    def test_motivo_do_evento_e_usado_no_seed(self):
        evento = Evento.objects.create(area=area_de_teste(), motivo="Motivo preenchido na etapa 1")
        seed = build_evento_document_seed(evento)
        self.assertEqual(seed["motivo"], "Motivo preenchido na etapa 1")

    def test_descricao_legada_e_usada_quando_motivo_vazio(self):
        evento = Evento.objects.create(area=area_de_teste(), descricao="Motivo legado via descricao")
        seed = build_evento_document_seed(evento)
        self.assertEqual(seed["motivo"], "Motivo legado via descricao")

    def test_motivo_tem_prioridade_sobre_descricao(self):
        evento = Evento.objects.create(area=area_de_teste(), motivo="Motivo novo", descricao="Motivo legado")
        seed = build_evento_document_seed(evento)
        self.assertEqual(seed["motivo"], "Motivo novo")
