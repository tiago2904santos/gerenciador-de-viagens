import json
from unittest.mock import patch

from django.conf import settings
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
from core.testing import area_de_teste
from core.testing import vincular_area


class OficioWizardRoteiroDiariasTests(TestCase):
    """Etapa 2 do ofício reutiliza o editor de roteiros e multiplica diárias pelos viajantes."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester_wizard_roteiro",
            password="123456",
        )
        self.client.force_login(self.user)
        vincular_area(self.user)
        self.cargo = Cargo.objects.create(area=area_de_teste(), nome="Cargo WR")
        self.comb = Combustivel.objects.create(area=area_de_teste(), nome="Flex WR")
        self.servidor_a = Servidor.objects.create(area=area_de_teste(), nome="Viajante A", cargo=self.cargo, cpf="11122233344")
        self.servidor_b = Servidor.objects.create(area=area_de_teste(), nome="Viajante B", cargo=self.cargo, cpf="55566677788")
        self.unidade_m = Unidade.objects.create(area=area_de_teste(), nome="Unidade WR", sigla="UWR")
        self.motorista_v = Servidor.objects.create(area=area_de_teste(), 
            nome="Motorista WR",
            cargo=self.cargo,
            cpf="99988877766",
            unidade=self.unidade_m,
        )
        self.viatura = Viatura.objects.create(area=area_de_teste(), 
            placa="WRZ9999",
            modelo="Modelo WR",
            combustivel=self.comb,
            tipo=Viatura.TIPO_DESCARACTERIZADA,
        )
        self.viatura.motoristas.add(self.motorista_v)

    def _oficio_ate_transporte(self, servidor_pks):
        self.client.post(reverse("oficios:novo"))
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

    def test_get_nao_cria_roteiro_e_renderiza_editor(self):
        """Abrir a Etapa 2 sozinha nao deve gravar nenhum Roteiro no banco (so no save real)."""
        oficio = self._oficio_ate_transporte([self.servidor_a.pk])
        self.assertIsNone(oficio.roteiro_id)

        response = self.client.get(reverse("oficios:wizard_roteiro", args=[oficio.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "oficios/wizard_roteiro.html")
        self.assertContains(response, 'id="roteiro-editor-form"')
        html = response.content.decode()
        id_form = html.index('id="roteiro-editor-form"')
        inicio_form = html.rindex("<form", 0, id_form)
        fim_form = html.index("</form>", inicio_form)
        self.assertIn('name="csrfmiddlewaretoken"', html[inicio_form:fim_form])
        # O stepper do v2 numera pelo próprio marcador e nomeia a etapa pelo
        # título; a sobrancelha "Etapa 2" do stepper legado saiu junto com ele.
        # O que prova que a etapa certa está aberta é o `aria-current`, que é
        # também o que um leitor de tela anuncia.
        self.assertContains(response, 'aria-current="step"')
        self.assertContains(response, "Roteiro e diárias")
        self.assertContains(response, reverse("oficios:index"))
        self.assertContains(response, "Voltar à lista")
        self.assertContains(response, "card-footer")
        self.assertContains(response, "Avançar")

        oficio.refresh_from_db()
        self.assertIsNone(oficio.roteiro_id)

    def test_stepper_global_reserva_intervalo_antes_do_painel(self):
        """O gap pertence ao rail, inclusive quando um script JSON vem antes do form."""
        css = (settings.BASE_DIR / "static/css/v2/stepper.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            ".wizard-page > .rail {\n  margin-bottom: var(--gap);",
            css,
        )
        self.assertNotIn(".wizard-page > .rail + *", css)

    def test_autosave_criar_vincula_rascunho_ao_oficio_imediatamente(self):
        """Sem isso, desmarcar um roteiro salvo e comecar o proprio nao sobrevive a um
        reload: como oficio.roteiro_id continua None ate o save final, a proxima visita
        volta a sugerir o roteiro do evento — parecendo que "desmarcar" nao funciona."""
        oficio = self._oficio_ate_transporte([self.servidor_a.pk])
        self.assertIsNone(oficio.roteiro_id)

        response = self.client.post(
            reverse("oficios:wizard_roteiro_autosave_criar", args=[oficio.pk]),
            data=json.dumps({
                "model": "roteiro",
                "object_id": "",
                "dirty_fields": ["observacoes"],
                "fields": {"observacoes": "Rascunho proprio do oficio"},
                "snapshots": {},
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["created"])

        oficio.refresh_from_db()
        self.assertEqual(oficio.roteiro_id, payload["object_id"])
        self.assertEqual(oficio.roteiro.observacoes, "RASCUNHO PROPRIO DO OFICIO")

    def test_autosave_criar_sem_conteudo_minimo_nao_cria_nem_vincula(self):
        oficio = self._oficio_ate_transporte([self.servidor_a.pk])
        response = self.client.post(
            reverse("oficios:wizard_roteiro_autosave_criar", args=[oficio.pk]),
            data=json.dumps({
                "model": "roteiro",
                "object_id": "",
                "dirty_fields": [],
                "fields": {},
                "snapshots": {},
            }),
            content_type="application/json",
        )
        payload = response.json()
        self.assertFalse(payload["ok"])
        oficio.refresh_from_db()
        self.assertIsNone(oficio.roteiro_id)

    def test_hidden_quantidade_servidores_reflete_viajantes(self):
        oficio = self._oficio_ate_transporte([self.servidor_a.pk, self.servidor_b.pk])
        response = self.client.get(reverse("oficios:wizard_roteiro", args=[oficio.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="quantidade_servidores"')
        self.assertContains(response, 'value="2"')

    def test_post_vazio_com_wizard_next_faz_soft_advance(self):
        """POST incompleto com Avançar grava rascunho parcial e redireciona."""
        oficio = self._oficio_ate_transporte([self.servidor_a.pk])
        self.client.get(reverse("oficios:wizard_roteiro", args=[oficio.pk]))
        response = self.client.post(
            reverse("oficios:wizard_roteiro", args=[oficio.pk]),
            data={"action": "save_continue"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            response.url,
            {
                reverse("oficios:wizard_documentos", args=[oficio.pk]),
                reverse("oficios:wizard_justificativa", args=[oficio.pk]),
            },
        )
        oficio.refresh_from_db()
        self.assertIsNotNone(oficio.roteiro_id)
        self.assertEqual(oficio.roteiro.status, Roteiro.STATUS_RASCUNHO)

    def test_post_parcial_wizard_next_preserva_dados_ao_voltar(self):
        """Soft-advance com sede/destino parciais mantém os dados no GET de volta."""
        est = Estado.objects.create(nome="Paraná Soft", sigla="PS")
        sede = Cidade.objects.create(nome="Curitiba Soft", estado=est)
        destino = Cidade.objects.create(nome="Londrina Soft", estado=est)
        oficio = self._oficio_ate_transporte([self.servidor_a.pk])
        self.client.get(reverse("oficios:wizard_roteiro", args=[oficio.pk]))
        response = self.client.post(
            reverse("oficios:wizard_roteiro", args=[oficio.pk]),
            data={
                "action": "wizard_next",
                "origem_estado": str(est.pk),
                "origem_cidade": str(sede.pk),
                "destino_estado_0": str(est.pk),
                "destino_cidade_0": str(destino.pk),
            },
        )
        self.assertEqual(response.status_code, 302)
        oficio.refresh_from_db()
        self.assertIsNotNone(oficio.roteiro_id)
        roteiro = oficio.roteiro
        self.assertEqual(roteiro.status, Roteiro.STATUS_RASCUNHO)
        self.assertEqual(roteiro.origem_estado_id, est.pk)
        self.assertEqual(roteiro.origem_cidade_id, sede.pk)
        destinos = list(roteiro.destinos.order_by("ordem").values_list("cidade_id", flat=True))
        self.assertEqual(destinos, [destino.pk])

        get_back = self.client.get(reverse("oficios:wizard_roteiro", args=[oficio.pk]))
        self.assertEqual(get_back.status_code, 200)
        self.assertContains(get_back, f'value="{est.pk}" selected')
        self.assertContains(get_back, f'value="{sede.pk}" selected')
        self.assertContains(get_back, f'value="{destino.pk}"')

    def test_post_incompleto_save_draft_permanece_com_erros(self):
        """Salvar rascunho sem navegar continua na página e mostra erros de validação."""
        oficio = self._oficio_ate_transporte([self.servidor_a.pk])
        self.client.get(reverse("oficios:wizard_roteiro", args=[oficio.pk]))
        response = self.client.post(
            reverse("oficios:wizard_roteiro", args=[oficio.pk]),
            data={"action": "save_draft"},
        )
        self.assertEqual(response.status_code, 200)
        # `alert alert-danger` eram classes do Bootstrap legado, que o editor
        # escrevia à mão. O resumo de erros do v2 é o `.alert` do sistema com o
        # tom do estado — a mesma caixa de qualquer outra falha da tela.
        self.assertContains(response, 'class="alert"')
        self.assertContains(response, 'data-tone="error"')

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
        self.assertNotContains(response, "css/pages/roteiros.css")

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
        self.assertIsNone(oficio.roteiro_id)

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
        self.assertIsNone(oficio.roteiro_id)
        self.assertContains(response, f'<option value="{est.pk}" selected')
        self.assertContains(response, f'<option value="{cidade_cep.pk}" selected')
