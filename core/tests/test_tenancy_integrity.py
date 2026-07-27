from django.core.exceptions import ValidationError
from django.test import TestCase

from cadastros.models import Servidor
from cadastros.models import Unidade
from eventos.models import Evento
from oficios.models import Oficio
from usuarios.models import AreaTrabalho


class AreaRelationshipIntegrityTests(TestCase):
    def setUp(self):
        self.area_a = AreaTrabalho.objects.create(nome="Área A", sigla="ARA")
        self.area_b = AreaTrabalho.objects.create(nome="Área B", sigla="ARB")

    def test_fk_de_outra_area_e_rejeitada(self):
        unidade = Unidade.objects.create(nome="Unidade B", area=self.area_b)

        with self.assertRaises(ValidationError):
            Evento.objects.create(
                titulo="Evento A",
                area=self.area_a,
                unidade_responsavel=unidade,
            )

    def test_m2m_de_outra_area_e_rejeitada(self):
        oficio = Oficio.objects.create(area=self.area_a)
        servidor = Servidor.objects.create(nome="Servidor B", area=self.area_b)

        with self.assertRaises(ValidationError):
            oficio.servidores.add(servidor)

    def test_relacoes_da_mesma_area_sao_aceitas(self):
        oficio = Oficio.objects.create(area=self.area_a)
        servidor = Servidor.objects.create(nome="Servidor A", area=self.area_a)

        oficio.servidores.add(servidor)

        self.assertTrue(oficio.servidores.filter(pk=servidor.pk).exists())
