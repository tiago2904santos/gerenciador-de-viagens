from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Estado
from cadastros.models import Cidade
from cadastros.models import Servidor
from cadastros.models import Unidade
from cadastros.models import Viatura
from cadastros.models import Combustivel
from oficios.models import Oficio
from roteiros.models import Roteiro


class OficioWizardRoteiroDiariasTests(TestCase):
    """Etapa 3 do ofício reutiliza o editor de roteiros e multiplica diárias pelos viajantes."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester_wizard_roteiro",
            password="123456",
        )
        self.client.force_login(self.user)
        self.cargo = Cargo.objects.create(nome="Cargo WR")
        self.comb = Combustivel.objects.create(nome="Flex WR")
        self.servidor_a = Servidor.objects.create(nome="Viajante A", cargo=self.cargo, cpf="11122233344")
        self.servidor_b = Servidor.objects.create(nome="Viajante B", cargo=self.cargo, cpf="55566677788")
        self.unidade_m = Unidade.objects.create(nome="Unidade WR", sigla="UWR")
        self.motorista_v = Servidor.objects.create(
            nome="Motorista WR",
            cargo=self.cargo,
            cpf="99988877766",
            unidade=self.unidade_m,
        )
        self.viatura = Viatura.objects.create(
            placa="WRZ9999",
            modelo="Modelo WR",
            combustivel=self.comb,
            tipo=Viatura.TIPO_DESCARACTERIZADA,
        )
        self.viatura.motoristas.add(self.motorista_v)

    def _oficio_ate_transporte(self, servidor_pks):
        self.client.get(reverse("oficios:novo"))
        oficio = Oficio.objects.get()
        payload = {
            "protocolo": "12.345.678-9",
            "motivo": "Motivo roteiro wizard",
            "custeio": Oficio.CUSTEIO_UNIDADE_DPC,
            "custeio_observacao": "",
            "servidores": [str(pk) for pk in servidor_pks],
            "action": "save_continue",
        }
        self.client.post(reverse("oficios:dados_viajantes", args=[oficio.pk]), data=payload)
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

    def test_get_cria_roteiro_vinculado_e_renderiza_editor(self):
        oficio = self._oficio_ate_transporte([self.servidor_a.pk])
        self.assertIsNone(oficio.roteiro_id)

        response = self.client.get(reverse("oficios:wizard_roteiro", args=[oficio.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "oficios/wizard_roteiro.html")
        self.assertContains(response, 'id="roteiro-editor-form"')

        oficio.refresh_from_db()
        self.assertIsNotNone(oficio.roteiro_id)
        self.assertEqual(oficio.roteiro.tipo, Roteiro.TIPO_AVULSO)

    def test_hidden_quantidade_servidores_reflete_viajantes(self):
        oficio = self._oficio_ate_transporte([self.servidor_a.pk, self.servidor_b.pk])
        response = self.client.get(reverse("oficios:wizard_roteiro", args=[oficio.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="quantidade_servidores"')
        self.assertContains(response, 'value="2"')

    def test_post_vazio_permite_rascunho_incompleto_sem_redirect(self):
        """POST sem dados de roteiro não avança para o resumo (validação do editor)."""
        oficio = self._oficio_ate_transporte([self.servidor_a.pk])
        self.client.get(reverse("oficios:wizard_roteiro", args=[oficio.pk]))
        response = self.client.post(
            reverse("oficios:wizard_roteiro", args=[oficio.pk]),
            data={"action": "save_continue"},
        )
        self.assertEqual(response.status_code, 200)

    def test_wizard_resumo_e_alias_da_etapa_documentos(self):
        oficio = self._oficio_ate_transporte([self.servidor_a.pk])
        self.client.get(reverse("oficios:wizard_roteiro", args=[oficio.pk]))
        response = self.client.get(reverse("oficios:wizard_resumo", args=[oficio.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "oficios/wizard_documentos.html")

    def test_wizard_documentos_get(self):
        oficio = self._oficio_ate_transporte([self.servidor_a.pk])
        self.client.get(reverse("oficios:wizard_roteiro", args=[oficio.pk]))
        response = self.client.get(reverse("oficios:wizard_documentos", args=[oficio.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Documentos")

    def test_etapa3_preenche_sede_a_partir_das_configuracoes(self):
        """Roteiro sem origem salva recebe UF/cidade do singleton de configuração."""
        est = Estado.objects.create(nome="Paraná", sigla="PR")
        cidade_sede = Cidade.objects.create(nome="Curitiba", estado=est)
        cfg = ConfiguracaoSistema.get_singleton()
        cfg.cidade_sede_padrao = cidade_sede
        cfg.save()

        oficio = self._oficio_ate_transporte([self.servidor_a.pk])
        response = self.client.get(reverse("oficios:wizard_roteiro", args=[oficio.pk]))
        self.assertEqual(response.status_code, 200)
        oficio.refresh_from_db()
        roteiro = oficio.roteiro
        self.assertIsNone(roteiro.origem_estado_id)
        self.assertIsNone(roteiro.origem_cidade_id)

        self.assertContains(response, f'<option value="{est.pk}" selected')
        self.assertContains(response, f'<option value="{cidade_sede.pk}" selected')

    @patch("cadastros.services.consultar_cep_externo")
    def test_etapa3_preenche_sede_via_cep_sem_cidade_sede_padrao_fk(self, mock_consulta_cep):
        """Com apenas CEP nas Configurações, ViaCEP resolve UF/localidade e casa com a base."""
        est, _ = Estado.objects.get_or_create(
            sigla="ZZ",
            defaults={"nome": "Estado ZZ Teste", "codigo_ibge": 99},
        )
        cidade_cep, _ = Cidade.objects.get_or_create(
            estado=est,
            nome="Município CEP Wizard Teste",
            defaults={"uf": "ZZ"},
        )
        mock_consulta_cep.return_value = {
            "cep": "01001-000",
            "logradouro": "",
            "bairro": "",
            "cidade": "Município CEP Wizard Teste",
            "uf": "ZZ",
        }
        cfg = ConfiguracaoSistema.get_singleton()
        cfg.cidade_sede_padrao = None
        cfg.uf = ""
        cfg.cidade_endereco = ""
        cfg.cep = "01001000"
        cfg.save()

        oficio = self._oficio_ate_transporte([self.servidor_a.pk])
        response = self.client.get(reverse("oficios:wizard_roteiro", args=[oficio.pk]))
        self.assertEqual(response.status_code, 200)
        mock_consulta_cep.assert_called()
        oficio.refresh_from_db()
        roteiro = oficio.roteiro
        self.assertIsNone(roteiro.origem_estado_id)
        self.assertIsNone(roteiro.origem_cidade_id)
        self.assertContains(response, f'<option value="{est.pk}" selected')
        self.assertContains(response, f'<option value="{cidade_cep.pk}" selected')
