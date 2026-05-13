import datetime

from django.test import TestCase
from django.utils import timezone

from cadastros.models import ConfiguracaoSistema
from justificativas.forms import JustificativaOficioForm
from justificativas.models import Justificativa
from justificativas.models import ModeloJustificativa
from justificativas.services import atualizar_justificativa_oficio
from justificativas.services import avaliar_etapa_justificativa_oficio
from justificativas.services import get_or_create_justificativa_oficio
from justificativas.services import justificativa_oficio_esta_completa
from justificativas.services import oficio_exige_justificativa
from oficios.models import Oficio
from roteiros.models import Roteiro


class JustificativaFormServicesLayerTests(TestCase):
    def setUp(self):
        ConfiguracaoSistema.get_singleton()

    def _oficio_com_saida(self, dias_para_saida=11):
        base = datetime.date(2026, 5, 10)
        roteiro = Roteiro.objects.create(tipo=Roteiro.TIPO_AVULSO, status=Roteiro.STATUS_RASCUNHO)
        d_saida = base + datetime.timedelta(days=dias_para_saida)
        roteiro.saida_dt = timezone.make_aware(
            datetime.datetime.combine(d_saida, datetime.time(8, 0)),
            timezone.get_current_timezone(),
        )
        roteiro.save(update_fields=["saida_dt"])
        return Oficio.objects.create(data_criacao=base, roteiro=roteiro)

    def test_obrigatorio_sem_texto_form_invalido(self):
        oficio = self._oficio_com_saida(5)
        self.assertTrue(oficio_exige_justificativa(oficio))
        j = get_or_create_justificativa_oficio(oficio)
        form = JustificativaOficioForm(
            data={"modelo": "", "texto": ""},
            instance=j,
            obrigatoria=True,
        )
        self.assertFalse(form.is_valid())

    def test_obrigatorio_com_texto_form_valido(self):
        oficio = self._oficio_com_saida(5)
        self.assertTrue(oficio_exige_justificativa(oficio))
        j = get_or_create_justificativa_oficio(oficio)
        form = JustificativaOficioForm(
            data={"modelo": "", "texto": "Motivo formal"},
            instance=j,
            obrigatoria=True,
        )
        self.assertTrue(form.is_valid())

    def test_nao_obrigatorio_sem_texto_form_valido(self):
        oficio = self._oficio_com_saida(11)
        self.assertFalse(oficio_exige_justificativa(oficio))
        j = get_or_create_justificativa_oficio(oficio)
        form = JustificativaOficioForm(
            data={"modelo": "", "texto": ""},
            instance=j,
            obrigatoria=False,
        )
        self.assertTrue(form.is_valid())

    def test_save_continue_marca_finalizada(self):
        oficio = self._oficio_com_saida(11)
        j = get_or_create_justificativa_oficio(oficio)
        form = JustificativaOficioForm(
            data={"modelo": "", "texto": ""},
            instance=j,
            obrigatoria=False,
        )
        self.assertTrue(form.is_valid())
        atualizar_justificativa_oficio(oficio, form, action="save_continue")
        j.refresh_from_db()
        self.assertEqual(j.status, Justificativa.STATUS_FINALIZADA)

    def test_save_draft_mantem_rascunho(self):
        oficio = self._oficio_com_saida(11)
        j = get_or_create_justificativa_oficio(oficio)
        form = JustificativaOficioForm(
            data={"modelo": "", "texto": "rascunho"},
            instance=j,
            obrigatoria=False,
        )
        self.assertTrue(form.is_valid())
        atualizar_justificativa_oficio(oficio, form, action="save_draft")
        j.refresh_from_db()
        self.assertEqual(j.status, Justificativa.STATUS_RASCUNHO)

    def test_snapshots_gravados_em_get_or_create(self):
        oficio = self._oficio_com_saida(10)
        j = get_or_create_justificativa_oficio(oficio)
        self.assertTrue(j.obrigatoria)
        self.assertEqual(j.prazo_dias, 10)

    def test_avaliar_etapa_obrigatorio_incompleto_e_completo(self):
        oficio = self._oficio_com_saida(3)
        ev = avaliar_etapa_justificativa_oficio(oficio)
        self.assertEqual(ev["status"], "incomplete")
        j = get_or_create_justificativa_oficio(oficio)
        j.texto = "ok"
        j.save(update_fields=["texto", "updated_at"])
        ev2 = avaliar_etapa_justificativa_oficio(oficio)
        self.assertEqual(ev2["status"], "complete")

    def test_justificativa_completa_nao_obrigatoria(self):
        oficio = self._oficio_com_saida(11)
        self.assertTrue(justificativa_oficio_esta_completa(oficio))

    def test_modelo_opcional_no_form(self):
        modelo = ModeloJustificativa.objects.create(nome="PADRAO X", texto="Bloco")
        oficio = self._oficio_com_saida(11)
        j = get_or_create_justificativa_oficio(oficio)
        form = JustificativaOficioForm(
            data={"modelo": str(modelo.pk), "texto": ""},
            instance=j,
            obrigatoria=False,
        )
        self.assertTrue(form.is_valid())
