from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import Combustivel
from cadastros.models import Servidor
from cadastros.models import Unidade
from cadastros.models import Viatura
from oficios.models import Oficio
from oficios.services import pendencias_motorista_documento
from oficios.services import validar_oficio_para_documento


class OficioWizardTransporteTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester_wizard_transporte",
            password="123456",
        )
        self.client.force_login(self.user)
        self.cargo = Cargo.objects.create(nome="Motorista Cargo")
        self.comb = Combustivel.objects.create(nome="Flex")
        self.servidor = Servidor.objects.create(nome="Motorista Servidor", cargo=self.cargo, cpf="11122233344")
        self.unidade_m = Unidade.objects.create(nome="ASCOM Central", sigla="ASCOM")
        self.motorista_viatura = Servidor.objects.create(
            nome="João da Silva",
            cargo=self.cargo,
            cpf="22233344455",
            unidade=self.unidade_m,
        )
        self.viatura = Viatura.objects.create(
            placa="ABC1234",
            modelo="Renault Duster",
            combustivel=self.comb,
            tipo=Viatura.TIPO_DESCARACTERIZADA,
            unidade=self.unidade_m,
        )
        self.viatura.motoristas.add(self.motorista_viatura)

    def _oficio_com_etapa1_minima(self):
        url_novo = self.client.get(reverse("oficios:novo")).url
        self.client.post(
            url_novo,
            data={
                "protocolo": "12.345.678-9",
                "motivo": "Motivo transporte",
                "custeio": Oficio.CUSTEIO_UNIDADE_DPC,
                "custeio_observacao": "",
                "servidores": [str(self.servidor.pk)],
                "action": "save_continue",
            },
        )
        return Oficio.objects.get()

    def _payload_transporte(self, **overrides):
        data = {
            "porte_transporte_armas": "sim",
            "motorista_modo": Oficio.MOTORISTA_MODO_SERVIDOR,
            "transporte_placa_manual": "",
            "transporte_modelo_manual": "",
            "transporte_combustivel_manual": "",
            "transporte_tipo_manual": "",
            "motorista": "",
            "motorista_manual_nome": "",
            "motorista_oficio_referencia": "",
            "motorista_protocolo_ref": "",
            "viatura": "",
            "action": "save_draft",
        }
        data.update(overrides)
        return data

    def test_get_transporte_renderiza(self):
        oficio = self._oficio_com_etapa1_minima()
        response = self.client.get(reverse("oficios:transporte", args=[oficio.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "oficios/wizard_transporte.html")
        self.assertContains(response, "Viatura")
        self.assertContains(response, "Motorista")
        self.assertContains(response, "Cadastrar nova viatura")
        self.assertContains(response, reverse("cadastros:viatura_create"))
        self.assertContains(response, reverse("cadastros:servidor_create"))
        self.assertContains(response, "Digite placa, modelo, unidade ou motorista")
        self.assertContains(response, "BUSCAR VIATURA")

    def test_post_save_draft_viatura_cadastrada(self):
        oficio = self._oficio_com_etapa1_minima()
        response = self.client.post(
            reverse("oficios:transporte", args=[oficio.pk]),
            data=self._payload_transporte(
                viatura=str(self.viatura.pk),
                action="save_draft",
            ),
        )
        self.assertEqual(response.status_code, 302)
        oficio.refresh_from_db()
        self.assertEqual(oficio.viatura_id, self.viatura.pk)

    def test_post_save_draft_viatura_manual(self):
        oficio = self._oficio_com_etapa1_minima()
        response = self.client.post(
            reverse("oficios:transporte", args=[oficio.pk]),
            data=self._payload_transporte(
                transporte_placa_manual="XYZ9876",
                transporte_modelo_manual="MODELO LIVRE",
                transporte_combustivel_manual=str(self.comb.pk),
                transporte_tipo_manual=Viatura.TIPO_DESCARACTERIZADA,
                porte_transporte_armas="nao",
                action="save_draft",
            ),
        )
        self.assertEqual(response.status_code, 302)
        oficio.refresh_from_db()
        self.assertIsNone(oficio.viatura_id)
        self.assertEqual(oficio.transporte_placa_manual, "XYZ9876")
        self.assertEqual(oficio.transporte_modelo_manual, "MODELO LIVRE")
        self.assertFalse(oficio.porte_transporte_armas)

    def test_post_motorista_servidor(self):
        oficio = self._oficio_com_etapa1_minima()
        response = self.client.post(
            reverse("oficios:transporte", args=[oficio.pk]),
            data=self._payload_transporte(
                motorista=str(self.servidor.pk),
                motorista_modo=Oficio.MOTORISTA_MODO_SERVIDOR,
                action="save_draft",
            ),
        )
        self.assertEqual(response.status_code, 302)
        oficio.refresh_from_db()
        self.assertEqual(oficio.motorista_id, self.servidor.pk)

    def test_post_motorista_manual(self):
        oficio = self._oficio_com_etapa1_minima()
        response = self.client.post(
            reverse("oficios:transporte", args=[oficio.pk]),
            data=self._payload_transporte(
                motorista_modo=Oficio.MOTORISTA_MODO_MANUAL,
                motorista_manual_nome="Externo Silva",
                motorista_oficio_referencia="10/2026",
                motorista_protocolo_ref="12.345.678-9",
                action="save_draft",
            ),
        )
        self.assertEqual(response.status_code, 302)
        oficio.refresh_from_db()
        self.assertIsNone(oficio.motorista_id)
        self.assertEqual(oficio.motorista_manual_nome, "EXTERNO SILVA")
        self.assertEqual(oficio.motorista_oficio_referencia, "10/2026")
        self.assertEqual(oficio.motorista_protocolo_ref, "123456789")

    def test_post_motorista_servidor_na_equipe_sem_oficio_motorista(self):
        oficio = self._oficio_com_etapa1_minima()
        response = self.client.post(
            reverse("oficios:transporte", args=[oficio.pk]),
            data=self._payload_transporte(
                motorista=str(self.servidor.pk),
                motorista_modo=Oficio.MOTORISTA_MODO_SERVIDOR,
                motorista_oficio_referencia="99/2099",
                motorista_protocolo_ref="11.111.111-1",
                action="save_draft",
            ),
        )
        self.assertEqual(response.status_code, 302)
        oficio.refresh_from_db()
        self.assertEqual(oficio.motorista_id, self.servidor.pk)
        self.assertEqual(oficio.motorista_oficio_referencia, "")
        self.assertEqual(oficio.motorista_protocolo_ref, "")

    def test_post_motorista_servidor_fora_equipe_com_oficio_protocolo(self):
        externo = Servidor.objects.create(nome="Fora Equipe", cargo=self.cargo, cpf="33344455566")
        oficio = self._oficio_com_etapa1_minima()
        response = self.client.post(
            reverse("oficios:transporte", args=[oficio.pk]),
            data=self._payload_transporte(
                motorista=str(externo.pk),
                motorista_modo=Oficio.MOTORISTA_MODO_SERVIDOR,
                motorista_oficio_referencia="7/2026",
                motorista_protocolo_ref="99.887.766-5",
                action="save_draft",
            ),
        )
        self.assertEqual(response.status_code, 302)
        oficio.refresh_from_db()
        self.assertEqual(oficio.motorista_id, externo.pk)
        self.assertEqual(oficio.motorista_oficio_referencia, "7/2026")
        self.assertEqual(oficio.motorista_protocolo_ref, "998877665")

    def test_documento_nao_exige_motorista_equipe(self):
        oficio = self._oficio_com_etapa1_minima()
        self.client.post(
            reverse("oficios:transporte", args=[oficio.pk]),
            data=self._payload_transporte(motorista=str(self.servidor.pk)),
        )
        oficio.refresh_from_db()
        self.assertEqual(pendencias_motorista_documento(oficio), [])

    def test_documento_exige_oficio_protocolo_motorista_manual(self):
        oficio = self._oficio_com_etapa1_minima()
        oficio.motorista_modo = Oficio.MOTORISTA_MODO_MANUAL
        oficio.motorista_manual_nome = "Nome Manual"
        oficio.motorista_oficio_referencia = ""
        oficio.motorista_protocolo_ref = ""
        oficio.save()
        p = pendencias_motorista_documento(oficio)
        self.assertTrue(any("ofício do motorista" in x.lower() for x in p))
        self.assertTrue(any("protocolo do motorista" in x.lower() for x in p))

    def test_documento_exige_oficio_protocolo_motorista_fora_equipe(self):
        externo = Servidor.objects.create(nome="Fora Equipe Doc", cargo=self.cargo, cpf="44455566677")
        oficio = self._oficio_com_etapa1_minima()
        oficio.motorista = externo
        oficio.motorista_modo = Oficio.MOTORISTA_MODO_SERVIDOR
        oficio.save()
        p = pendencias_motorista_documento(oficio)
        self.assertTrue(len(p) >= 2)

    def test_validar_documento_agrega_pendencias_motorista(self):
        oficio = self._oficio_com_etapa1_minima()
        oficio.motivo = "Motivo transporte"
        oficio.protocolo = "123456789"
        oficio.save()
        oficio.servidores.add(self.servidor)
        oficio.motorista_modo = Oficio.MOTORISTA_MODO_MANUAL
        oficio.motorista_manual_nome = "Zé"
        oficio.save()
        avaliacao = validar_oficio_para_documento(oficio)
        self.assertTrue(avaliacao["pendencias"])

    def test_save_continue_redireciona_roteiro(self):
        oficio = self._oficio_com_etapa1_minima()
        response = self.client.post(
            reverse("oficios:transporte", args=[oficio.pk]),
            data=self._payload_transporte(action="save_continue"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("oficios:wizard_roteiro", args=[oficio.pk]))

    def test_api_viatura_legacy_apenas_placa(self):
        oficio = self._oficio_com_etapa1_minima()
        response = self.client.get(
            reverse("oficios:api_viatura_por_placa", args=[oficio.pk]),
            data={"placa": "ABC-1234"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["found"])
        self.assertEqual(payload["id"], self.viatura.pk)

    def test_api_busca_q_retorna_por_placa(self):
        oficio = self._oficio_com_etapa1_minima()
        response = self.client.get(
            reverse("oficios:api_viatura_por_placa", args=[oficio.pk]),
            data={"q": "ABC1"},
        )
        self.assertEqual(response.status_code, 200)
        ids = [row["id"] for row in response.json()["results"]]
        self.assertIn(self.viatura.pk, ids)

    def test_api_busca_q_retorna_por_modelo(self):
        oficio = self._oficio_com_etapa1_minima()
        response = self.client.get(
            reverse("oficios:api_viatura_por_placa", args=[oficio.pk]),
            data={"q": "Duster"},
        )
        self.assertEqual(response.status_code, 200)
        ids = [row["id"] for row in response.json()["results"]]
        self.assertIn(self.viatura.pk, ids)

    def test_api_busca_q_retorna_por_unidade(self):
        oficio = self._oficio_com_etapa1_minima()
        response = self.client.get(
            reverse("oficios:api_viatura_por_placa", args=[oficio.pk]),
            data={"q": "ASCOM"},
        )
        self.assertEqual(response.status_code, 200)
        ids = [row["id"] for row in response.json()["results"]]
        self.assertIn(self.viatura.pk, ids)

    def test_api_busca_q_retorna_por_unidade_vinculada_a_viatura(self):
        self.viatura.motoristas.clear()
        oficio = self._oficio_com_etapa1_minima()
        response = self.client.get(
            reverse("oficios:api_viatura_por_placa", args=[oficio.pk]),
            data={"q": "ASCOM"},
        )
        self.assertEqual(response.status_code, 200)
        ids = [row["id"] for row in response.json()["results"]]
        self.assertIn(self.viatura.pk, ids)

    def test_api_busca_q_retorna_por_motorista(self):
        oficio = self._oficio_com_etapa1_minima()
        response = self.client.get(
            reverse("oficios:api_viatura_por_placa", args=[oficio.pk]),
            data={"q": "Silva"},
        )
        self.assertEqual(response.status_code, 200)
        ids = [row["id"] for row in response.json()["results"]]
        self.assertIn(self.viatura.pk, ids)

    def test_api_busca_q_curto_retorna_vazio(self):
        oficio = self._oficio_com_etapa1_minima()
        response = self.client.get(
            reverse("oficios:api_viatura_por_placa", args=[oficio.pk]),
            data={"q": "A"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

    def test_api_prefiltro_equipe_sem_termo(self):
        self.servidor.unidade = self.unidade_m
        self.servidor.save(update_fields=["unidade"])
        oficio = self._oficio_com_etapa1_minima()
        response = self.client.get(
            reverse("oficios:api_viatura_por_placa", args=[oficio.pk]),
            data={"q": ""},
        )
        self.assertEqual(response.status_code, 200)
        ids = [row["id"] for row in response.json()["results"]]
        self.assertIn(self.viatura.pk, ids)

    def test_post_transporte_nao_apaga_dados_viajantes(self):
        oficio = self._oficio_com_etapa1_minima()
        self.assertEqual(oficio.motivo, "Motivo transporte")
        self.client.post(
            reverse("oficios:transporte", args=[oficio.pk]),
            data=self._payload_transporte(motorista=str(self.servidor.pk)),
        )
        oficio.refresh_from_db()
        self.assertEqual(oficio.motivo, "Motivo transporte")
