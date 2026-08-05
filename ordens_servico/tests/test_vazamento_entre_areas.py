"""BE-05 — o seletor de modelo de motivo da OS só pode oferecer modelos da área ativa.

`ModeloMotivoOficio` tem campo `area`, e `oficios/forms.py:289` já aplica o
recorte. `ordens_servico/forms.py` era a exceção: oferecia os modelos de todas as
áreas. O texto do modelo entra **literalmente** no documento gerado, com a
terminologia e os nomes de outra unidade.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from oficios.models import ModeloMotivoOficio
from ordens_servico.models import OrdemServico
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea


class ModeloDeMotivoNaoVazaEntreAreasTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="AREA-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="AREA-B")
        self.user = get_user_model().objects.create_user(username="os_motivo", password="123456")
        VinculoUsuarioArea.objects.create(usuario=self.user, area=self.area, area_padrao=True)
        self.client.force_login(self.user)

        self.ordem = OrdemServico.objects.create(numero=1, ano=2026, area=self.area)
        self.meu = ModeloMotivoOficio.objects.create(
            nome="Motivo da área A", texto="Texto da área A", ativo=True, area=self.area
        )
        self.alheio = ModeloMotivoOficio.objects.create(
            nome="Motivo da área B", texto="Texto da área B", ativo=True, area=self.outra
        )

    def _queryset_do_seletor(self):
        response = self.client.get(reverse("ordens_servico:editar", args=[self.ordem.pk]))
        self.assertEqual(response.status_code, 200)
        return response.context["form"].fields["modelo_motivo"].queryset

    def test_nao_oferece_modelo_de_outra_area(self):
        queryset = self._queryset_do_seletor()

        self.assertFalse(
            queryset.filter(pk=self.alheio.pk).exists(),
            msg="o seletor ofereceu o modelo de motivo de outra área",
        )

    def test_continua_oferecendo_o_modelo_da_propria_area(self):
        queryset = self._queryset_do_seletor()

        self.assertTrue(queryset.filter(pk=self.meu.pk).exists())

    def test_modelo_inativo_da_propria_area_continua_fora(self):
        """O recorte por área não pode atropelar o filtro de ativo que já existia."""
        inativo = ModeloMotivoOficio.objects.create(
            nome="Aposentado", texto="…", ativo=False, area=self.area
        )

        self.assertFalse(self._queryset_do_seletor().filter(pk=inativo.pk).exists())
