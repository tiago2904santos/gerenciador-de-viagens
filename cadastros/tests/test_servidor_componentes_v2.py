"""NOVO-20260818-180959-c19b650c0c5b: controles relacionais do Servidor no v2."""

from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import Servidor
from cadastros.models import Unidade
from core.testing import vincular_area


TEMPLATES = Path(settings.BASE_DIR) / "templates"


class ServidorComponentesV2SourceTests(TestCase):
    def test_campos_relacionais_usam_componentes_especializados_v2(self):
        identificacao = (
            TEMPLATES / "cadastros/servidores/partials/_form_fields.html"
        ).read_text(encoding="utf-8")
        lotacao = (
            TEMPLATES / "cadastros/servidores/partials/_lotacao_fields.html"
        ).read_text(encoding="utf-8")

        self.assertIn("<c-v2.select_with_action", identificacao)
        self.assertIn(':field="form.cargo"', identificacao)
        self.assertIn("<c-v2.picker", lotacao)
        self.assertIn(':field="form.unidade"', lotacao)
        for source in (identificacao, lotacao):
            self.assertNotIn("field__control-row", source)


class ServidorComponentesV2RenderTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(username="servidor-componentes-v2")
        self.area = vincular_area(self.usuario).area
        self.client.force_login(self.usuario)
        self.cargo = Cargo.objects.create(nome="AGENTE", area=self.area)
        self.unidade = Unidade.objects.create(nome="Assessoria", sigla="ASCOM", area=self.area)
        self.servidor = Servidor.objects.create(
            nome="ADEMAR SCHONS",
            cargo=self.cargo,
            unidade=self.unidade,
            area=self.area,
        )

    def test_edicao_renderiza_select_e_picker_v2_com_acoes_de_gerenciar(self):
        response = self.client.get(reverse("cadastros:servidor_update", args=[self.servidor.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-entity-picker-renderer="select"')
        self.assertContains(response, "data-picker-v2", count=1)
        self.assertContains(response, 'class="field-with-action"', count=1)
        self.assertContains(
            response,
            'class="picker__action field-with-action__action"',
            count=1,
        )
        self.assertContains(response, 'data-autosave-link="1"', count=2)
        self.assertNotContains(response, "data-picker-label")
        self.assertNotContains(response, 'class="button button--secondary button--sm field__manage"')

    def test_componentes_preservam_os_campos_e_valores_do_formulario(self):
        response = self.client.get(reverse("cadastros:servidor_update", args=[self.servidor.pk]))
        html = response.content.decode()

        for field_name in ("cargo", "unidade"):
            self.assertIn(f'name="{field_name}"', html)
        self.assertIn(f'value="{self.cargo.pk}" selected', html)
        self.assertIn(f'value="{self.unidade.pk}" selected', html)
