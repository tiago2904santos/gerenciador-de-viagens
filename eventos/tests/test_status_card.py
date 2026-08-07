from datetime import timedelta

from django.core.files.base import ContentFile
from django.test import TestCase
from django.utils import timezone

from eventos.models import Evento, EventoAnexo
from eventos.presenters import apresentar_evento_list_card
from oficios.models import Oficio
from core.testing import area_de_teste


def _evento_com_prefetch(pk):
    """Recarrega o evento com os mesmos prefetches usados na view de listagem."""
    return (
        Evento.objects.prefetch_related(
            "anexos",
            "oficios",
            "oficios__roteiro",
            "oficios__roteiro__origem_cidade",
            "roteiros",
            "roteiros__origem_cidade",
            "planos_trabalho",
            "ordens_servico",
            "documentos_solicitacao",
        )
        .get(pk=pk)
    )


class EventoStatusCardTests(TestCase):
    def test_evento_sem_documentos_fica_rascunho(self):
        evento = Evento.objects.create(area=area_de_teste(), titulo="Evento vazio")
        card = apresentar_evento_list_card(_evento_com_prefetch(evento.pk))
        self.assertEqual(card["status_label"], "Rascunho")
        self.assertEqual(card["status_state"], "warning")

    def test_oficio_pendente_bloqueia_mesmo_com_convite(self):
        evento = Evento.objects.create(area=area_de_teste(), titulo="Evento com ofício pendente")
        Oficio.objects.create(area=area_de_teste(), evento=evento, status=Oficio.STATUS_RASCUNHO, assunto="x")
        EventoAnexo.objects.create(
            evento=evento, tipo=EventoAnexo.TIPO_CONVITE,
            arquivo=ContentFile(b"conteudo", name="convite.pdf"),
        )
        card = apresentar_evento_list_card(_evento_com_prefetch(evento.pk))
        self.assertEqual(card["status_label"], "Rascunho")

    def test_convite_sem_oficio_pendente_fica_pronto(self):
        evento = Evento.objects.create(area=area_de_teste(), titulo="Evento só com convite")
        EventoAnexo.objects.create(
            evento=evento, tipo=EventoAnexo.TIPO_CONVITE,
            arquivo=ContentFile(b"conteudo", name="convite.pdf"),
        )
        card = apresentar_evento_list_card(_evento_com_prefetch(evento.pk))
        # Sem roteiro/saída: cai no rótulo genérico "Pronto".
        self.assertEqual(card["status_label"], "Pronto")
        self.assertEqual(card["status_state"], "success")

    def test_oficio_gerado_com_convite_mostra_contagem_ate_saida(self):
        from roteiros.models import Roteiro

        evento = Evento.objects.create(area=area_de_teste(), titulo="Evento pronto com saída futura")
        saida = timezone.now() + timedelta(days=5)
        roteiro = Roteiro.objects.create(area=area_de_teste(), saida_dt=saida, evento=evento)
        oficio = Oficio.objects.create(area=area_de_teste(), evento=evento, status=Oficio.STATUS_GERADO, assunto="x")
        oficio.roteiro = roteiro
        oficio.save(update_fields=["roteiro"])
        EventoAnexo.objects.create(
            evento=evento, tipo=EventoAnexo.TIPO_CONVITE,
            arquivo=ContentFile(b"c", name="convite.pdf"),
        )
        card = apresentar_evento_list_card(_evento_com_prefetch(evento.pk))
        self.assertIn("faltam 5 dias", card["status_label"])
        self.assertEqual(card["status_state"], "warning")

    def test_evento_cancelado_mostra_cancelado(self):
        evento = Evento.objects.create(area=area_de_teste(), titulo="Evento cancelado", status=Evento.STATUS_CANCELADO)
        card = apresentar_evento_list_card(_evento_com_prefetch(evento.pk))
        self.assertEqual(card["status_label"], "Cancelado")
        self.assertEqual(card["status_state"], "danger")
