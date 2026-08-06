"""DB-05 — a placa de viatura era única no sistema inteiro, não por área.

`Viatura.placa` era `unique=True` global (`cadastros/models.py:379`). Duas
consequências, e a segunda é a que aparece para quem usa:

1. **bloqueio funcional** — a área B não conseguia cadastrar uma viatura cuja
   placa a área A já tivesse, mesmo sem enxergar nem poder usar a viatura dela;
2. **vazamento de existência** — `VuaturaForm.clean_placa`
   (`cadastros/forms.py:492`) consultava `Viatura.objects.filter(placa=raw)`
   **sem recorte de área** e devolvia *"Já existe uma viatura com esta placa"*.
   A mensagem confirma que a placa existe em algum lugar do sistema. É pouco,
   mas é informação de outra unidade entregue por um formulário.

A metade deste ID que era sobre `ModeloJustificativa.nome` já foi fechada pelo
`NOVO-09`; esta é a que sobrou.

O modelo espelha o que o `NOVO-09` fez: duas `UniqueConstraint` condicionais em
vez de um `unique_together`. São **duas e não uma** porque `area` é anulável e em
SQL `NULL != NULL` — um `unique(area, placa)` puro deixaria passar duas linhas
globais com a mesma placa.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.test import TestCase

from cadastros.forms import ViaturaForm
from cadastros.models import Viatura
from usuarios.models import AreaTrabalho


class PlacaUnicaPorAreaTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="VT-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="VT-B")

    # ── o banco ──

    def test_duas_areas_podem_ter_a_mesma_placa(self):
        """O defeito: `unique=True` global impedia isto."""
        Viatura.objects.create(placa="ABC1234", area=self.area)

        Viatura.objects.create(placa="ABC1234", area=self.outra)

        self.assertEqual(Viatura.objects.filter(placa="ABC1234").count(), 2)

    def test_a_mesma_area_continua_sem_poder_repetir_placa(self):
        """Afrouxar entre áreas não pode afrouxar dentro de uma."""
        Viatura.objects.create(placa="ABC1234", area=self.area)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Viatura.objects.create(placa="ABC1234", area=self.area)

    def test_duas_viaturas_globais_nao_podem_repetir_placa(self):
        """`area IS NULL` precisa da constraint própria.

        Em SQL `NULL != NULL`, então um `unique(area, placa)` puro deixaria
        passar duas linhas globais homônimas. É por isso que são duas
        constraints condicionais, e não uma.
        """
        Viatura.objects.create(placa="XYZ9876", area=None)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Viatura.objects.create(placa="XYZ9876", area=None)

    # ── o formulário ──

    def _form(self, placa, area):
        dados = {"placa": placa, "status": Viatura.STATUS_RASCUNHO, "modelo": "HILUX"}
        form = ViaturaForm(dados)
        form.instance.area = area
        return form

    def test_o_formulario_deixa_cadastrar_placa_que_existe_em_outra_area(self):
        """Era aqui que a pessoa batia: o banco liberou, mas o form ainda barrava.

        A constraint sozinha não resolve — `clean_placa` fazia a própria
        consulta, sem recorte, e reprovava antes de o banco ser consultado.
        """
        Viatura.objects.create(placa="ABC1234", area=self.outra)

        form = self._form("ABC1234", self.area)

        self.assertTrue(
            form.is_valid(),
            msg=f"o formulário recusou placa de outra área: {form.errors.as_json()}",
        )

    def test_o_formulario_continua_recusando_placa_repetida_na_propria_area(self):
        Viatura.objects.create(placa="ABC1234", area=self.area)

        form = self._form("ABC1234", self.area)

        self.assertFalse(form.is_valid())
        self.assertIn("placa", form.errors)

    def test_a_mensagem_de_erro_nao_confirma_placa_de_outra_area(self):
        """O vazamento era a própria mensagem.

        *"Já existe uma viatura com esta placa"* confirmava, para quem estivesse
        sondando, que aquela placa está cadastrada em algum lugar do sistema.
        """
        Viatura.objects.create(placa="ABC1234", area=self.outra)

        form = self._form("ABC1234", self.area)
        form.is_valid()

        self.assertNotIn("placa", form.errors)

    def test_editar_a_propria_viatura_nao_colide_consigo_mesma(self):
        viatura = Viatura.objects.create(placa="ABC1234", area=self.area)

        form = ViaturaForm(
            {"placa": "ABC1234", "status": viatura.status, "modelo": "HILUX"},
            instance=viatura,
        )

        self.assertTrue(form.is_valid(), msg=form.errors.as_json())

    def test_o_clean_do_modelo_tambem_recorta(self):
        """`full_clean` valida as constraints; ele não pode reprovar entre áreas."""
        Viatura.objects.create(placa="ABC1234", area=self.outra)

        nova = Viatura(placa="ABC1234", area=self.area)
        try:
            nova.full_clean(exclude=["motoristas"])
        except ValidationError as erro:
            self.fail(f"o `full_clean` recusou placa de outra área: {erro.message_dict}")
