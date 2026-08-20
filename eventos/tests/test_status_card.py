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

    def test_os_dois_selos_separam_situacao_de_quando(self):
        """Situação e tempo são DOIS selos desde 2026-08-19.

        Antes eram um só, e a viagem sequestrava o rótulo: um evento pronto
        dizia "faltam 5 dias" e não dizia mais que estava pronto — e um evento
        em rascunho não dizia quando ia acontecer.
        """
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

        self.assertEqual(card["status_label"], "Pronto")
        rotulos = [chip["label"] for chip in card["chips_v2"]]
        self.assertEqual(rotulos[0], "Pronto")
        self.assertIn("faltam 5 dias", rotulos[1])

    def test_evento_em_rascunho_tambem_diz_quando_acontece(self):
        """O selo do tempo não depende de o documento estar pronto."""
        from roteiros.models import Roteiro

        evento = Evento.objects.create(area=area_de_teste(), titulo="Rascunho com saída futura")
        Roteiro.objects.create(
            area=area_de_teste(), saida_dt=timezone.now() + timedelta(days=3), evento=evento,
        )
        card = apresentar_evento_list_card(_evento_com_prefetch(evento.pk))

        self.assertEqual(card["status_label"], "Rascunho")
        self.assertIn("faltam 3 dias", [chip["label"] for chip in card["chips_v2"]])

    def test_realizado_nao_se_confunde_com_em_andamento(self):
        """Duas viagens passadas e presentes recebem selos DIFERENTES."""
        from roteiros.models import Roteiro

        agora = timezone.now()
        passado = Evento.objects.create(area=area_de_teste(), titulo="Já foi")
        Roteiro.objects.create(
            area=area_de_teste(), saida_dt=agora - timedelta(days=9),
            retorno_chegada_dt=agora - timedelta(days=7), evento=passado,
        )
        presente = Evento.objects.create(area=area_de_teste(), titulo="Acontecendo")
        Roteiro.objects.create(
            area=area_de_teste(), saida_dt=agora - timedelta(days=1),
            retorno_chegada_dt=agora + timedelta(days=1), evento=presente,
        )

        rotulos_passado = [c["label"] for c in apresentar_evento_list_card(_evento_com_prefetch(passado.pk))["chips_v2"]]
        rotulos_presente = [c["label"] for c in apresentar_evento_list_card(_evento_com_prefetch(presente.pk))["chips_v2"]]

        self.assertIn("Realizado", rotulos_passado)
        self.assertIn("Em andamento", rotulos_presente)
        self.assertNotIn("Realizado", rotulos_presente)

    def test_evento_cancelado_nao_recebe_selo_de_tempo(self):
        """Contar dias de uma viagem que não vai haver só atrapalha."""
        from roteiros.models import Roteiro

        evento = Evento.objects.create(
            area=area_de_teste(), titulo="Cancelado com saída futura", status=Evento.STATUS_CANCELADO,
        )
        Roteiro.objects.create(
            area=area_de_teste(), saida_dt=timezone.now() + timedelta(days=4), evento=evento,
        )
        card = apresentar_evento_list_card(_evento_com_prefetch(evento.pk))

        self.assertEqual([c["label"] for c in card["chips_v2"]], ["Cancelado"])

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
        # A contagem vive no SEGUNDO selo; o primeiro fala da situação.
        self.assertIn("faltam 5 dias", [chip["label"] for chip in card["chips_v2"]])
        self.assertEqual(card["status_label"], "Pronto")

    def test_evento_cancelado_mostra_cancelado(self):
        evento = Evento.objects.create(area=area_de_teste(), titulo="Evento cancelado", status=Evento.STATUS_CANCELADO)
        card = apresentar_evento_list_card(_evento_com_prefetch(evento.pk))
        self.assertEqual(card["status_label"], "Cancelado")
        self.assertEqual(card["status_state"], "danger")
