from pathlib import Path
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode

from cadastros.models import Cargo
from cadastros.models import Servidor
from cadastros.models import Unidade
from justificativas.models import ModeloJustificativa
from justificativas.models import Justificativa
from oficios.models import Oficio
from oficios.selectors import listar_modelos_motivo
from roteiros.models import Roteiro


class OficioViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester_oficios",
            password="123456",
        )
        self.client.force_login(self.user)
        self.cargo = Cargo.objects.create(nome="Analista Teste")
        self.unidade = Unidade.objects.create(nome="Unidade Teste", sigla="UT")
        self.servidor = Servidor.objects.create(nome="Servidor Teste", cargo=self.cargo, cpf="12345678901")

    def test_get_index_retorna_200(self):
        response = self.client.get(reverse("oficios:index") + "?aba=atuais")
        self.assertEqual(response.status_code, 200)

    def test_index_usa_modal_para_excluir_oficio(self):
        oficio = Oficio.objects.create(numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        # Ofício sem data de viagem cai na aba "Em andamento e realizados" (atuais).
        response = self.client.get(reverse("oficios:index") + "?aba=atuais")
        self.assertContains(response, "data-delete-confirm-modal")
        self.assertContains(response, "data-delete-modal-trigger")
        excluir_url = reverse("oficios:excluir", args=[oficio.pk])
        next_qs = urlencode({"next": reverse("oficios:index")})
        self.assertContains(response, f'data-delete-url="{excluir_url}?{next_qs}"')
        self.assertNotContains(response, f'href="{excluir_url}"')

    def test_get_novo_nao_cria_rascunho(self):
        response = self.client.get(reverse("oficios:novo"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Oficio.objects.exists())

    def test_post_novo_cria_rascunho_e_redireciona(self):
        response = self.client.post(reverse("oficios:novo"))
        self.assertEqual(response.status_code, 302)
        oficio = Oficio.objects.get()
        self.assertEqual(response.url, reverse("oficios:dados_viajantes", args=[oficio.pk]))
        self.assertEqual(oficio.status, Oficio.STATUS_RASCUNHO)
        self.assertEqual(oficio.numero, 1)
        self.assertEqual(oficio.ano, timezone.localdate().year)
        self.assertEqual(oficio.data_criacao, timezone.localdate())

        response = self.client.get(response.url)
        self.assertContains(response, "cv-form-section-card")
        self.assertContains(response, "field-grid")
        self.assertContains(response, f'name="numero" value="{oficio.numero}"')
        self.assertContains(response, f"/ {oficio.ano}")
        self.assertNotContains(response, "Data criaÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â§ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â£o:")
        self.assertNotContains(response, "Gerado automaticamente ao salvar.")
        self.assertNotContains(response, "serÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¡ definida automaticamente ao salvar")
        self.assertNotContains(response, "PendÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Âªncias para concluir esta etapa")
        self.assertContains(response, "page-header-status-chip")
        self.assertContains(response, "page-stepper")
        self.assertContains(response, "page-shell--wizard")
        self.assertContains(response, "cv-field-with-action--manage-reveal")
        self.assertContains(response, "Modelo de motivo")
        self.assertContains(response, reverse("oficios:modelos_motivo_index"))
        self.assertContains(response, "cv-card-footer-section")
        self.assertContains(response, "Avan\u00e7ar")
        self.assertNotContains(
            response,
            "Escolha um modelo para iniciar com texto prÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â©-preenchido ou escreva manualmente o motivo.",
        )

    def test_post_dados_viajantes_valido_atualiza_rascunho(self):
        oficio = Oficio.objects.create(
            numero=1,
            ano=timezone.localdate().year,
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        response = self.client.post(
            reverse("oficios:dados_viajantes", args=[oficio.pk]),
            data={
                "protocolo": "12.345.678-1",
                "motivo": "Motivo",
                "servidores": [str(self.servidor.pk)],
                "custeio": Oficio.CUSTEIO_UNIDADE_DPC,
                "custeio_observacao": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Oficio.objects.count(), 1)
        oficio.refresh_from_db()
        self.assertEqual(oficio.numero, 1)
        self.assertEqual(oficio.ano, timezone.localdate().year)

    def test_lista_continua_exibindo_status_rascunho(self):
        Oficio.objects.create(numero=1, ano=timezone.localdate().year, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        response = self.client.get(reverse("oficios:index") + "?aba=atuais")
        self.assertContains(response, "Rascunho")

    def test_lista_visualizar_documento_aponta_para_etapa_documentos(self):
        oficio = Oficio.objects.create(numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        oficio.servidores.add(self.servidor)
        response = self.client.get(reverse("oficios:index") + "?aba=atuais")
        self.assertContains(response, "Visualizar ofício")
        self.assertContains(response, reverse("oficios:wizard_documentos", args=[oficio.pk]))
        self.assertNotContains(
            response,
            reverse("termos:termo_servidor_pdf_inline", args=[oficio.pk, self.servidor.pk]),
        )

    @mock.patch("documentos.services.warm_cache.ensure_document_artifact_cached")
    @mock.patch(
        "oficios.document_generation.get_document_generation_status",
        return_value={
            "docx_available": True,
            "pdf_available": True,
            "pdf_cached": False,
            "pdf_engine": "test",
            "pdf_message": "",
            "pdf_link_label": "PDF",
            "documentos_persist_artefatos": False,
            "oficio_pdf_botoes_assinatura": False,
        },
    )
    @mock.patch("oficios.services.validar_oficio_para_documento", return_value={"status": "complete", "pendencias": []})
    @mock.patch("oficios.views.validar_oficio_para_documento", return_value={"status": "complete", "pendencias": []})
    def test_wizard_documentos_exibe_baixar_docx_no_documento_original(
        self,
        _m_view_val,
        _m_service_val,
        _m_generation,
        _m_cache,
    ):
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            motivo="Motivo",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        response = self.client.get(reverse("oficios:wizard_documentos", args=[oficio.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visualizar documento")
        self.assertContains(response, "Baixar PDF")
        self.assertContains(response, "Baixar DOCX")
        self.assertContains(response, reverse("oficios:baixar_documento", args=[oficio.pk, "docx"]))

    @mock.patch("documentos.services.warm_cache.ensure_document_artifact_cached")
    @mock.patch(
        "oficios.document_generation.get_document_generation_status",
        return_value={
            "docx_available": True,
            "pdf_available": True,
            "pdf_cached": False,
            "pdf_engine": "test",
            "pdf_message": "",
            "pdf_link_label": "PDF",
            "documentos_persist_artefatos": False,
            "oficio_pdf_botoes_assinatura": False,
        },
    )
    @mock.patch("oficios.services.validar_oficio_para_documento", return_value={"status": "complete", "pendencias": []})
    @mock.patch("oficios.views.validar_oficio_para_documento", return_value={"status": "complete", "pendencias": []})
    def test_wizard_documentos_exibe_baixar_docx_na_justificativa(
        self,
        _m_view_val,
        _m_service_val,
        _m_generation,
        _m_cache,
    ):
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            motivo="Motivo",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        response = self.client.get(reverse("oficios:wizard_documentos", args=[oficio.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Justificativa")
        self.assertContains(response, "Visualizar documento")
        self.assertContains(response, "Baixar PDF")
        self.assertContains(response, "Baixar DOCX")
        self.assertContains(response, reverse("oficios:baixar_justificativa_documento", args=[oficio.pk, "docx"]))

    @mock.patch("documentos.services.warm_cache.ensure_document_artifact_cached")
    def test_wizard_documentos_exibe_secao_conferencia(self, _m_cache):
        oficio = Oficio.objects.create(numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        response = self.client.get(reverse("oficios:wizard_documentos", args=[oficio.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Documentos para conferência")
        self.assertNotContains(response, "Visualizar documento")
        self.assertNotContains(response, "PDF pronto.")
        self.assertContains(response, reverse("oficios:index"))
        self.assertContains(response, "Voltar à lista")
        self.assertContains(response, 'data-autosave-link="1"')

    @mock.patch("documentos.services.warm_cache.ensure_document_artifact_cached")
    def test_wizard_documentos_omite_secao_de_justificativa(self, _m_cache):
        oficio = Oficio.objects.create(numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        roteiro = Roteiro.objects.create(saida_dt=timezone.now() + timedelta(days=7))
        oficio.roteiro = roteiro
        oficio.save(update_fields=["roteiro"])
        modelo = ModeloJustificativa.objects.create(
            nome="Urgencia operacional",
            texto="Modelo de justificativa para teste.",
        )
        Justificativa.objects.create(
            oficio=oficio,
            modelo=modelo,
            texto="Justificativa registrada para teste.",
        )
        response = self.client.get(reverse("oficios:wizard_documentos", args=[oficio.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "oficio-documentos-justification-section")
        self.assertNotContains(response, "Justificativa registrada para teste.")
        self.assertNotContains(response, "Urgencia operacional")

    @mock.patch("documentos.services.warm_cache.ensure_document_artifact_cached")
    @mock.patch("oficios.services.validar_oficio_para_documento", return_value={"status": "complete", "pendencias": []})
    @mock.patch("oficios.views.validar_oficio_para_documento", return_value={"status": "complete", "pendencias": []})
    def test_wizard_documentos_footer_mostra_voltar_e_finalizar_quando_sem_pendencias(
        self,
        _m_view_val,
        _m_service_val,
        _m_cache,
    ):
        oficio = Oficio.objects.create(numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        response = self.client.get(reverse("oficios:wizard_documentos", args=[oficio.pk]))
        html = response.content.decode("utf-8")
        preview_start = html.index('oficio-documentos-preview-section document-inline-stack')
        self.assertIn("oficio-documentos-summary-section", html[preview_start:])
        self.assertIn("oficio-documentos-viajantes-section", html[preview_start:])
        self.assertIn("oficio-documentos-viatura-section", html[preview_start:])
        footer_start = html.index('<section class="cv-card-footer-section">', preview_start)
        footer_end = html.index('</section>', footer_start) + len('</section>')
        footer = html[footer_start:footer_end]

        self.assertIn("Voltar", footer)
        self.assertIn("Finalizar Ofício", footer)
        self.assertNotIn("Salvar rascunho", footer)
        self.assertNotIn("DOCX", footer)
        self.assertNotIn("PDF", footer)
        self.assertNotIn("Central de assinaturas", footer)
        self.assertNotIn("Justificativa PDF", footer)
        self.assertNotIn("Plano DOCX", footer)
        self.assertNotIn("Ordem", footer)

    @mock.patch("documentos.services.warm_cache.ensure_document_artifact_cached")
    @mock.patch("oficios.services.validar_oficio_para_documento", return_value={"status": "incomplete", "pendencias": ["Pendencia de teste"]})
    @mock.patch("oficios.views.validar_oficio_para_documento", return_value={"status": "incomplete", "pendencias": ["Pendencia de teste"]})
    def test_wizard_documentos_footer_mostra_voltar_e_salvar_rascunho_quando_ha_pendencias(
        self,
        _m_view_val,
        _m_service_val,
        _m_cache,
    ):
        oficio = Oficio.objects.create(numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        response = self.client.get(reverse("oficios:wizard_documentos", args=[oficio.pk]))
        html = response.content.decode("utf-8")
        preview_start = html.index('oficio-documentos-preview-section document-inline-stack')
        self.assertIn("oficio-documentos-summary-section", html[preview_start:])
        footer_start = html.index('<section class="cv-card-footer-section">', preview_start)
        footer_end = html.index('</section>', footer_start) + len('</section>')
        footer = html[footer_start:footer_end]

        self.assertIn("Voltar", footer)
        self.assertIn("Salvar rascunho", footer)
        self.assertNotIn("Finalizar Ofício", footer)
        self.assertNotIn("DOCX", footer)
        self.assertNotIn("PDF", footer)
        self.assertNotIn("Central de assinaturas", footer)
        self.assertNotIn("Justificativa PDF", footer)
        self.assertNotIn("Plano DOCX", footer)
        self.assertNotIn("Ordem", footer)

    def test_post_wizard_documentos_save_draft_list_salva_e_redireciona_para_lista(self):
        oficio = Oficio.objects.create(numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        updated_before = oficio.updated_at
        response = self.client.post(
            reverse("oficios:wizard_documentos", args=[oficio.pk]),
            data={"action": "save_draft_list"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("oficios:index"))
        oficio.refresh_from_db()
        self.assertEqual(oficio.status, Oficio.STATUS_RASCUNHO)
        self.assertGreater(oficio.updated_at, updated_before)

    @mock.patch("documentos.services.warm_cache.ensure_document_artifact_cached")
    @mock.patch("oficios.services.validar_oficio_para_documento", return_value={"status": "complete", "pendencias": []})
    @mock.patch("oficios.views.validar_oficio_para_documento", return_value={"status": "complete", "pendencias": []})
    @mock.patch(
        "oficios.document_generation.get_document_generation_status",
        return_value={
            "docx_available": True,
            "pdf_available": True,
            "pdf_cached": False,
            "pdf_engine": "test",
            "pdf_message": "",
            "pdf_link_label": "PDF",
            "documentos_persist_artefatos": False,
            "oficio_pdf_botoes_assinatura": False,
        },
    )
    def test_wizard_documentos_termos_apontam_para_pdf_inline(
        self,
        _m_generation,
        _m_view_val,
        _m_service_val,
        _m_cache,
    ):
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            motivo="Motivo",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        oficio.servidores.add(self.servidor)
        oficio.servidores_termo_autorizacao.add(self.servidor)
        response = self.client.get(reverse("oficios:wizard_documentos", args=[oficio.pk]))
        inline_url = reverse("termos:termo_servidor_pdf_inline", args=[oficio.pk, self.servidor.pk])
        self.assertContains(response, inline_url)
        self.assertContains(response, f'data-src="{inline_url}"')
        self.assertContains(response, f'data-termo-inline-url="{inline_url}"')
        self.assertNotContains(response, "data-open-all-termos")
        self.assertNotContains(response, "data-download-all-termos")
        self.assertContains(response, "Visualizar termo")
        self.assertContains(response, "Baixar PDF")
        self.assertContains(response, "Baixar DOCX")
        self.assertContains(
            response,
            reverse("termos:baixar_termo_servidor", args=[oficio.pk, self.servidor.pk, "pdf"]),
        )
        self.assertContains(
            response,
            reverse("termos:baixar_termo_servidor", args=[oficio.pk, self.servidor.pk, "docx"]),
        )

    @mock.patch("documentos.services.warm_cache.ensure_document_artifact_cached")
    @mock.patch("oficios.services.validar_oficio_para_documento", return_value={"status": "complete", "pendencias": []})
    @mock.patch("oficios.views.validar_oficio_para_documento", return_value={"status": "complete", "pendencias": []})
    @mock.patch(
        "oficios.document_generation.get_document_generation_status",
        return_value={
            "docx_available": True,
            "pdf_available": True,
            "pdf_cached": False,
            "pdf_engine": "test",
            "pdf_message": "",
            "pdf_link_label": "PDF",
            "documentos_persist_artefatos": False,
            "oficio_pdf_botoes_assinatura": False,
        },
    )
    def test_wizard_documentos_multiplos_termos_exibe_acoes_em_lote(
        self,
        _m_generation,
        _m_view_val,
        _m_service_val,
        _m_cache,
    ):
        servidor_2 = Servidor.objects.create(nome="Servidor Teste 2", cargo=self.cargo, cpf="12345678902")
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            motivo="Motivo",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        oficio.servidores.add(self.servidor, servidor_2)
        oficio.servidores_termo_autorizacao.add(self.servidor, servidor_2)
        response = self.client.get(reverse("oficios:wizard_documentos", args=[oficio.pk]))
        self.assertContains(response, "data-open-all-termos")
        self.assertContains(response, "data-download-all-termos")
        self.assertContains(response, "data-termo-inline-url=", count=2)
        self.assertContains(response, "data-termo-download-pdf-url=", count=2)
        self.assertContains(response, "Visualizar termo")
        self.assertContains(response, "Baixar PDF")
        self.assertContains(response, "Baixar DOCX")
        self.assertContains(response, reverse("termos:baixar_termo_lote_zip", args=[oficio.pk, "docx"]))

    @mock.patch("documentos.services.warm_cache.ensure_document_artifact_cached")
    def test_wizard_documentos_omite_motorista_do_transporte_quando_esta_no_oficio(self, _m_cache):
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            motivo="Motivo",
            motorista=self.servidor,
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        oficio.servidores.add(self.servidor)
        response = self.client.get(reverse("oficios:wizard_documentos", args=[oficio.pk]))
        self.assertContains(response, "oficio-documentos-traveller-tile--motorista")
        self.assertNotContains(response, "Motorista carona")
        self.assertNotContains(response, "oficio-documentos-fact--driver-external")
        self.assertNotContains(response, "oficio-documentos-vehicle-executive__driver--external")

    @mock.patch("documentos.services.warm_cache.ensure_document_artifact_cached")
    def test_wizard_documentos_exibe_motorista_carona_no_transporte_quando_externo(self, _m_cache):
        motorista = Servidor.objects.create(nome="Motorista Carona", cargo=self.cargo, cpf="12345678903")
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            motivo="Motivo",
            motorista=motorista,
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        oficio.servidores.add(self.servidor)
        response = self.client.get(reverse("oficios:wizard_documentos", args=[oficio.pk]))
        self.assertContains(response, "oficio-documentos-fact--driver-external")
        self.assertContains(response, "Motorista carona")
        self.assertContains(response, "MOTORISTA CARONA")
        self.assertNotContains(response, "oficio-documentos-vehicle-executive__driver--external")

    @mock.patch("documentos.services.warm_cache.ensure_document_artifact_cached")
    @mock.patch("oficios.services.validar_oficio_para_documento", return_value={"status": "complete", "pendencias": []})
    @mock.patch("oficios.views.validar_oficio_para_documento", return_value={"status": "complete", "pendencias": []})
    @mock.patch(
        "oficios.document_generation.get_document_generation_status",
        return_value={
            "docx_available": True,
            "pdf_available": True,
            "pdf_cached": False,
            "pdf_engine": "test",
            "pdf_message": "",
            "pdf_link_label": "PDF",
            "documentos_persist_artefatos": False,
            "oficio_pdf_botoes_assinatura": False,
        },
    )
    def test_wizard_documentos_termos_mostra_estado_vazio_sem_servidores_selecionados(
        self,
        _m_generation,
        _m_view_val,
        _m_service_val,
        _m_cache,
    ):
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            motivo="Motivo",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        oficio.servidores.add(self.servidor)
        response = self.client.get(reverse("oficios:wizard_documentos", args=[oficio.pk]))
        inline_url = reverse("termos:termo_servidor_pdf_inline", args=[oficio.pk, self.servidor.pk])
        self.assertContains(response, "Nenhum servidor selecionado para Termo de Autorização.")
        self.assertNotContains(response, inline_url)

    def test_get_detalhe_redireciona_para_dados_viajantes(self):
        oficio = Oficio.objects.create(numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        response = self.client.get(reverse("oficios:detalhe", args=[oficio.pk]), follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("oficios:dados_viajantes", args=[oficio.pk]))

    def test_get_editar_redireciona_para_dados_viajantes(self):
        oficio = Oficio.objects.create(numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        response = self.client.get(reverse("oficios:editar", args=[oficio.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("oficios:dados_viajantes", args=[oficio.pk]))

    def test_post_editar_redireciona_sem_alterar(self):
        oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            motivo="Motivo antigo",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        response = self.client.post(
            reverse("oficios:editar", args=[oficio.pk]),
            data={
                "protocolo": "12.345.678-2",
                "motivo": "Motivo novo",
                "servidores": [str(self.servidor.pk)],
                "custeio": Oficio.CUSTEIO_UNIDADE_DPC,
                "custeio_observacao": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("oficios:dados_viajantes", args=[oficio.pk]))
        oficio.refresh_from_db()
        self.assertEqual(oficio.numero, 1)
        self.assertEqual(oficio.motivo, "Motivo antigo")

    def test_post_excluir_remove(self):
        oficio = Oficio.objects.create(numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        response = self.client.post(reverse("oficios:excluir", args=[oficio.pk]))
        self.assertEqual(response.status_code, 302)
        detail_response = self.client.get(reverse("oficios:detalhe", args=[oficio.pk]))
        self.assertEqual(detail_response.status_code, 404)

    def test_post_excluir_de_oficio_de_evento_sem_next_volta_para_evento(self):
        from eventos.models import Evento

        evento = Evento.objects.create(motivo="Evento de teste")
        oficio = Oficio.objects.create(
            numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC, evento=evento,
        )
        response = self.client.post(reverse("oficios:excluir", args=[oficio.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url, reverse("eventos:guiado_etapa", kwargs={"pk": evento.pk, "etapa": 3}),
        )

    def test_post_excluir_de_oficio_de_evento_com_next_da_lista_volta_para_lista(self):
        from eventos.models import Evento

        evento = Evento.objects.create(motivo="Evento de teste")
        oficio = Oficio.objects.create(
            numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC, evento=evento,
        )
        excluir_url = reverse("oficios:excluir", args=[oficio.pk])
        next_qs = urlencode({"next": reverse("oficios:index")})
        response = self.client.post(f"{excluir_url}?{next_qs}")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("oficios:index"))

    def test_get_excluir_redireciona_para_lista(self):
        oficio = Oficio.objects.create(numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        response = self.client.get(reverse("oficios:excluir", args=[oficio.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("oficios:index"))

    def test_crud_modelo_motivo_views(self):
        list_response = self.client.get(reverse("oficios:modelos_motivo_index"))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Nenhum modelo de motivo cadastrado.")
        self.assertContains(list_response, "Novo modelo")
        self.assertContains(list_response, "Buscar modelos de motivo")
        self.assertContains(list_response, 'id="quick-add-modelo-motivo"')
        self.assertContains(list_response, 'name="nome"')
        self.assertContains(list_response, 'name="texto"')
        self.assertContains(list_response, "cv-field__control--textarea")

        new_get = self.client.get(reverse("oficios:modelo_motivo_novo"))
        self.assertEqual(new_get.status_code, 200)
        self.assertContains(new_get, "Novo modelo")
        self.assertContains(new_get, 'name="texto"')

        new_post = self.client.post(
            reverse("oficios:modelos_motivo_index"),
            data={
                "nome": "Padrao equipe",
                "texto": "Texto base",
                "is_padrao": "on",
            },
        )
        self.assertEqual(new_post.status_code, 302)
        modelo = listar_modelos_motivo().first()

        edit_get = self.client.get(reverse("oficios:modelo_motivo_editar", args=[modelo.pk]))
        self.assertRedirects(edit_get, reverse("oficios:modelos_motivo_index"))

        edit_post = self.client.post(
            reverse("oficios:modelo_motivo_editar", args=[modelo.pk]),
            data={
                "nome": "Padrao equipe atualizado",
                "texto": "Texto atualizado",
                "is_padrao": "",
            },
        )
        self.assertEqual(edit_post.status_code, 302)
        modelo.refresh_from_db()
        self.assertEqual(modelo.nome, "PADRAO EQUIPE ATUALIZADO")

        delete_post = self.client.post(reverse("oficios:modelo_motivo_excluir", args=[modelo.pk]))
        self.assertEqual(delete_post.status_code, 302)
        self.assertFalse(listar_modelos_motivo().filter(pk=modelo.pk).exists())

    def test_listagem_modelos_exibe_apenas_badge_padrao(self):
        self.client.post(
            reverse("oficios:modelo_motivo_novo"),
            data={
                "nome": "Modelo Ativo PadrÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â£o",
                "texto": "Texto ativo padrÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â£o",
                "is_padrao": "on",
            },
        )
        self.client.post(
            reverse("oficios:modelo_motivo_novo"),
            data={
                "nome": "Modelo Secundario",
                "texto": "Texto secundario",
                "is_padrao": "",
            },
        )

        response = self.client.get(reverse("oficios:modelos_motivo_index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Padrão")

    def test_templates_modelos_motivo_sem_href_falso_css_ou_js_inline(self):
        template_paths = [
            Path("templates/oficios/modelos_motivo/index.html"),
            Path("templates/oficios/modelos_motivo/confirm_delete.html"),
            Path("templates/oficios/modelos_motivo/partials/_quick_add_fields.html"),
        ]
        for template_path in template_paths:
            content = template_path.read_text(encoding="utf-8")
            self.assertNotIn('href="#"', content)
            self.assertNotIn('style="', content)
            self.assertNotIn("<script", content)

    def test_listagem_modelos_ordenada_alfabeticamente(self):
        self.client.post(
            reverse("oficios:modelo_motivo_novo"),
            data={"nome": "Zeta", "texto": "texto zeta", "is_padrao": ""},
        )
        self.client.post(
            reverse("oficios:modelo_motivo_novo"),
            data={"nome": "Alfa", "texto": "texto alfa", "is_padrao": ""},
        )

        response = self.client.get(reverse("oficios:modelos_motivo_index"))
        content = response.content.decode("utf-8")
        self.assertLess(content.find("ALFA"), content.find("ZETA"))
