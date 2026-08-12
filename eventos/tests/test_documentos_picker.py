"""Cobre o picker de "Documentos vinculados" do evento: resumos, pré-filtro de
datas (proximidade) e a marcação do toggle segmentado no HTML renderizado."""
from datetime import date
from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from eventos.forms import EventoNovoCadastroForm
from eventos.models import Evento
from eventos.presenters import DOCUMENTO_FILTRO_DIAS_TOLERANCIA
from eventos.presenters import build_evento_documentos_context
from oficios.models import Oficio
from roteiros.models import Roteiro
from core.testing import area_de_teste
from core.testing import com_request
from core.testing import vincular_area


def _dt(y, m, d):
    return timezone.make_aware(datetime(y, m, d, 8, 0))


class DocumentosPickerContextTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="picker", password="123456")
        self.client.force_login(self.user)
        vincular_area(self.user)
        self.evento = Evento.objects.create(area=area_de_teste(), 
            titulo="Evento base",
            data_inicio=date(2026, 8, 10),
            data_fim=date(2026, 8, 12),
        )

    def _summary(self, resumos, key, pk):
        return next((s for s in resumos[key] if s["id"] == pk), None)

    def test_build_context_gera_resumos_e_datas(self):
        roteiro = Roteiro.objects.create(area=area_de_teste(), saida_dt=_dt(2026, 8, 10), retorno_chegada_dt=_dt(2026, 8, 12))
        oficio = Oficio.objects.create(area=area_de_teste(), roteiro=roteiro)

        # DB-02: o form recorta os pickers pela area do request no __init__
        # (BE-04); a chamada direta reproduz o contexto que a view teria.
        with com_request(area_de_teste()):
            form = EventoNovoCadastroForm(instance=self.evento)
            context = build_evento_documentos_context(form)

        self.assertIn("evento_doc_summaries", context)
        self.assertEqual(context["evento_doc_tolerancia_dias"], DOCUMENTO_FILTRO_DIAS_TOLERANCIA)
        self.assertEqual(context["evento_doc_periodo"], {"inicio": "2026-08-10", "fim": "2026-08-12"})

        resumo = self._summary(context["evento_doc_summaries"], "oficios", oficio.pk)
        self.assertIsNotNone(resumo)
        self.assertEqual(resumo["data_inicio"], "2026-08-10")
        self.assertEqual(resumo["data_fim"], "2026-08-12")
        self.assertIn("Ofício", resumo["title"])

    def test_pagina_renderiza_toggle_segmentado_e_json(self):
        Oficio.objects.create(area=area_de_teste(), 
            roteiro=Roteiro.objects.create(area=area_de_teste(), saida_dt=_dt(2026, 8, 10), retorno_chegada_dt=_dt(2026, 8, 11)),
        )
        url = reverse("eventos:guiado_etapa", kwargs={"pk": self.evento.pk, "etapa": 1})
        html = self.client.get(url).content.decode("utf-8")

        self.assertIn("segment-toggle evento-doc-toggle", html)
        self.assertIn("data-evento-doc-toggle", html)
        self.assertIn('id="evento-doc-summaries"', html)
        self.assertIn('data-evento-doc-field="oficios"', html)
        # O <select> de origem fica oculto (a lista é montada pelo JS).
        self.assertIn("evento-doc-source-select", html)

    def test_periodo_referencia_usa_dados_do_form_bound(self):
        form = EventoNovoCadastroForm(
            data={"data_inicio": "2026-09-01", "data_fim": "2026-09-05"},
            instance=self.evento,
        )
        context = build_evento_documentos_context(form)
        self.assertEqual(context["evento_doc_periodo"], {"inicio": "2026-09-01", "fim": "2026-09-05"})
