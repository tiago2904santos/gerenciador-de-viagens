"""NOVO-06 — a tela de justificativas não recorta por área de trabalho.

Achado pela régua do `PF-07` (`scripts/medir_desempenho.py`): com 20.000
justificativas em três áreas, `page_obj.paginator.count` deu **20.000** contra
**6.666** da área ativa do usuário.

São **quatro** pontos, e dois deles não são de leitura:

1. `selectors.listar_justificativas()` — a lista mostra as de todas as áreas;
2. `views._oficios_summary_for_quick_add()` — o *picker* serializa todo ofício do
   banco no HTML por `json_script`; dado de outra área entregue ao navegador;
3. `forms.JustificativaQuickAddForm.oficios` — o campo aceita ofício de outra
   área, então dá para **criar** justificativa cruzando a fronteira;
4. `selectors.get_justificativa_by_id()` — sem recorte, e é o que
   `justificativa_excluir` usa: dá para **apagar** justificativa de outra área
   por `pk`.

`Justificativa` não tem campo `area` — o recorte vem por `oficio__area`, que é
sempre resolvível porque `oficio` é obrigatório e um-para-um. `ordens_servico` e
`termos` montam o mesmo *picker* e já aplicam `filter_queryset_by_area`
(`ordens_servico/forms.py:201`, `termos/forms.py:124`); justificativas era a
exceção.
"""

from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from justificativas.models import Justificativa
from justificativas.models import ModeloJustificativa
from oficios.models import Oficio
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea


class JustificativasNaoVazamEntreAreasTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="JUST-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="JUST-B")
        self.user = get_user_model().objects.create_user(username="just_area")
        VinculoUsuarioArea.objects.create(usuario=self.user, area=self.area, area_padrao=True)
        self.client.force_login(self.user)

        self.meu_oficio = Oficio.objects.create(numero=1, ano=2026, area=self.area, assunto="Meu ofício")
        self.oficio_alheio = Oficio.objects.create(
            numero=2, ano=2026, area=self.outra, assunto="Ofício da área B"
        )
        self.modelo = ModeloJustificativa.objects.create(nome="Modelo", texto="Texto", ativo=True)

        self.minha = Justificativa.objects.create(oficio=self.meu_oficio, texto="Minha justificativa")
        self.alheia = Justificativa.objects.create(
            oficio=self.oficio_alheio, texto="Justificativa da área B"
        )

    def _index(self):
        resposta = self.client.get(reverse("justificativas:index"))
        self.assertEqual(resposta.status_code, 200)
        return resposta

    # 1 — a lista

    def test_a_lista_nao_conta_justificativa_de_outra_area(self):
        resposta = self._index()

        self.assertEqual(
            resposta.context["page_obj"].paginator.count,
            1,
            msg="a paginação contou justificativa de outra área",
        )

    def test_a_lista_nao_mostra_o_texto_de_outra_area(self):
        """O texto vai renderizado na linha — não basta não contar, tem que não sair."""
        self.assertNotContains(self._index(), "Justificativa da área B")

    def test_a_lista_continua_mostrando_a_da_propria_area(self):
        resposta = self._index()

        self.assertEqual(
            [linha["title"] for linha in resposta.context["rows"]],
            [f"Oficio {self.meu_oficio.numero_formatado}"],
        )

    # 2 — o picker no HTML

    def test_o_picker_nao_entrega_oficio_de_outra_area(self):
        """`NOVO-07` mudou o caminho, não a garantia.

        O resumo deixou de ir inteiro no `json_script` e passou a vir do endpoint
        de busca — que é onde o recorte de área precisa valer agora.
        """
        resposta = self.client.get(reverse("justificativas:api_buscar_oficios"))
        ids = {item["id"] for item in json.loads(resposta.content)["resultados"]}

        self.assertNotIn(self.oficio_alheio.pk, ids)
        self.assertIn(self.meu_oficio.pk, ids)

    def test_o_assunto_de_outra_area_nao_aparece_no_html(self):
        """Continua valendo: nada de outra área pode sair no corpo da página."""
        self.assertNotContains(self._index(), "Ofício da área B")

    # 3 — o caminho de escrita

    def test_nao_da_para_criar_justificativa_para_oficio_de_outra_area(self):
        resposta = self.client.post(
            reverse("justificativas:index"),
            {
                "oficios": [self.oficio_alheio.pk],
                "texto": "Tentando cruzar a fronteira",
                "modelo": "",
            },
        )

        self.assertFalse(
            Justificativa.objects.filter(texto="Tentando cruzar a fronteira").exists(),
            msg="criou justificativa vinculada a ofício de outra área",
        )
        self.assertIn(resposta.status_code, (200, 302))

    def test_continua_dando_para_criar_para_oficio_da_propria_area(self):
        """O recorte não pode atropelar o fluxo normal."""
        outro_meu = Oficio.objects.create(numero=3, ano=2026, area=self.area, assunto="Outro meu")

        self.client.post(
            reverse("justificativas:index"),
            {"oficios": [outro_meu.pk], "texto": "Justificativa legítima", "modelo": ""},
        )

        self.assertTrue(Justificativa.objects.filter(oficio=outro_meu).exists())

    # 4 — o caminho destrutivo

    def test_nao_da_para_excluir_justificativa_de_outra_area(self):
        resposta = self.client.post(
            reverse("justificativas:justificativa_excluir", args=[self.alheia.pk])
        )

        self.assertEqual(resposta.status_code, 404)
        self.assertTrue(
            Justificativa.objects.filter(pk=self.alheia.pk).exists(),
            msg="apagou justificativa de outra área por pk",
        )

    def test_continua_dando_para_excluir_a_da_propria_area(self):
        self.client.post(reverse("justificativas:justificativa_excluir", args=[self.minha.pk]))

        self.assertFalse(Justificativa.objects.filter(pk=self.minha.pk).exists())
