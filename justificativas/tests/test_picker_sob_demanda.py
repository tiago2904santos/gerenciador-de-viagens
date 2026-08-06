"""NOVO-07 — o seletor de ofício deixa de carregar a tabela inteira no HTML.

A régua do `PF-07` mediu `justificativas:index` com **15.295 KB** de HTML. O
`NOVO-06` derrubou para 5.141 KB por recortar por área — dividiu por três, não
resolveu. Medido no volume 200 (66 ofícios na área): o `json_script` sozinho eram
**45,1 KB**, ~680 bytes por ofício, e crescia com a tabela.

Agora o blob traz só os ofícios **já selecionados** e o resto chega por
`api_buscar_oficios`. O teste mais importante deste arquivo é o de que o
formulário continua **aceitando um pk que ele não renderizou** — é a regressão
que a mudança convida, e ela não apareceria em nenhuma tela até alguém tentar
salvar.
"""

from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from justificativas.models import Justificativa
from oficios.models import Oficio
from oficios.picker import LIMITE_BUSCA
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea


class PickerDeOficioSobDemandaTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="PK-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="PK-B")
        self.user = get_user_model().objects.create_user(username="picker_demanda")
        VinculoUsuarioArea.objects.create(usuario=self.user, area=self.area, area_padrao=True)
        self.client.force_login(self.user)

        self.meus = [
            Oficio.objects.create(
                numero=n, ano=2026, area=self.area, assunto=f"Deslocamento {n}", protocolo=f"P{n}"
            )
            for n in range(1, 6)
        ]
        self.alheio = Oficio.objects.create(
            numero=99, ano=2026, area=self.outra, assunto="Deslocamento da área B"
        )

    def _opcoes_do_seletor(self, html):
        """Só o miolo do `<select name="oficios">`.

        Procurar `value="N"` na página inteira é ruído: qualquer outro registro
        com o mesmo pk casaria e o teste passaria a mentir nas duas direções.
        """
        return html.split('name="oficios"', 1)[1].split("</select>", 1)[0]

    def _buscar(self, **params):
        resposta = self.client.get(reverse("justificativas:api_buscar_oficios"), params)
        self.assertEqual(resposta.status_code, 200)
        return json.loads(resposta.content)["resultados"]

    # ── o endpoint ──

    def test_a_busca_devolve_o_resumo_no_formato_que_o_picker_consome(self):
        resultados = self._buscar(q="Deslocamento 1")

        self.assertTrue(resultados)
        primeiro = resultados[0]
        for chave in ("id", "label", "numero", "search_text", "servidores_nomes"):
            self.assertIn(chave, primeiro, msg=f"o resumo perdeu a chave {chave!r}")

    def test_a_busca_nao_devolve_oficio_de_outra_area(self):
        resultados = self._buscar(q="Deslocamento")

        ids = {r["id"] for r in resultados}
        self.assertNotIn(self.alheio.pk, ids, msg="a busca vazou ofício de outra área")
        self.assertEqual(ids, {o.pk for o in self.meus})

    def test_a_busca_sem_termo_devolve_os_da_area(self):
        """Sem `q` o picker ainda pode querer semear a lista; o recorte continua."""
        ids = {r["id"] for r in self._buscar()}

        self.assertNotIn(self.alheio.pk, ids)

    def test_a_busca_respeita_o_teto(self):
        Oficio.objects.bulk_create(
            [
                Oficio(numero=1000 + n, ano=2026, area=self.area, assunto="Deslocamento em massa")
                for n in range(LIMITE_BUSCA + 10)
            ]
        )

        self.assertEqual(len(self._buscar(q="Deslocamento")), LIMITE_BUSCA)

    def test_a_busca_com_termo_que_nao_casa_devolve_vazio(self):
        self.assertEqual(self._buscar(q="zzzznadaaqui"), [])

    # ── o blob deixou de carregar tudo ──

    def test_o_blob_nao_traz_oficio_nenhum_quando_nada_esta_selecionado(self):
        resposta = self.client.get(reverse("justificativas:index"))

        self.assertEqual(
            resposta.context["oficios_summary"],
            {},
            msg="o blob continua carregando ofício sem ninguém ter selecionado",
        )

    def test_a_pagina_nao_renderiza_um_option_por_oficio(self):
        """O `<select>` também crescia com a tabela, 15× mais devagar que o blob."""
        opcoes = self._opcoes_do_seletor(
            self.client.get(reverse("justificativas:index")).content.decode()
        )

        for oficio in self.meus:
            self.assertNotIn(f'value="{oficio.pk}"', opcoes)

    # ── a regressão que a mudança convida ──

    def test_o_formulario_aceita_um_oficio_que_nao_foi_renderizado(self):
        """O campo renderiza só o selecionado, mas tem de VALIDAR qualquer um da área.

        Se o `queryset` fosse estreitado junto com o `choices`, salvar pelo picker
        pararia de funcionar — e nenhuma tela mostraria isso antes do submit.
        """
        escolhido = self.meus[3]

        resposta = self.client.post(
            reverse("justificativas:index"),
            {"oficios": [escolhido.pk], "texto": "Justificativa via picker", "modelo": ""},
        )

        self.assertIn(resposta.status_code, (200, 302))
        self.assertTrue(
            Justificativa.objects.filter(oficio=escolhido).exists(),
            msg="o formulário recusou um ofício válido da área só porque não o renderizou",
        )

    def test_o_formulario_continua_recusando_oficio_de_outra_area(self):
        """O recorte do `NOVO-06` não pode ter sido afrouxado pelo caminho."""
        self.client.post(
            reverse("justificativas:index"),
            {"oficios": [self.alheio.pk], "texto": "Tentativa", "modelo": ""},
        )

        self.assertFalse(Justificativa.objects.filter(oficio=self.alheio).exists())

    def test_depois_de_erro_de_validacao_a_escolha_continua_na_tela(self):
        """Re-render de formulário *bound*: a escolha está em `data`, não em `initial`."""
        escolhido = self.meus[2]

        resposta = self.client.post(
            reverse("justificativas:index"),
            {"oficios": [escolhido.pk], "texto": "", "modelo": ""},  # texto vazio → inválido
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertIn(
            str(escolhido.pk),
            resposta.context["oficios_summary"],
            msg="a escolha sumiu do resumo junto com a mensagem de erro",
        )
        self.assertContains(resposta, f'value="{escolhido.pk}"')
