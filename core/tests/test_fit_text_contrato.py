"""O medidor do `fit-text` não pode voltar a perguntar ao `scrollWidth`.

`fit-text.js` encolhe o valor do cartão até caber em uma linha. Ele media o
estouro com `scrollWidth > clientWidth`, e essa medida é CEGA justamente no caso
que o componente existe para evitar: quando o elemento tem `text-overflow:
ellipsis` — que é o caso de todo `.fact__value` —, o Chrome devolve `scrollWidth`
limitado ao `clientWidth`. Assim que o texto começa a ser cortado, a medida passa
a dizer que ele cabe, e o laço para um degrau antes.

Medido na lista de Ofícios: "TOYOTA COROLLA XEI" ficava com 333,06px numa caixa
de 333px. Seis centésimos de pixel — e o custo na tela não foi de 0,06px, foi de
TRÊS CARACTERES, porque o navegador remove letras até abrir espaço para o próprio
"…". O cartão mostrava "TOYOTA COROLLA …" com 5px de sobra no bloco.

Este teste é estático de propósito: o defeito é de MEDIÇÃO, e jsdom não faz
layout — um teste de unidade em JS devolveria zero para as duas larguras e
passaria com o código errado.
"""
from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase


FONTE = Path(__file__).resolve().parents[2] / "static/js/components/fit-text.js"
_COMENTARIO = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)


def _corpo(codigo: str, nome: str) -> str:
    """O corpo da função, SEM comentário.

    Sem tirar o comentário, este arquivo se auto-reprova: as notas explicam o
    defeito citando `scrollWidth` e `clientWidth` pelo nome, e um teste que
    procura o nome no texto acha a explicação de por que não usá-lo. É a mesma
    armadilha do auditor de paleta, que conta cor citada em prosa.
    """
    trecho = codigo[codigo.index(f"function {nome}"):]
    trecho = trecho[: trecho.index("\n  }")]
    return _COMENTARIO.sub("", trecho)


class FitTextContratoTests(SimpleTestCase):
    def setUp(self):
        self.codigo = FONTE.read_text(encoding="utf-8")

    def test_nao_mede_estouro_por_scrollwidth(self):
        corpo = _corpo(self.codigo, "transborda")
        self.assertNotIn(
            "scrollWidth",
            corpo,
            "o estouro voltou a ser medido por scrollWidth, que o `ellipsis` limita",
        )

    def test_mede_o_texto_com_range(self):
        self.assertIn("createRange", self.codigo)
        self.assertIn("selectNodeContents", self.codigo)

    def test_a_caixa_e_medida_em_fracao(self):
        """`clientWidth` é inteiro; com os dois lados arredondando para lados
        diferentes sobra exatamente a folga em que o defeito vivia."""
        corpo = _corpo(self.codigo, "larguraUtil")
        self.assertIn("getBoundingClientRect", corpo)
        self.assertNotIn("clientWidth", corpo)

    def test_a_tolerancia_e_praticamente_zero(self):
        """Qualquer folga generosa aqui é uma palavra cortada na tela."""
        corpo = _corpo(self.codigo, "transborda")
        self.assertIn("+ 0.01", corpo)
