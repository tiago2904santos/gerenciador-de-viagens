"""NOVO-09 — `ModeloJustificativa` é por área, e o "padrão" de uma não derruba o das outras.

Achado ao corrigir o `NOVO-06`. `ModeloJustificativa` não tinha campo `area`,
enquanto o seu gêmeo `oficios.ModeloMotivoOficio` tinha desde o `BE-05`. Três
consequências, e a primeira não é de leitura:

1. **`save()` atropelava as outras áreas.** `models.py:27` fazia
   `objects.exclude(pk=self.pk).update(is_padrao=False)` **sem filtro**: marcar um
   modelo como padrão na área A desmarcava o padrão de todas as demais.
2. **O texto de outra unidade entrava no documento.** Mesmo argumento do `BE-05`:
   o `texto` do modelo é copiado para a justificativa e vai literal para o
   documento gerado, com a terminologia e os nomes de outra área.
3. **`nome` era `unique` global**, então uma área não conseguia criar modelo com
   um título que outra já tivesse usado.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.tenancy import AREA_SESSION_KEY
from justificativas.models import ModeloJustificativa
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea


class ModeloJustificativaPorAreaTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="MJ-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="MJ-B")
        self.user = get_user_model().objects.create_user(username="modelos_area")
        VinculoUsuarioArea.objects.create(usuario=self.user, area=self.area, area_padrao=True)
        VinculoUsuarioArea.objects.create(usuario=self.user, area=self.outra)
        self.client.force_login(self.user)

        self.meu = ModeloJustificativa.objects.create(
            nome="MODELO DA A", texto="Texto da área A", area=self.area
        )
        self.alheio = ModeloJustificativa.objects.create(
            nome="MODELO DA B", texto="Texto da área B", area=self.outra
        )

    def _trocar_para(self, area):
        sessao = self.client.session
        sessao[AREA_SESSION_KEY] = area.pk
        sessao.save()

    # ── o efeito colateral entre áreas, que é o pior dos três ──

    def test_definir_padrao_numa_area_nao_derruba_o_das_outras(self):
        padrao_da_outra = ModeloJustificativa.objects.create(
            nome="PADRÃO DA B", texto="Texto", area=self.outra, is_padrao=True
        )

        ModeloJustificativa.objects.create(
            nome="PADRÃO DA A", texto="Texto", area=self.area, is_padrao=True
        )

        padrao_da_outra.refresh_from_db()
        self.assertTrue(
            padrao_da_outra.is_padrao,
            msg="marcar um padrão numa área desmarcou o padrão de outra",
        )

    def test_dentro_da_mesma_area_o_padrao_continua_exclusivo(self):
        """O recorte não pode desligar a regra que já existia."""
        antigo = ModeloJustificativa.objects.create(
            nome="PADRÃO ANTIGO", texto="Texto", area=self.area, is_padrao=True
        )

        ModeloJustificativa.objects.create(
            nome="PADRÃO NOVO", texto="Texto", area=self.area, is_padrao=True
        )

        antigo.refresh_from_db()
        self.assertFalse(antigo.is_padrao)

    # ── nomes deixam de colidir entre áreas ──

    def test_duas_areas_podem_ter_modelo_com_o_mesmo_nome(self):
        ModeloJustificativa.objects.create(nome="ATRASO", texto="Texto A", area=self.area)
        ModeloJustificativa.objects.create(nome="ATRASO", texto="Texto B", area=self.outra)

        self.assertEqual(ModeloJustificativa.objects.filter(nome="ATRASO").count(), 2)

    # ── leitura ──

    def test_a_lista_de_modelos_nao_mostra_a_de_outra_area(self):
        resposta = self.client.get(reverse("justificativas:modelos_index"))

        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, "MODELO DA B")
        self.assertContains(resposta, "MODELO DA A")

    def test_o_seletor_do_quick_add_so_oferece_os_da_area(self):
        resposta = self.client.get(reverse("justificativas:index"))

        queryset = resposta.context["quick_add_form"].fields["modelo"].queryset
        self.assertTrue(queryset.filter(pk=self.meu.pk).exists())
        self.assertFalse(
            queryset.filter(pk=self.alheio.pk).exists(),
            msg="o seletor ofereceu o modelo de outra área — o texto dele iria para o documento",
        )

    def test_trocar_de_area_troca_os_modelos_oferecidos(self):
        """Prova que o recorte segue a área ativa, não o usuário."""
        self._trocar_para(self.outra)

        queryset = self.client.get(reverse("justificativas:index")).context[
            "quick_add_form"
        ].fields["modelo"].queryset

        self.assertTrue(queryset.filter(pk=self.alheio.pk).exists())
        self.assertFalse(queryset.filter(pk=self.meu.pk).exists())

    # ── escrita e caminhos destrutivos ──

    def test_modelo_criado_pela_tela_nasce_na_area_ativa(self):
        self.client.post(
            reverse("justificativas:modelos_index"),
            {"nome": "NOVO PELA TELA", "texto": "Texto novo", "ordem": 10, "ativo": "on"},
        )

        criado = ModeloJustificativa.objects.get(nome="NOVO PELA TELA")
        self.assertEqual(criado.area_id, self.area.pk)

    def test_nao_da_para_editar_modelo_de_outra_area_pelo_pk(self):
        resposta = self.client.post(
            reverse("justificativas:modelo_editar", args=[self.alheio.pk]),
            {"nome": "SEQUESTRADO", "texto": "Texto", "ordem": 10, "ativo": "on"},
        )

        self.assertEqual(resposta.status_code, 404)
        self.alheio.refresh_from_db()
        self.assertEqual(self.alheio.nome, "MODELO DA B")

    def test_nao_da_para_excluir_modelo_de_outra_area_pelo_pk(self):
        resposta = self.client.post(reverse("justificativas:modelo_excluir", args=[self.alheio.pk]))

        self.assertEqual(resposta.status_code, 404)
        self.assertTrue(ModeloJustificativa.objects.filter(pk=self.alheio.pk).exists())

    def test_nao_da_para_definir_padrao_em_modelo_de_outra_area(self):
        resposta = self.client.post(
            reverse("justificativas:modelo_definir_padrao", args=[self.alheio.pk])
        )

        self.assertEqual(resposta.status_code, 404)
        self.alheio.refresh_from_db()
        self.assertFalse(self.alheio.is_padrao)
