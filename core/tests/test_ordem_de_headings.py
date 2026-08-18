"""`HT-05` — a ordem de cabeçalhos das listas não pode pular nível.

Leitor de tela navega por cabeçalho: `h1 → h3` some com um degrau da estrutura e
faz o usuário perder de onde está (WCAG 1.3.1). O `empty_state.html` fixava
`<h3>`, e como as `<section>` das listas se nomeiam por `aria-label` — não por
heading próprio — o título do estado vazio era filho direto do `<h1>` da página.

**Medido nas dez listas, todas vazias: `h1 → h3` em 10 de 10.** O enunciado do
plano dizia 9 de 10; a medição corrigiu para 10.

Este teste não afirma um número: ele **derruba a regra sobre o HTML renderizado**
de cada lista. Uma tela nova com estado vazio entra na varredura sozinha, e um
componente que volte a fixar nível é pego onde ele aparece, não onde foi escrito.
"""

from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from django.test import TestCase

#: As dez listas do sistema. Vazias no banco de teste, que é justamente o estado
#: em que o defeito aparece.
LISTAS = [
    ("ofícios", "/oficios/"),
    ("roteiros", "/roteiros/"),
    ("eventos", "/eventos/"),
    ("termos", "/termos/"),
    ("justificativas", "/justificativas/"),
    ("planos de trabalho", "/planos-trabalho/"),
    ("ordens de serviço", "/ordens-servico/"),
    ("prestações de contas", "/prestacoes-contas/"),
    ("servidores", "/cadastros/servidores/"),
    ("viaturas", "/cadastros/viaturas/"),
]

_HEADING = re.compile(r"<h([1-6])\b", re.IGNORECASE)


def niveis_de_heading(html: str) -> list[int]:
    return [int(nivel) for nivel in _HEADING.findall(html)]


def primeiro_pulo(niveis: list[int]) -> str | None:
    """`'h1->h3'` no primeiro degrau perdido, ou `None` se a ordem é contínua."""
    for anterior, seguinte in zip(niveis, niveis[1:], strict=False):
        if seguinte > anterior + 1:
            return f"h{anterior}->h{seguinte}"
    return None


class OrdemDeHeadingsNasListasTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester_ht05", password="123456",
        )
        self.client.force_login(self.user)

    def test_nenhuma_lista_pula_nivel_de_heading(self):
        for nome, url in LISTAS:
            with self.subTest(lista=nome):
                resposta = self.client.get(url)
                self.assertEqual(resposta.status_code, 200, f"{url} não abriu")
                html = resposta.content.decode()
                # Duas marcações, porque a migração é gradual: `empty-state` é
                # a do legado e `panel__empty` a do v2. Sem esta checagem o
                # teste passaria numa tela que parou de mostrar o estado vazio.
                self.assertTrue(
                    "empty-state" in html or "panel__empty" in html,
                    f"{url} não está exibindo estado vazio — o teste perdeu o alvo",
                )
                niveis = niveis_de_heading(html)
                self.assertIsNone(
                    primeiro_pulo(niveis),
                    f"{url} pula nível: {niveis}",
                )

    def test_o_estado_vazio_e_um_h2(self):
        """A metade que fixa o nível, e não só a ausência de pulo.

        Sem ela, mudar o default para 4 manteria "não pula" verdadeiro em
        qualquer página cujo `h1` fosse seguido de `h3` por outro motivo.
        """
        resposta = self.client.get("/oficios/")
        html = resposta.content.decode()

        # As duas marcações, pelo mesmo motivo do teste acima: `empty-state` é
        # a do legado e `panel__empty-title` a do v2, e a lista de ofícios já
        # migrou. O que se prova aqui é o NÍVEL do título, não qual folha o
        # desenha.
        self.assertRegex(
            html, r'<h2 class="(empty-state__title|panel__empty-title)">',
            "o título do estado vazio deixou de ser h2",
        )
