"""A recursão do editor de roteiro ao sugerir a chegada de um trecho (PR #27).

Reproduzida no navegador antes da correção: digitar a hora de saída de um trecho
disparava 43 eventos `change` no hidden da chegada e três
`Maximum call stack size exceeded` — para quatro teclas.

O caminho é fechado: `recalcCard` chama `setTrechoDateValue(card, 'chegada', …)`,
que dispara `change` no hidden; o `change` sobe até o listener do
`trechos-gerados-container`, que casa em `_chegada_` e chama `recalcCard` de
novo. Nada corta o ciclo, porque o `change` era disparado mesmo quando a data
recalculada era a mesma.

A correção tem duas camadas, e este arquivo guarda as duas:

1. as chamadas dentro de `recalcCard` passam `{ silent: true }` — mesmo padrão
   já usado na aplicação de datas em lote;
2. `setTrechoDateValue` só avisa quando a data **mudou** — a rede que segura um
   sexto chamador que esqueça o `silent`.

Medi cada camada isolada no navegador: só a guarda já derruba os 43 eventos para
1 e zera os erros; o `silent` leva a 0. Sem nenhuma das duas, os 43 voltam.

O teste é estático porque o projeto não roda JavaScript no CI. Ele não substitui
a reprodução no navegador — guarda o padrão que a reprodução provou correto.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


EDITOR_DIR = Path(settings.BASE_DIR) / "static" / "js" / "pages" / "roteiros" / "editor"


def _corpo_de_recalc_card() -> str:
    """Recorta o corpo de `recalcCard` contando chaves."""
    fonte = (EDITOR_DIR / "index.js").read_text(encoding="utf-8")
    inicio = fonte.index("function recalcCard(")
    abertura = fonte.index("{", inicio)
    profundidade = 0
    for pos in range(abertura, len(fonte)):
        if fonte[pos] == "{":
            profundidade += 1
        elif fonte[pos] == "}":
            profundidade -= 1
            if profundidade == 0:
                return fonte[abertura : pos + 1]
    raise AssertionError("não achei o fim de recalcCard")


class RecalcCardNaoReentraTests(SimpleTestCase):
    def test_recalc_card_so_escreve_a_data_de_chegada_em_silencio(self):
        corpo = _corpo_de_recalc_card()
        chamadas = re.findall(r"setTrechoDateValue\([^;]*?\);", corpo, re.S)

        self.assertGreaterEqual(
            len(chamadas),
            3,
            "recalcCard deveria seguir escrevendo a data de chegada sugerida",
        )
        barulhentas = [c for c in chamadas if "silent" not in c]
        self.assertEqual(
            barulhentas,
            [],
            "chamada sem `{ silent: true }` dentro de recalcCard reabre a recursão: "
            f"{barulhentas}",
        )

    def test_o_listener_do_container_ainda_recalcula_pela_data(self):
        """O `silent` não pode ser 'resolvido' desligando o listener.

        Se alguém tirar `_chegada_` das condições do listener, a recursão some —
        e junto some o recálculo quando o usuário edita a data na mão.
        """
        fonte = (EDITOR_DIR / "index.js").read_text(encoding="utf-8")

        self.assertIn("n.indexOf('_chegada_') !== -1", fonte)
        self.assertIn("recalcCard(c, true)", fonte)


class SetTrechoDateValueGuardaTests(SimpleTestCase):
    def test_o_change_so_sai_quando_a_data_muda(self):
        fonte = (EDITOR_DIR / "trechos.js").read_text(encoding="utf-8")
        inicio = fonte.index("export function setTrechoDateValue(")
        corpo = fonte[inicio : inicio + 1200]

        self.assertIn("var mudou = hidden.value !== (isoDate || '');", corpo)
        self.assertIn("if (mudou && !opts.silent) {", corpo)

        despachos = re.findall(r"dispatchEvent\(new Event\('change'", corpo)
        self.assertEqual(
            len(despachos),
            1,
            "um segundo dispatch sem a guarda traz a recursão de volta",
        )
