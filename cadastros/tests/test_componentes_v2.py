"""NOVO-20260818-161641-9c71598641c6: conclusão dos cadastros no v2."""

from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Estado
from core.testing import vincular_area


ROOT = Path(settings.BASE_DIR)
TEMPLATES = ROOT / "templates"
CADASTROS = TEMPLATES / "cadastros"


class ComponentesCadastrosV2SourceTests(SimpleTestCase):
    def test_quick_add_de_unidades_distribui_nome_e_sigla_em_dois_para_um(self):
        source = (
            CADASTROS / "unidades/partials/_quick_add_fields.html"
        ).read_text(encoding="utf-8")

        self.assertIn('class="field-grid field-grid--cols-3"', source)
        self.assertIn('extra_class="field-grid__span-2"', source)

    def test_cadastros_nao_chamam_componentes_visuais_anteriores_ao_v2(self):
        namespaces_legados = (
            "<c-ui.",
            "<c-cards.",
            "<c-feedback.",
            "<c-form.",
            "<c-lists.",
        )
        offenders = {}
        for template in sorted(CADASTROS.rglob("*.html")):
            source = template.read_text(encoding="utf-8")
            encontrados = [tag for tag in namespaces_legados if tag in source]
            if encontrados:
                offenders[str(template.relative_to(TEMPLATES))] = encontrados

        self.assertEqual(offenders, {})

    def test_tres_confirmacoes_de_exclusao_compartilham_a_mesma_pagina(self):
        for relative in (
            "cadastros/estados/confirm_delete.html",
            "cadastros/servidores/confirm_delete.html",
            "cadastros/viaturas/confirm_delete.html",
        ):
            with self.subTest(template=relative):
                source = (TEMPLATES / relative).read_text(encoding="utf-8")
                self.assertIn("<c-v2.confirm_delete_page", source)
                self.assertNotIn("<form", source)

    def test_parciais_substituidas_pela_composicao_v2_foram_removidas(self):
        removidas = (
            "cadastros/servidores/partials/_form_card_body.html",
            "cadastros/servidores/partials/_form_card_footer.html",
            "cadastros/viaturas/partials/_form_card_body.html",
            "cadastros/viaturas/partials/_form_card_footer.html",
            "cadastros/unidades/partials/_quick_add_inline_fields.html",
        )
        existentes = [relative for relative in removidas if (TEMPLATES / relative).exists()]
        self.assertEqual(existentes, [])

    def test_card_de_modulo_tem_um_unico_componente_v2(self):
        self.assertFalse((TEMPLATES / "cotton/cards/module_card.html").exists())
        self.assertTrue((TEMPLATES / "cotton/v2/module_card.html").exists())
        for relative in ("cadastros/index.html", "core/dashboard.html"):
            source = (TEMPLATES / relative).read_text(encoding="utf-8")
            self.assertIn("<c-v2.module_card", source, relative)
            self.assertNotIn("<c-cards.module_card", source, relative)


class ComponentesCadastrosV2RenderTests(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_user(username="cadastros-v2")
        vincular_area(usuario)
        self.client.force_login(usuario)

    def test_cinco_catalogos_renderizam_campos_e_pagina_v2(self):
        for route in (
            "cadastros:cargos_index",
            "cadastros:cidades_index",
            "cadastros:combustiveis_index",
            "cadastros:estados_index",
            "cadastros:unidades_index",
        ):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="list-page"')
                self.assertContains(response, 'class="quick-add__panel"')
                self.assertContains(response, 'class="field')

    def test_confirmacao_de_estado_preserva_texto_e_formulario_post(self):
        estado = Estado.objects.create(nome="Paraná", sigla="PR", codigo_ibge=41)

        response = self.client.get(reverse("cadastros:estado_delete", args=[estado.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Excluir estado?")
        self.assertContains(response, "PARANÁ")
        self.assertContains(response, "Não é possível excluir se existirem cidades vinculadas.")
        self.assertContains(response, "confirm-delete-page__form")
        self.assertContains(response, 'method="post"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_hub_renderiza_header_e_cards_de_modulo_v2(self):
        response = self.client.get(reverse("cadastros:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="header"')
        self.assertContains(response, "module-card-v2", count=7)
