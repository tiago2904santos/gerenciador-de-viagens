"""NOVO-20260818-173204-55aec7fb0127: controles relacionais da Viatura no v2."""

from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Combustivel
from cadastros.models import Unidade
from cadastros.models import Viatura
from core.testing import vincular_area


TEMPLATES = Path(settings.BASE_DIR) / "templates"


class ViaturaComponentesV2SourceTests(TestCase):
    def test_campos_relacionais_usam_componentes_especializados_v2(self):
        identidade = (
            TEMPLATES / "cadastros/viaturas/partials/_identity_fields.html"
        ).read_text(encoding="utf-8")
        lotacao = (
            TEMPLATES / "cadastros/viaturas/partials/_assignment_fields.html"
        ).read_text(encoding="utf-8")
        motoristas = (
            TEMPLATES / "cadastros/viaturas/partials/_drivers_fields.html"
        ).read_text(encoding="utf-8")

        self.assertIn("<c-v2.select_with_action", identidade)
        self.assertIn("<c-v2.picker", lotacao)
        self.assertIn(':field="form.unidade"', lotacao)
        self.assertIn("<c-v2.picker", motoristas)
        self.assertIn(':field="form.motoristas"', motoristas)
        for source in (identidade, lotacao, motoristas):
            self.assertNotIn("field__control-row", source)

    def test_tipo_usa_select_v2_e_acao_do_picker_pertence_so_ao_controle(self):
        identidade = (
            TEMPLATES / "cadastros/viaturas/partials/_identity_fields.html"
        ).read_text(encoding="utf-8")
        picker = (TEMPLATES / "cotton/v2/picker.html").read_text(encoding="utf-8")
        engine = (Path(settings.BASE_DIR) / "static/js/components/picker.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('<c-v2.select :field="form.tipo"', identidade)
        self.assertNotIn('<c-v2.form_field :field="form.tipo"', identidade)
        self.assertIn('class="picker__action field-with-action__action"', picker)
        self.assertIn("search-picker__control-row", engine)


class ViaturaComponentesV2RenderTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(username="viatura-componentes-v2")
        self.area = vincular_area(self.usuario).area
        self.client.force_login(self.usuario)
        self.combustivel = Combustivel.objects.create(nome="FLEX", area=self.area)
        self.unidade = Unidade.objects.create(nome="Assessoria", sigla="ASCOM", area=self.area)
        self.viatura = Viatura.objects.create(
            placa="AAA1234",
            modelo="DUSTER",
            combustivel=self.combustivel,
            tipo=Viatura.TIPO_DESCARACTERIZADA,
            unidade=self.unidade,
            area=self.area,
        )

    def test_edicao_renderiza_select_e_pickers_v2_com_acoes_de_gerenciar(self):
        response = self.client.get(reverse("cadastros:viatura_update", args=[self.viatura.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-entity-picker-renderer="select"')
        self.assertContains(response, "data-picker-v2", count=2)
        self.assertContains(response, 'class="field-with-action"', count=1)
        self.assertContains(
            response,
            'class="picker__action field-with-action__action"',
            count=2,
        )
        self.assertContains(response, 'data-autosave-link="1"', count=3)
        self.assertNotContains(response, "data-picker-label")
        self.assertNotContains(response, 'class="button button--secondary button--sm field__manage"')

    def test_componentes_preservam_os_campos_e_valores_do_formulario(self):
        response = self.client.get(reverse("cadastros:viatura_update", args=[self.viatura.pk]))
        html = response.content.decode()

        for field_name in ("combustivel", "unidade", "motoristas"):
            self.assertIn(f'name="{field_name}"', html)
        self.assertIn(f'value="{self.combustivel.pk}" selected', html)
        self.assertIn(f'value="{self.unidade.pk}" selected', html)

    def test_tipo_nao_oferece_opcao_vazia(self):
        response = self.client.get(reverse("cadastros:viatura_update", args=[self.viatura.pk]))
        html = response.content.decode()
        choices = list(response.context["form"].fields["tipo"].choices)

        self.assertNotIn(("", "---------"), choices)
        self.assertEqual(choices, list(Viatura.TIPO_CHOICES))
        self.assertIn('<option value="CARACTERIZADA">Caracterizada</option>', html)
        self.assertIn(
            '<option value="DESCARACTERIZADA" selected>Descaracterizada</option>',
            html,
        )
