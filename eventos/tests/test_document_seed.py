from django.test import TestCase

from cadastros.models import Servidor
from core.testing import area_de_teste
from eventos.models import Evento
from eventos.services import build_evento_document_seed
from oficios.models import Oficio


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


class BuildEventoDocumentSeedServidoresTests(TestCase):
    def test_reune_servidores_de_todos_os_oficios_sem_duplicar(self):
        area = area_de_teste()
        evento = Evento.objects.create(area=area, titulo="Evento com dois ofícios")
        servidor_98 = Servidor.objects.create(area=area, nome="SERVIDOR DO OFÍCIO 98")
        servidor_99 = Servidor.objects.create(area=area, nome="SERVIDOR DO OFÍCIO 99")
        servidor_comum = Servidor.objects.create(area=area, nome="SERVIDOR COMUM")
        oficio_98 = Oficio.objects.create(area=area, evento=evento, numero=98, ano=2026)
        oficio_99 = Oficio.objects.create(area=area, evento=evento, numero=99, ano=2026)
        oficio_98.servidores.set([servidor_98, servidor_comum])
        oficio_99.servidores.set([servidor_99, servidor_comum])

        seed = build_evento_document_seed(evento)

        self.assertEqual(
            {servidor.pk for servidor in seed["servidores"]},
            {servidor_98.pk, servidor_99.pk, servidor_comum.pk},
        )
        self.assertEqual(len(seed["servidores"]), 3)
