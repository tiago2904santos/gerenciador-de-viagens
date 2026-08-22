"""NOVO-03 — `_CAMPO_LABELS` ficou para trás quando as views de modelo saíram de
`views.py` para `model_views.py`.

O nome continuou definido no fim de `prestacoes_contas/views.py`, onde ninguém mais
lê, e `model_views.py` passou a referenciá-lo sem defini-lo. Resultado: `NameError`
em rota viva, nas duas entradas que consultam o rótulo do campo —
`modelo_novo` com `?campo=` na querystring, e `_voltar_modelos_url`, que é o
redirect de sucesso de criar, editar e excluir.

Nenhum teste cobria essas quatro views, e nenhum auditor do projeto lê código como
código: foi o `ruff` do `QA-07` que apontou (`F821`). Este teste é o que impede o
nome de sumir de novo.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from prestacoes_contas.models import ModeloTextoRelatorioTecnico
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea

CAMPO = ModeloTextoRelatorioTecnico.CAMPO_MOTIVO


class ModelosDeTextoRTTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área RT", sigla="AREA-RT")
        self.user = get_user_model().objects.create_user(username="rt_modelos", password="123456")
        VinculoUsuarioArea.objects.create(usuario=self.user, area=self.area, area_padrao=True)
        self.client.force_login(self.user)

    def _criar(self, nome="Modelo A"):
        return ModeloTextoRelatorioTecnico.objects.create(
            nome=nome, texto="Texto do modelo", campo=CAMPO, area=self.area
        )

    def test_index_abre(self):
        self._criar()
        self.assertEqual(self.client.get(reverse("prestacoes_contas:modelos_index")).status_code, 200)

    def test_index_exibe_retorno_para_relatorio_tecnico_de_origem(self):
        retorno = "/prestacoes-contas/servidor-prestacao/41/rt/"

        response = self.client.get(reverse("prestacoes_contas:modelos_index"), {"next": retorno})

        self.assertEqual(response.context["back_url"], retorno)
        self.assertEqual(response.context["back_label"], "Voltar para o relatório técnico")
        self.assertContains(response, f'href="{retorno}"')
        self.assertContains(response, "Voltar para o relatório técnico")

    def test_index_ignora_retorno_externo(self):
        response = self.client.get(
            reverse("prestacoes_contas:modelos_index"),
            {"next": "https://externo.invalido/rt/"},
        )

        self.assertEqual(response.context["back_url"], "")
        self.assertNotContains(response, "Voltar para o relatório técnico")

    def test_novo_com_campo_na_querystring_abre(self):
        """A leitura de `_CAMPO_LABELS` acontece antes de qualquer coisa nesta view."""
        response = self.client.get(reverse("prestacoes_contas:modelo_create"), {"campo": CAMPO})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial.get("campo"), CAMPO)

    def test_novo_com_campo_desconhecido_nao_pre_seleciona(self):
        response = self.client.get(reverse("prestacoes_contas:modelo_create"), {"campo": "inexistente"})

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["form"].initial.get("campo"))

    def test_criar_redireciona_para_a_aba_do_campo(self):
        """O redirect de sucesso passa por `_voltar_modelos_url` — o segundo `F821`."""
        response = self.client.post(
            reverse("prestacoes_contas:modelo_create"),
            {"nome": "Modelo novo", "texto": "Texto novo", "campo": CAMPO},
        )

        self.assertRedirects(response, f"{reverse('prestacoes_contas:modelos_index')}?campo={CAMPO}")
        self.assertTrue(ModeloTextoRelatorioTecnico.objects.filter(nome="Modelo novo").exists())

    def test_editar_redireciona_para_a_aba_do_campo(self):
        modelo = self._criar()

        response = self.client.post(
            reverse("prestacoes_contas:modelo_update", args=[modelo.pk]),
            {"nome": "Modelo A editado", "texto": "Texto editado", "campo": CAMPO},
        )

        self.assertRedirects(response, f"{reverse('prestacoes_contas:modelos_index')}?campo={CAMPO}")
        modelo.refresh_from_db()
        self.assertEqual(modelo.nome, "Modelo A editado")

    def test_excluir_redireciona_para_a_aba_do_campo(self):
        modelo = self._criar()

        response = self.client.post(reverse("prestacoes_contas:modelo_delete", args=[modelo.pk]))

        self.assertRedirects(response, f"{reverse('prestacoes_contas:modelos_index')}?campo={CAMPO}")
        self.assertFalse(ModeloTextoRelatorioTecnico.objects.filter(pk=modelo.pk).exists())

    def test_index_nao_mostra_modelo_de_outra_area(self):
        """O recorte por área já existia aqui; o teste o segura enquanto o arquivo muda."""
        outra = AreaTrabalho.objects.create(nome="Área B", sigla="AREA-B")
        alheio = ModeloTextoRelatorioTecnico.objects.create(
            nome="Alheio", texto="Texto de outra área", campo=CAMPO, area=outra
        )

        response = self.client.get(reverse("prestacoes_contas:modelos_index"))

        titulos = [linha["title"] for grupo in response.context["grupos"] for linha in grupo["rows"]]
        self.assertNotIn(alheio.nome, titulos)
