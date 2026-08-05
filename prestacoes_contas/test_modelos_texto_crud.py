"""As telas de modelo de texto do RT respondem (NOVO-38).

`model_views.py` usava `_CAMPO_LABELS` sem definir nem importar. Nenhum teste
tocava nestas rotas, entao o `NameError` atravessou a suite verde e so apareceu
quando a varredura de estilo computado da fase 5 tentou abrir a tela e levou
500. Este arquivo fecha o buraco: cada rota do CRUD tem de responder.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import ModeloTextoRelatorioTecnico


class ModelosTextoRelatorioTecnicoCrudTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="mt_test", password="x")
        self.client.force_login(self.user)
        self.campo = ModeloTextoRelatorioTecnico.CAMPO_CHOICES[0][0]
        self.modelo = ModeloTextoRelatorioTecnico.objects.create(
            nome="MODELO BASE", campo=self.campo, texto="Texto base"
        )

    def test_listagem_responde(self):
        r = self.client.get(reverse("prestacoes_contas:modelos_index"))
        self.assertEqual(r.status_code, 200)

    def test_novo_responde(self):
        r = self.client.get(reverse("prestacoes_contas:modelo_novo"))
        self.assertEqual(r.status_code, 200)

    def test_novo_com_campo_na_query_responde(self):
        """O ramo que consultava `_CAMPO_LABELS` — o que quebrava."""
        r = self.client.get(f"{reverse('prestacoes_contas:modelo_novo')}?campo={self.campo}")
        self.assertEqual(r.status_code, 200)

    def test_editar_responde(self):
        r = self.client.get(
            reverse("prestacoes_contas:modelo_editar", args=[self.modelo.pk]))
        self.assertEqual(r.status_code, 200)

    def test_excluir_responde(self):
        r = self.client.get(
            reverse("prestacoes_contas:modelo_excluir", args=[self.modelo.pk]))
        self.assertEqual(r.status_code, 200)

    def test_voltar_com_campo_valido_leva_o_filtro(self):
        """`_voltar_modelos_url` e o outro ponto de uso do nome que faltava."""
        from .model_views import _voltar_modelos_url

        self.assertIn(f"campo={self.campo}", _voltar_modelos_url(self.campo))
        self.assertNotIn("campo=", _voltar_modelos_url("nao-existe"))
