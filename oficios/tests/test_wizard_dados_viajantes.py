from pathlib import Path
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Cargo
from cadastros.models import Servidor
from cadastros.models import Unidade
from cadastros.models import Viatura
from oficios.models import ModeloMotivoOficio
from oficios.models import Oficio


class OficioWizardDadosViajantesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester_wizard_dados",
            password="123456",
        )
        self.client.force_login(self.user)
        self.cargo = Cargo.objects.create(nome="Analista Wizard")
        self.unidade = Unidade.objects.create(nome="Unidade Wizard", sigla="UW")
        self.servidor = Servidor.objects.create(nome="Servidor Wizard", cargo=self.cargo, cpf="12345678901")
        self.outro_servidor = Servidor.objects.create(
            nome="Outro Servidor Wizard",
            cargo=self.cargo,
            cpf="98765432100",
        )
        self.viatura = Viatura.objects.create(placa="ABC1234", modelo="Viatura Wizard")
        self.modelo_ativo = ModeloMotivoOficio.objects.create(nome="PADRAO", texto="Texto padrão ativo", ativo=True)
        ModeloMotivoOficio.objects.create(nome="INATIVO", texto="Texto inativo", ativo=False)

    def _payload(self, **overrides):
        data = {
            "protocolo": "12.345.678-9",
            "modelo_motivo": str(self.modelo_ativo.pk),
            "motivo": "Motivo inicial",
            "custeio": Oficio.CUSTEIO_UNIDADE_DPC,
            "custeio_observacao": "",
            "servidores": [str(self.servidor.pk)],
            "servidores_termo_autorizacao_present": "1",
            "servidores_termo_autorizacao": [str(self.servidor.pk)],
            "porte_transporte_armas": "sim",
            "motorista_modo": "SERVIDOR",
            "motorista": str(self.servidor.pk),
            "transporte_placa_manual": "",
            "transporte_modelo_manual": "",
            "transporte_combustivel_manual": "",
            "transporte_tipo_manual": "",
            "motorista_manual_nome": "",
            "motorista_oficio_referencia": "",
            "motorista_protocolo_ref": "",
            "action": "save_draft",
        }
        data.update(overrides)
        return data

    def _novo_rascunho_url(self):
        response = self.client.get(reverse("oficios:novo"))
        self.assertEqual(response.status_code, 302)
        return response.url

    def test_get_novo_renderiza_wizard(self):
        response = self.client.get(reverse("oficios:novo"))

        self.assertEqual(response.status_code, 302)
        oficio = Oficio.objects.get()
        self.assertEqual(response.url, reverse("oficios:dados_viajantes", args=[oficio.pk]))
        self.assertEqual(oficio.status, Oficio.STATUS_RASCUNHO)
        self.assertEqual(oficio.numero, 1)
        self.assertEqual(oficio.ano, timezone.localdate().year)
        self.assertEqual(oficio.data_criacao, timezone.localdate())

        response = self.client.get(response.url)
        self.assertTemplateUsed(response, "oficios/wizard_dados_viajantes.html")
        self.assertContains(response, "Cadastro de ofício")
        self.assertContains(response, "Dados e viajantes")
        self.assertContains(response, "Transporte")
        self.assertContains(response, "Roteiro e diárias")
        self.assertContains(response, "Justificativa")
        self.assertContains(response, "Documentos")
        self.assertContains(response, "N° do Ofício")
        self.assertContains(response, oficio.numero_formatado)
        self.assertContains(response, "Data criação:")
        self.assertContains(response, oficio.data_criacao.strftime("%d/%m/%Y"))
        self.assertContains(response, "cv-wizard-section-card")
        self.assertContains(response, "field-grid")
        self.assertNotContains(response, "DOCX")
        self.assertContains(response, "Avançar →")
        self.assertNotContains(response, "Gerado automaticamente ao salvar.")
        self.assertNotContains(response, "será definida automaticamente ao salvar")
        self.assertNotContains(response, "Status:")
        self.assertContains(response, "page-header-status-chip")
        self.assertContains(response, "page-stepper")
        self.assertContains(response, "page-shell--wizard")
        self.assertNotContains(response, "Pendências para concluir esta etapa")
        self.assertContains(response, "Protocolo")
        self.assertContains(response, "Custeio")
        self.assertContains(response, "Motivo")
        self.assertNotContains(response, "<h3>Termos de Autoriza")
        self.assertNotContains(response, "Escolha quais viajantes devem ter termo gerado.")
        self.assertNotContains(response, "data-oficio-termos-summary")
        self.assertNotContains(response, "oficio-termos-selector__list")
        self.assertContains(response, "oficio-termos-selector-field")
        self.assertContains(response, 'name="servidores_termo_autorizacao_present"')
        self.assertContains(response, 'name="servidores_termo_autorizacao"')
        self.assertContains(response, "app-termos-selector__native")
        self.assertContains(response, "js/oficios_termos_selector.js")
        self.assertContains(response, "Equipe do ofício")
        self.assertContains(response, "A busca mostra apenas viajantes finalizados e continua disponível após cada seleção.")
        self.assertContains(response, "Cadastrar novo viajante")
        self.assertContains(response, "Digite nome, RG ou CPF")
        self.assertContains(response, "A busca mostra apenas viajantes finalizados e continua disponível após cada seleção.")
        self.assertContains(response, 'data-app-multiselect="true"')
        self.assertContains(response, "app-multiselect__native")
        self.assertContains(response, 'data-placeholder="Digite nome, RG ou CPF"')
        self.assertContains(response, 'data-search-placeholder="Digite nome, RG ou CPF"')
        self.assertContains(response, 'data-empty-selected="Nenhum viajante selecionado."')
        self.assertContains(response, "data-main=")
        self.assertContains(response, "data-cpf=")
        self.assertContains(response, "data-rg=")
        self.assertContains(response, "data-cargo=")
        self.assertContains(response, "data-unidade=")
        self.assertContains(response, "js/components/app-multiselect.js")
        self.assertNotContains(response, "data-filterable-multiselect-input")
        self.assertNotContains(response, "js/components/filterable-multiselect.js")
        self.assertContains(response, "Gerenciar modelos")
        self.assertContains(response, reverse("oficios:modelos_motivo_index"))
        self.assertContains(response, "Use um modelo salvo ou descreva o motivo da viagem.")
        self.assertContains(response, "Modelo de motivo")
        self.assertContains(response, 'name="modelo_motivo"')
        self.assertContains(response, 'name="motivo"')
        self.assertContains(response, "wizard-inner-section")
        self.assertContains(response, "id=\"oficio-wizard-motivo\"")
        self.assertNotContains(
            response,
            "Escolha um modelo para iniciar com texto pré-preenchido ou escreva manualmente o motivo.",
        )
        self.assertNotContains(response, "Assunto e motivo")
        self.assertNotContains(response, "Contexto operacional")
        self.assertNotContains(response, "Is padrão")
        self.assertNotContains(response, 'name="numero"')
        self.assertNotContains(response, 'name="ano"')
        self.assertNotContains(response, 'name="data_criacao"')
        self.assertNotContains(response, 'name="status"')
        self.assertNotContains(response, 'href="#"')
        self.assertNotContains(response, 'style="')
        self.assertNotContains(response, "oficio-wizard__aside")

    def test_post_novo_save_draft_cria_e_redireciona_para_etapa(self):
        response = self.client.post(self._novo_rascunho_url(), data=self._payload(action="save_draft"))

        self.assertEqual(response.status_code, 302)
        oficio = Oficio.objects.get()
        self.assertEqual(response.url, reverse("oficios:dados_viajantes", args=[oficio.pk]))
        self.assertEqual(oficio.numero, 1)
        self.assertEqual(oficio.ano, timezone.localdate().year)
        self.assertEqual(oficio.numero_formatado, f"01/{timezone.localdate().year}")
        self.assertEqual(oficio.protocolo, "123456789")
        self.assertEqual(oficio.motivo, "Motivo inicial")
        self.assertEqual(oficio.status, Oficio.STATUS_RASCUNHO)
        self.assertEqual(list(oficio.servidores.all()), [self.servidor])
        self.assertEqual(list(oficio.servidores_termo_autorizacao.all()), [self.servidor])

    def test_post_novo_save_continue_cria_e_redireciona_para_transporte(self):
        response = self.client.post(self._novo_rascunho_url(), data=self._payload(action="save_continue"))

        self.assertEqual(response.status_code, 302)
        oficio = Oficio.objects.get()
        self.assertEqual(response.url, reverse("oficios:transporte", args=[oficio.pk]))
        self.assertEqual(oficio.status, Oficio.STATUS_GERADO)

    def test_get_dados_viajantes_renderiza_oficio_existente(self):
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            motivo="Motivo existente",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        oficio.servidores.add(self.servidor)

        response = self.client.get(reverse("oficios:dados_viajantes", args=[oficio.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "oficios/wizard_dados_viajantes.html")
        self.assertContains(response, "Motivo existente")
        self.assertContains(response, "page-stepper")
        self.assertContains(response, "page-shell--wizard")
        self.assertContains(response, "01/2026")
        self.assertContains(response, oficio.data_criacao.strftime("%d/%m/%Y"))
        self.assertContains(response, "page-header-status-chip")
        self.assertContains(response, oficio.get_status_display())

    def test_post_dados_viajantes_atualiza_sem_apagar_transporte(self):
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            assunto="Antigo",
            motivo="Antigo",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
            viatura=self.viatura,
            motorista=self.servidor,
        )
        oficio.servidores.add(self.servidor)

        response = self.client.post(
            reverse("oficios:dados_viajantes", args=[oficio.pk]),
            data=self._payload(
                motivo="Motivo atualizado",
                servidores=[str(self.outro_servidor.pk)],
                action="save_draft",
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("oficios:dados_viajantes", args=[oficio.pk]))
        oficio.refresh_from_db()
        self.assertEqual(oficio.numero, 1)
        self.assertEqual(oficio.ano, 2026)
        self.assertEqual(oficio.motivo, "Motivo atualizado")
        self.assertEqual(list(oficio.servidores.all()), [self.outro_servidor])
        self.assertEqual(oficio.viatura, self.viatura)
        self.assertEqual(oficio.motorista, self.servidor)

    def test_post_dados_viajantes_salva_multiplos_servidores(self):
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            assunto="Antigo",
            motivo="Antigo",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )

        response = self.client.post(
            reverse("oficios:dados_viajantes", args=[oficio.pk]),
            data=self._payload(
                servidores=[str(self.servidor.pk), str(self.outro_servidor.pk)],
                servidores_termo_autorizacao=[str(self.servidor.pk), str(self.outro_servidor.pk)],
                action="save_draft",
            ),
        )

        self.assertEqual(response.status_code, 302)
        oficio.refresh_from_db()
        self.assertEqual(set(oficio.servidores.all()), {self.servidor, self.outro_servidor})
        self.assertEqual(
            set(oficio.servidores_termo_autorizacao.all()),
            {self.servidor, self.outro_servidor},
        )

        response = self.client.get(reverse("oficios:dados_viajantes", args=[oficio.pk]))
        self.assertContains(response, f'<option value="{self.servidor.pk}" selected')
        self.assertContains(response, f'<option value="{self.outro_servidor.pk}" selected')

    def test_post_dados_viajantes_salva_apenas_servidores_selecionados_para_termo(self):
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            assunto="Antigo",
            motivo="Antigo",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )

        response = self.client.post(
            reverse("oficios:dados_viajantes", args=[oficio.pk]),
            data=self._payload(
                servidores=[str(self.servidor.pk), str(self.outro_servidor.pk)],
                servidores_termo_autorizacao_present="1",
                servidores_termo_autorizacao=[str(self.servidor.pk)],
                action="save_draft",
            ),
        )

        self.assertEqual(response.status_code, 302)
        oficio.refresh_from_db()
        self.assertEqual(set(oficio.servidores.all()), {self.servidor, self.outro_servidor})
        self.assertEqual(list(oficio.servidores_termo_autorizacao.all()), [self.servidor])

    def test_post_dados_viajantes_ignora_termo_fora_da_equipe(self):
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            assunto="Antigo",
            motivo="Antigo",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )

        response = self.client.post(
            reverse("oficios:dados_viajantes", args=[oficio.pk]),
            data=self._payload(
                servidores=[str(self.servidor.pk)],
                servidores_termo_autorizacao_present="1",
                servidores_termo_autorizacao=[str(self.outro_servidor.pk)],
                action="save_draft",
            ),
        )

        self.assertEqual(response.status_code, 302)
        oficio.refresh_from_db()
        self.assertEqual(list(oficio.servidores.all()), [self.servidor])
        self.assertEqual(list(oficio.servidores_termo_autorizacao.all()), [])

    def test_get_dados_viajantes_reexibe_servidores_de_termo_marcados(self):
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            motivo="Motivo existente",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        oficio.servidores.add(self.servidor, self.outro_servidor)
        oficio.servidores_termo_autorizacao.add(self.outro_servidor)

        response = self.client.get(reverse("oficios:dados_viajantes", args=[oficio.pk]))

        self.assertContains(response, 'name="servidores_termo_autorizacao"')
        self.assertContains(response, f'<option value="{self.outro_servidor.pk}" selected')

    def test_post_dados_viajantes_remove_termo_quando_servidor_sai_da_equipe(self):
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            motivo="Motivo existente",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        oficio.servidores.add(self.servidor, self.outro_servidor)
        oficio.servidores_termo_autorizacao.add(self.servidor, self.outro_servidor)

        response = self.client.post(
            reverse("oficios:dados_viajantes", args=[oficio.pk]),
            data=self._payload(
                servidores=[str(self.outro_servidor.pk)],
                servidores_termo_autorizacao_present="1",
                servidores_termo_autorizacao=[str(self.outro_servidor.pk)],
                action="save_draft",
            ),
        )

        self.assertEqual(response.status_code, 302)
        oficio.refresh_from_db()
        self.assertEqual(list(oficio.servidores.all()), [self.outro_servidor])
        self.assertEqual(list(oficio.servidores_termo_autorizacao.all()), [self.outro_servidor])

    def test_get_editar_redireciona_para_dados_viajantes(self):
        oficio = Oficio.objects.create(numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)

        response = self.client.get(reverse("oficios:editar", args=[oficio.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("oficios:dados_viajantes", args=[oficio.pk]))

    def test_numero_automatico_reaproveita_numero_excluido(self):
        ano = timezone.localdate().year
        self.client.post(self._novo_rascunho_url(), data=self._payload(action="save_draft"))
        self.client.post(self._novo_rascunho_url(), data=self._payload(protocolo="12.345.678-8", action="save_draft"))
        primeiro = Oficio.objects.get(numero=1, ano=ano)
        primeiro.delete()

        self.client.post(self._novo_rascunho_url(), data=self._payload(protocolo="12.345.678-7", action="save_draft"))

        self.assertTrue(Oficio.objects.filter(numero=1, ano=ano, protocolo="123456787").exists())

    def test_pendencias_aparecem_apenas_apos_tentativa_documental(self):
        oficio = Oficio.objects.create(numero=1, ano=timezone.localdate().year, custeio=Oficio.CUSTEIO_UNIDADE_DPC)

        response = self.client.get(reverse("oficios:dados_viajantes", args=[oficio.pk]))

        self.assertContains(response, "Incompleta")
        self.assertNotContains(response, "Informe o motivo.")
        self.assertNotContains(response, "Selecione ao menos um viajante.")

        download_response = self.client.get(reverse("oficios:baixar_documento", args=[oficio.pk, "pdf"]))
        self.assertEqual(download_response.status_code, 302)
        self.assertIn("documento_incompleto=1", download_response.url)

        response = self.client.get(download_response.url)
        self.assertContains(response, "Informe o motivo.")
        self.assertContains(response, "Selecione ao menos um viajante.")

        oficio.motivo = "Motivo"
        oficio.save()
        oficio.servidores.add(self.servidor)
        response = self.client.get(reverse("oficios:dados_viajantes", args=[oficio.pk]))

        self.assertContains(response, "Concluída")
        self.assertNotContains(response, "Pendências para concluir esta etapa")

    def test_index_renderiza_card_com_numero_do_oficio(self):
        ano = timezone.localdate().year
        Oficio.objects.create(numero=1, ano=ano, motivo="Motivo card", protocolo="123456789", custeio=Oficio.CUSTEIO_UNIDADE_DPC)

        response = self.client.get(reverse("oficios:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "N° do Ofício")
        self.assertContains(response, f"01/{ano}")
        self.assertContains(response, "Motivo card")
        self.assertContains(response, "12.345.678-9")

    def test_templates_do_wizard_nao_usam_href_falso_css_ou_script_inline(self):
        template_paths = [
            Path("templates/oficios/wizard_base.html"),
            Path("templates/oficios/wizard_dados_viajantes.html"),
            Path("templates/oficios/wizard_transporte.html"),
            Path("templates/oficios/wizard_roteiro.html"),
            Path("templates/oficios/wizard_justificativa.html"),
            Path("templates/oficios/wizard_documentos.html"),
            Path("templates/oficios/partials/wizard_stepper.html"),
            Path("templates/oficios/partials/wizard_actions.html"),
        ]
        for template_path in template_paths:
            content = template_path.read_text(encoding="utf-8")
            self.assertNotIn('href="#"', content)
            self.assertNotIn('style="', content)
            self.assertIsNone(re.search(r"<script(?![^>]+src=)", content))

    def test_modelos_motivo_aparecem_no_select(self):
        response = self.client.get(self._novo_rascunho_url())
        self.assertContains(response, "PADRAO")
        self.assertContains(response, "INATIVO")

    def test_protocolo_invalido_retorna_erro_amigavel(self):
        payload = self._payload(protocolo="12345")
        response = self.client.post(self._novo_rascunho_url(), data=payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informe um protocolo válido com 9 dígitos.")

    def test_custeio_observacao_inicia_oculto_quando_nao_e_outra_instituicao(self):
        response = self.client.get(self._novo_rascunho_url())
        self.assertContains(response, "oficio-data-observacao")
        self.assertContains(response, "form-field--hidden")
        self.assertContains(response, "data-custeio-observacao-wrapper")

    def test_custeio_observacao_aparece_quando_outra_instituicao(self):
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            motivo="Motivo existente",
            custeio=Oficio.CUSTEIO_OUTRA_INSTITUICAO,
        )
        response = self.client.get(reverse("oficios:dados_viajantes", args=[oficio.pk]))
        self.assertContains(response, "oficio-data-observacao")
        self.assertContains(response, "data-custeio-observacao-wrapper")
        self.assertNotContains(
            response,
            'oficio-data-observacao form-field--hidden',
        )

    def test_post_custeio_outra_instituicao_sem_observacao_salva_rascunho(self):
        payload = self._payload(custeio=Oficio.CUSTEIO_OUTRA_INSTITUICAO, custeio_observacao="")
        response = self.client.post(self._novo_rascunho_url(), data=payload)
        self.assertEqual(response.status_code, 302)
        oficio = Oficio.objects.get()
        self.assertEqual(oficio.custeio, Oficio.CUSTEIO_OUTRA_INSTITUICAO)

        response = self.client.get(reverse("oficios:baixar_documento", args=[oficio.pk, "docx"]))
        self.assertEqual(response.status_code, 302)
        response = self.client.get(response.url)
        self.assertContains(response, "Informe a observação de custeio.")

    def test_post_custeio_outra_instituicao_com_observacao_valido(self):
        payload = self._payload(custeio=Oficio.CUSTEIO_OUTRA_INSTITUICAO, custeio_observacao="Convênio externo")
        response = self.client.post(self._novo_rascunho_url(), data=payload)
        self.assertEqual(response.status_code, 302)

    def test_post_custeio_normal_sem_observacao_valido(self):
        payload = self._payload(custeio=Oficio.CUSTEIO_UNIDADE_DPC, custeio_observacao="")
        response = self.client.post(self._novo_rascunho_url(), data=payload)
        self.assertEqual(response.status_code, 302)
