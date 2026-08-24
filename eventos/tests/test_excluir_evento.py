from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from eventos.models import Evento
from eventos.services import excluir_evento
from oficios.models import Oficio
from prestacoes_contas.models import PrestacaoContas
from roteiros.models import Roteiro
from core.testing import area_de_teste
from core.testing import vincular_area


class ExcluirEventoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester_eventos",
            password="123456",
        )
        self.client.force_login(self.user)
        vincular_area(self.user)
        self.evento = Evento.objects.create(area=area_de_teste(), titulo="Evento de teste")

    def test_excluir_evento_exclui_roteiro_pertencente_apenas_a_ele(self):
        roteiro = Roteiro.objects.create(area=area_de_teste(), evento=self.evento)
        Oficio.objects.create(area=area_de_teste(), evento=self.evento, roteiro=roteiro)

        excluir_evento(self.evento)

        self.assertFalse(Evento.objects.filter(pk=self.evento.pk).exists())
        self.assertFalse(Roteiro.objects.filter(pk=roteiro.pk).exists())

    def test_excluir_evento_preserva_roteiro_usado_por_oficio_de_outro_evento(self):
        outro_evento = Evento.objects.create(area=area_de_teste(), titulo="Outro evento")
        roteiro = Roteiro.objects.create(area=area_de_teste(), evento=self.evento)
        Oficio.objects.create(area=area_de_teste(), evento=self.evento, roteiro=roteiro)
        oficio_outro_evento = Oficio.objects.create(area=area_de_teste(), evento=outro_evento, roteiro=roteiro)

        excluir_evento(self.evento)

        self.assertFalse(Evento.objects.filter(pk=self.evento.pk).exists())
        roteiro.refresh_from_db()
        self.assertIsNone(roteiro.evento_id)
        oficio_outro_evento.refresh_from_db()
        self.assertEqual(oficio_outro_evento.roteiro_id, roteiro.pk)

    def test_excluir_evento_preserva_roteiro_usado_por_oficio_avulso(self):
        roteiro = Roteiro.objects.create(area=area_de_teste(), evento=self.evento)
        Oficio.objects.create(area=area_de_teste(), evento=self.evento, roteiro=roteiro)
        oficio_avulso = Oficio.objects.create(area=area_de_teste(), evento=None, roteiro=roteiro)

        excluir_evento(self.evento)

        roteiro.refresh_from_db()
        self.assertIsNone(roteiro.evento_id)
        oficio_avulso.refresh_from_db()
        self.assertEqual(oficio_avulso.roteiro_id, roteiro.pk)

    def test_excluir_evento_preserva_roteiro_usado_em_prestacao_de_contas_de_outro_evento(self):
        outro_evento = Evento.objects.create(area=area_de_teste(), titulo="Outro evento")
        roteiro = Roteiro.objects.create(area=area_de_teste(), evento=self.evento)
        Oficio.objects.create(area=area_de_teste(), evento=self.evento, roteiro=roteiro)
        oficio_outro_evento = Oficio.objects.create(
            area=area_de_teste(), evento=outro_evento, protocolo="123456789"
        )
        prestacao = PrestacaoContas.objects.get(oficio=oficio_outro_evento)
        prestacao.roteiro_ajustado = roteiro
        prestacao.save(update_fields=["roteiro_ajustado", "atualizado_em"])

        excluir_evento(self.evento)

        roteiro.refresh_from_db()
        self.assertIsNone(roteiro.evento_id)
        prestacao.refresh_from_db()
        self.assertEqual(prestacao.roteiro_ajustado_id, roteiro.pk)

    def test_excluir_evento_exclui_oficio_proprio(self):
        oficio = Oficio.objects.create(area=area_de_teste(), evento=self.evento)

        excluir_evento(self.evento)

        self.assertFalse(Oficio.objects.filter(pk=oficio.pk).exists())

    def test_view_excluir_preserva_roteiro_de_outro_evento(self):
        outro_evento = Evento.objects.create(area=area_de_teste(), titulo="Outro evento")
        roteiro = Roteiro.objects.create(area=area_de_teste(), evento=self.evento)
        Oficio.objects.create(area=area_de_teste(), evento=self.evento, roteiro=roteiro)
        oficio_outro_evento = Oficio.objects.create(area=area_de_teste(), evento=outro_evento, roteiro=roteiro)

        response = self.client.post(reverse("eventos:excluir", args=[self.evento.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Evento.objects.filter(pk=self.evento.pk).exists())
        roteiro.refresh_from_db()
        self.assertIsNone(roteiro.evento_id)
        oficio_outro_evento.refresh_from_db()
        self.assertEqual(oficio_outro_evento.roteiro_id, roteiro.pk)
