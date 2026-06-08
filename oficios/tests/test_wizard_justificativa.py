import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Cargo
from cadastros.models import Combustivel
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Servidor
from cadastros.models import Unidade
from cadastros.models import Viatura
from justificativas.services import oficio_exige_justificativa
from oficios.models import Oficio
from roteiros.models import Roteiro


class WizardJustificativaTests(TestCase):
    """Etapa 3 â€” Justificativa â€” rotas e fluxo condicional."""

    def setUp(self):
        ConfiguracaoSistema.get_singleton()
        self.user = get_user_model().objects.create_user(
            username="tester_wizard_justificativa",
            password="123456",
        )
        self.client.force_login(self.user)
        self.cargo = Cargo.objects.create(nome="Cargo J")
        self.comb = Combustivel.objects.create(nome="Flex J")
        self.servidor_a = Servidor.objects.create(nome="Viajante J", cargo=self.cargo, cpf="11122233344")
        self.unidade_m = Unidade.objects.create(nome="Unidade J", sigla="UJ")
        self.motorista_v = Servidor.objects.create(
            nome="Motorista J",
            cargo=self.cargo,
            cpf="99988877766",
            unidade=self.unidade_m,
        )
        self.viatura = Viatura.objects.create(
            placa="JRZ9999",
            modelo="Modelo J",
            combustivel=self.comb,
            tipo=Viatura.TIPO_DESCARACTERIZADA,
        )
        self.viatura.motoristas.add(self.motorista_v)

    def _oficio_ate_transporte(self):
        self.client.get(reverse("oficios:novo"))
        oficio = Oficio.objects.get()
        self.client.post(
            reverse("oficios:dados_viajantes", args=[oficio.pk]),
            data={
                "protocolo": "12.345.678-9",
                "motivo": "Motivo etapa justificativa",
                "custeio": Oficio.CUSTEIO_UNIDADE_DPC,
                "custeio_observacao": "",
                "servidores": [str(self.servidor_a.pk)],
                "action": "save_continue",
            },
        )
        oficio.refresh_from_db()
        self.client.post(
            reverse("oficios:transporte", args=[oficio.pk]),
            data={
                "porte_transporte_armas": "sim",
                "motorista_modo": Oficio.MOTORISTA_MODO_SERVIDOR,
                "motorista": str(self.motorista_v.pk),
                "viatura": str(self.viatura.pk),
                "transporte_placa_manual": "",
                "transporte_modelo_manual": "",
                "transporte_combustivel_manual": "",
                "transporte_tipo_manual": "",
                "motorista_manual_nome": "",
                "motorista_oficio_referencia": "",
                "motorista_protocolo_ref": "",
                "action": "save_continue",
            },
        )
        return Oficio.objects.get(pk=oficio.pk)

    def _roteiro_com_saida(self, oficio, dias_apos_criacao=5):
        self.client.get(reverse("oficios:wizard_roteiro", args=[oficio.pk]))
        oficio.refresh_from_db()
        roteiro = oficio.roteiro
        base = oficio.data_criacao
        d_saida = base + datetime.timedelta(days=dias_apos_criacao)
        roteiro.saida_dt = timezone.make_aware(
            datetime.datetime.combine(d_saida, datetime.time(8, 0)),
            timezone.get_current_timezone(),
        )
        roteiro.origem_estado_id = None
        roteiro.save(update_fields=["saida_dt"])
        return roteiro

    def test_get_etapa_justificativa_200(self):
        oficio = self._oficio_ate_transporte()
        self._roteiro_com_saida(oficio, 5)
        url = reverse("oficios:wizard_justificativa", args=[oficio.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "oficios/wizard_justificativa.html")
        self.assertContains(response, "cv-wizard-section-card oficio-justificativa-card")
        self.assertContains(response, "wizard-inner-section")
        self.assertContains(response, "Gerenciar modelos")
        self.assertContains(response, "Justificativa")
        self.assertContains(response, "data-modelo-justificativa-select")
        self.assertContains(response, reverse("justificativas:index"))
        self.assertContains(response, reverse('oficios:index'))
        self.assertContains(response, 'Voltar à lista')
        self.assertContains(response, "cv-card-footer-section")
        self.assertContains(response, 'data-autosave-link="1"')
        self.assertContains(response, "Avançar")
        self.assertNotContains(response, "cv-field-panel justificativa-panel")

    def test_stepper_contem_justificativa(self):
        oficio = self._oficio_ate_transporte()
        self._roteiro_com_saida(oficio, 11)
        response = self.client.get(reverse("oficios:wizard_justificativa", args=[oficio.pk]))
        self.assertContains(response, "Justificativa")
        self.assertContains(response, "page-stepper")

    def test_exige_justificativa_menor_igual_10_dias(self):
        oficio = self._oficio_ate_transporte()
        self._roteiro_com_saida(oficio, 10)
        self.assertTrue(oficio_exige_justificativa(oficio))

    def test_nao_exige_maior_que_10_dias(self):
        oficio = self._oficio_ate_transporte()
        self._roteiro_com_saida(oficio, 11)
        self.assertFalse(oficio_exige_justificativa(oficio))

    def test_obrigatoria_sem_texto_nao_redireciona(self):
        oficio = self._oficio_ate_transporte()
        self._roteiro_com_saida(oficio, 5)
        self.assertTrue(oficio_exige_justificativa(oficio))
        url = reverse("oficios:wizard_justificativa", args=[oficio.pk])
        response = self.client.post(
            url,
            data={
                "modelo": "",
                "texto": "",
                "action": "save_continue",
            },
        )
        self.assertEqual(response.status_code, 200)

    def test_obrigatoria_com_texto_redireciona_documentos(self):
        oficio = self._oficio_ate_transporte()
        self._roteiro_com_saida(oficio, 5)
        url = reverse("oficios:wizard_justificativa", args=[oficio.pk])
        response = self.client.post(
            url,
            data={
                "modelo": "",
                "texto": "Justificativa formal para viagem urgente.",
                "action": "save_continue",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("oficios:wizard_documentos", args=[oficio.pk]))

    def test_nao_obrigatoria_sem_texto_avanca(self):
        oficio = self._oficio_ate_transporte()
        self._roteiro_com_saida(oficio, 11)
        url = reverse("oficios:wizard_justificativa", args=[oficio.pk])
        response = self.client.post(
            url,
            data={
                "modelo": "",
                "texto": "",
                "action": "save_continue",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("oficios:wizard_documentos", args=[oficio.pk]))
