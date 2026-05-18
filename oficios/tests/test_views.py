from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Cargo
from cadastros.models import Servidor
from cadastros.models import Unidade
from oficios.models import Oficio
from oficios.selectors import listar_modelos_motivo


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
        response = self.client.get(reverse("oficios:index"))
        self.assertEqual(response.status_code, 200)

    def test_get_novo_cria_rascunho_e_redireciona(self):
        response = self.client.get(reverse("oficios:novo"))
        self.assertEqual(response.status_code, 302)
        oficio = Oficio.objects.get()
        self.assertEqual(response.url, reverse("oficios:dados_viajantes", args=[oficio.pk]))
        self.assertEqual(oficio.status, Oficio.STATUS_RASCUNHO)
        self.assertEqual(oficio.numero, 1)
        self.assertEqual(oficio.ano, timezone.localdate().year)
        self.assertEqual(oficio.data_criacao, timezone.localdate())

        response = self.client.get(response.url)
        self.assertContains(response, "oficio-data-grid--three")
        self.assertContains(response, "oficio-data-grid--full")
        self.assertContains(response, oficio.numero_formatado)
        self.assertContains(response, oficio.data_criacao.strftime("%d/%m/%Y"))
        self.assertNotContains(response, "Gerado automaticamente ao salvar.")
        self.assertNotContains(response, "será definida automaticamente ao salvar")
        self.assertNotContains(response, "Pendências para concluir esta etapa")
        self.assertNotContains(response, "status-chip")
        self.assertNotContains(response, "Rascunho")
        self.assertContains(response, "motivo-card__header")
        self.assertContains(response, "Modelo de motivo")
        self.assertContains(response, reverse("oficios:modelos_motivo_index"))
        self.assertNotContains(
            response,
            "Escolha um modelo para iniciar com texto pré-preenchido ou escreva manualmente o motivo.",
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
        response = self.client.get(reverse("oficios:index"))
        self.assertContains(response, "Rascunho")

    def test_lista_visualizar_documento_aponta_para_etapa_documentos(self):
        oficio = Oficio.objects.create(numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        oficio.servidores.add(self.servidor)
        response = self.client.get(reverse("oficios:index"))
        self.assertContains(response, "Visualizar documento")
        self.assertContains(response, reverse("oficios:wizard_documentos", args=[oficio.pk]))
        self.assertNotContains(
            response,
            reverse("termos:termo_servidor_pdf_inline", args=[oficio.pk, self.servidor.pk]),
        )

    @mock.patch("documentos.services.warm_cache.ensure_document_artifact_cached")
    def test_wizard_documentos_exibe_secao_conferencia(self, _m_cache):
        oficio = Oficio.objects.create(numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)
        response = self.client.get(reverse("oficios:wizard_documentos", args=[oficio.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Documentos para conferência")
        self.assertNotContains(response, "Visualizar documento")

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

    def test_crud_modelo_motivo_views(self):
        list_response = self.client.get(reverse("oficios:modelos_motivo_index"))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Nenhum modelo de motivo cadastrado.")
        self.assertContains(list_response, "Novo modelo")
        self.assertContains(list_response, "Buscar modelos de motivo")

        new_get = self.client.get(reverse("oficios:modelo_motivo_novo"))
        self.assertEqual(new_get.status_code, 200)
        self.assertContains(new_get, "Novo modelo de motivo")
        self.assertContains(new_get, "Texto do modelo")
        self.assertNotContains(new_get, "Modelo padrão")
        self.assertNotContains(new_get, "Is padrão")

        new_post = self.client.post(
            reverse("oficios:modelo_motivo_novo"),
            data={
                "nome": "Padrao equipe",
                "texto": "Texto base",
                "is_padrao": "on",
            },
        )
        self.assertEqual(new_post.status_code, 302)
        modelo = listar_modelos_motivo().first()

        edit_get = self.client.get(reverse("oficios:modelo_motivo_editar", args=[modelo.pk]))
        self.assertEqual(edit_get.status_code, 200)

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
                "nome": "Modelo Ativo Padrão",
                "texto": "Texto ativo padrão",
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
            Path("templates/oficios/modelos_motivo/form.html"),
            Path("templates/oficios/modelos_motivo/confirm_delete.html"),
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
