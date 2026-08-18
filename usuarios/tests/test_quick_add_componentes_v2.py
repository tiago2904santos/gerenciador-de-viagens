"""NOVO-20260818-183006-40ad9eb5163f: quick-adds administrativos no v2."""

import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.test import TestCase
from django.urls import reverse

from core.testing import vincular_area


TEMPLATES = Path(settings.BASE_DIR) / "templates"


class QuickAddComponentesV2SourceTests(SimpleTestCase):
    def test_parciais_nao_chamam_namespace_visual_anterior_ao_v2(self):
        relatives = (
            "usuarios/partials/_quick_add_usuario_fields.html",
            "usuarios/partials/_quick_add_area_fields.html",
            "usuarios/partials/_criar_usuario_identidade_fields.html",
            "usuarios/partials/_criar_usuario_senha_fields.html",
            "usuarios/partials/_criar_usuario_acesso_fields.html",
            "usuarios/partials/_criar_area_fields.html",
            "cadastros/unidades/partials/_quick_add_fields.html",
        )

        offenders = {}
        for relative in relatives:
            source = (TEMPLATES / relative).read_text(encoding="utf-8")
            if "<c-ui." in source:
                offenders[relative] = "<c-ui."

        self.assertEqual(offenders, {})

    def test_cada_secao_logica_tem_form_block_v2_proprio(self):
        usuario = (TEMPLATES / "usuarios/partials/_quick_add_usuario_fields.html").read_text(
            encoding="utf-8"
        )
        area = (TEMPLATES / "usuarios/partials/_quick_add_area_fields.html").read_text(
            encoding="utf-8"
        )
        unidade = (
            TEMPLATES / "cadastros/unidades/partials/_quick_add_fields.html"
        ).read_text(encoding="utf-8")
        form_block_css = (Path(settings.BASE_DIR) / "static/css/v2/form-block.css").read_text(
            encoding="utf-8"
        )

        self.assertEqual(usuario.count("<c-v2.form_block"), 3)
        self.assertEqual(area.count("<c-v2.form_block"), 1)
        self.assertEqual(unidade.count("<c-v2.form_block"), 1)
        self.assertEqual(usuario.count('surface="rail"'), 3)
        self.assertEqual(area.count('surface="rail"'), 1)
        self.assertEqual(unidade.count('surface="rail"'), 1)
        self.assertIn('class="field-grid field-grid--cols-2"', unidade)
        self.assertNotIn("form.servidores", unidade)
        self.assertIn(".form-block--v2 .field-grid--cols-2", form_block_css)

    def test_picker_v2_esconde_o_select_nativo_que_alimenta_o_componente(self):
        css = (Path(settings.BASE_DIR) / "static/css/v2/picker.css").read_text(encoding="utf-8")

        self.assertIn(".picker > .search-picker__native", css)
        self.assertIn("display: none !important", css)

    def test_controles_do_usuario_chamam_componentes_visuais_v2(self):
        identidade = (
            TEMPLATES / "usuarios/partials/_criar_usuario_identidade_fields.html"
        ).read_text(encoding="utf-8")
        senha = (TEMPLATES / "usuarios/partials/_criar_usuario_senha_fields.html").read_text(
            encoding="utf-8"
        )
        acesso = (TEMPLATES / "usuarios/partials/_criar_usuario_acesso_fields.html").read_text(
            encoding="utf-8"
        )
        select_css = (Path(settings.BASE_DIR) / "static/css/v2/select.css").read_text(
            encoding="utf-8"
        )

        self.assertEqual((identidade + senha).count("<c-v2.input"), 5)
        self.assertNotIn("<c-v2.form_field", identidade + senha)
        self.assertIn('<c-v2.picker :field="form.area"', acesso)
        self.assertIn('<c-v2.select :field="form.papel"', acesso)
        self.assertNotIn("<c-v2.select_with_action", acesso)
        self.assertIn(".select > .custom-select__native", select_css)


class QuickAddComponentesV2RenderTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="quick-add-v2-admin",
            password="SenhaForte123!",
            is_staff=True,
        )
        vincular_area(self.admin)
        self.client.force_login(self.admin)

    def _quick_add_html(self, route, panel_id):
        response = self.client.get(reverse(route))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        match = re.search(rf'<form[^>]+id="{panel_id}".*?</form>', html, re.DOTALL)
        self.assertIsNotNone(match)
        return match.group(0)

    def _assert_describedby_resolve(self, html):
        referenced = {
            token
            for value in re.findall(r'aria-describedby="([^"]+)"', html)
            for token in value.split()
        }
        rendered_ids = set(re.findall(r'\sid="([^"]+)"', html))
        self.assertEqual(referenced - rendered_ids, set())

    def test_usuario_renderiza_tres_blocos_v2_e_preserva_campos(self):
        html = self._quick_add_html("usuarios:index", "quick-add-usuario")

        self.assertEqual(html.count('class="form-block--v2'), 3)
        self.assertNotIn("document-form-block", html)
        self.assertNotIn("data-travel-document-wizard-step1", html)
        for field_name in (
            "usuario-username",
            "usuario-email",
            "usuario-nome_completo",
            "usuario-password1",
            "usuario-password2",
            "usuario-area",
            "usuario-papel",
        ):
            self.assertIn(f'name="{field_name}"', html)
        self.assertEqual(html.count('class="input__control"'), 5)
        self.assertNotIn('class="form-control"', html)
        self.assertNotIn('class="field-with-action"', html)
        self._assert_describedby_resolve(html)

    def test_area_renderiza_bloco_v2_e_preserva_campos(self):
        html = self._quick_add_html("usuarios:areas_index", "quick-add-area")

        self.assertEqual(html.count('class="form-block--v2'), 1)
        self.assertNotIn("document-form-block", html)
        for field_name in ("area-nome", "area-sigla"):
            self.assertIn(f'name="{field_name}"', html)
        self._assert_describedby_resolve(html)

    def test_unidade_renderiza_um_bloco_sem_servidores(self):
        html = self._quick_add_html("cadastros:unidades_index", "quick-add-unidade")

        self.assertEqual(html.count('class="form-block--v2'), 1)
        self.assertNotIn("data-picker-v2", html)
        for field_name in ("nome", "sigla"):
            self.assertIn(f'name="{field_name}"', html)
        self.assertNotIn('name="servidores"', html)
        self._assert_describedby_resolve(html)
