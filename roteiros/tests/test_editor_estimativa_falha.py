"""A estimativa automática de distância falhando em silêncio (JS-04).

`scheduleAutoEstimarTrechos` dispara `runAutoEstimarTrechos` por `setTimeout`
com 450 ms de debounce; a função serializa um POST por card de trecho num
`pending.reduce(...)` para preencher distância e tempo. Eram três defeitos numa
cadeia só:

1. **Nenhum `.catch`, em nenhum nível.** Falha de rede rejeitava o elo, e o
   `reduce` propagava a rejeição para o elo seguinte — os trechos restantes da
   fila eram cancelados junto, não só o que falhou.
2. **`ok:false` voltava calado.** Só `data.ok` era lido; `result.ok` (o status
   HTTP) nem chegava a ser consultado, e `data.error` ia para o lixo. HTTP 500,
   401 de sessão expirada e resposta não-JSON saíam todos pelo mesmo `return`
   mudo.
3. **A promise era descartada duas vezes** — pelo `setTimeout` e pela ausência
   de `return` antes do `reduce`. Não havia como esperar nem observar o fim.

O efeito para quem usa: os campos de distância e tempo ficam vazios sem
explicação, numa tela que alimenta valor de diária.

A correção tem três camadas, e este arquivo guarda as três: `.catch` DENTRO do
elo (para um trecho não derrubar os outros), normalização por `throw` (para o
erro do servidor chegar à tela) e a faixa `#trechos-error`, que não existia — o
editor tinha faixa para diárias e para o mapa, nenhuma para trechos.

A quarta camada é o `applyingState`: ele só voltava a `false` no caminho de
sucesso de `applyState`, então uma exceção na cadeia — inclusive na carga
inicial — travava o editor inteiro em silêncio.

O teste é estático porque o projeto não roda JavaScript no CI. Ele não substitui
a reprodução no navegador — guarda o padrão que a reprodução provou correto.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


EDITOR_DIR = Path(settings.BASE_DIR) / "static" / "js" / "pages" / "roteiros" / "editor"
TRECHOS_PARTIAL = (
    Path(settings.BASE_DIR)
    / "templates"
    / "roteiros"
    / "partials"
    / "roteiro"
    / "_trechos_gerados_body.html"
)


def _fonte_do_editor() -> str:
    return (EDITOR_DIR / "index.js").read_text(encoding="utf-8")


def _corpo_de(nome: str) -> str:
    """Recorta o corpo de uma função do editor contando chaves."""
    fonte = _fonte_do_editor()
    inicio = fonte.index("function %s(" % nome)
    abertura = fonte.index("{", inicio)
    profundidade = 0
    for pos in range(abertura, len(fonte)):
        if fonte[pos] == "{":
            profundidade += 1
        elif fonte[pos] == "}":
            profundidade -= 1
            if profundidade == 0:
                return fonte[abertura : pos + 1]
    raise AssertionError("não achei o fim de %s" % nome)


class EstimativaDeTrechoAvisaQuandoFalhaTests(SimpleTestCase):
    def test_cada_trecho_falha_sozinho_sem_derrubar_a_fila(self):
        corpo = _corpo_de("runAutoEstimarTrechos")

        # O `.catch` precisa estar DENTRO do elo do reduce. Um `.catch` só no
        # fim da cadeia capturaria o erro, mas a fila já teria morrido no
        # primeiro trecho — que é exatamente o defeito.
        elo = corpo[corpo.index("pending.reduce(") : corpo.index(", Promise.resolve())")]
        self.assertIn(
            ".catch(",
            elo,
            "sem `.catch` dentro do elo, uma falha de rede num trecho cancela "
            "todos os trechos seguintes da fila",
        )
        self.assertRegex(
            corpo,
            r"return pending\.reduce\(",
            "a promise precisa ser devolvida: sem isso não há como observar o fim",
        )

    def test_erro_do_servidor_chega_a_tela_e_ao_log(self):
        corpo = _corpo_de("runAutoEstimarTrechos")

        # Normaliza por `throw`, como `calculateDiarias` já fazia: o status HTTP
        # e o `ok` do payload viram o mesmo erro.
        self.assertIn(
            "!result.ok",
            corpo,
            "o status HTTP precisa ser lido — antes só `data.ok` era consultado",
        )
        self.assertIn(
            "data.error",
            corpo,
            "a mensagem do servidor era descartada",
        )
        self.assertIn("throw new Error(", corpo)
        self.assertIn("showTrechosError(", corpo)
        self.assertIn("window.CV.log.error(", corpo)

    def test_a_faixa_de_erro_existe_e_nasce_escondida(self):
        markup = TRECHOS_PARTIAL.read_text(encoding="utf-8")
        self.assertIn('id="trechos-error"', markup)
        self.assertIn("hidden", markup)
        self.assertIn('role="alert"', markup)
        # Design system, não o Bootstrap legado que o HT-03 vai varrer.
        self.assertIn("cv-notice", markup)
        self.assertNotIn("alert alert-", markup)

        fonte = _fonte_do_editor()
        for contrato in ("function showTrechosError(", "function clearTrechosError("):
            with self.subTest(contrato=contrato):
                self.assertIn(contrato, fonte)

    def test_apply_state_devolve_o_editor_mesmo_quando_a_cadeia_falha(self):
        corpo = _corpo_de("applyState")
        self.assertIn(
            ".finally(",
            corpo,
            "sem `.finally`, uma exceção na cadeia deixa `applyingState` travado "
            "em true e o editor para de responder, sem sinal na tela",
        )
        depois_do_finally = corpo[corpo.index(".finally(") :]
        self.assertIn("applyingState = false", depois_do_finally)


class EstimativaContinuaAcontecendoTests(SimpleTestCase):
    """A rede que impede 'consertar' o defeito desligando a estimativa.

    Um `.catch` que engolisse tudo, ou a remoção da chamada, passariam nas
    asserções acima. Estas fixam que o trabalho útil continua no lugar.
    """

    def test_a_estimativa_segue_sendo_pedida_e_aplicada(self):
        corpo = _corpo_de("runAutoEstimarTrechos")
        self.assertIn("window.CV.http.fetchJson(urlTrechosEstimar", corpo)
        self.assertIn("applyEstimarPayloadToTrechoCard(card, data)", corpo)
        for efeito in ("updateResumo()", "scheduleRealtimeDiarias()", "scheduleAutosave()"):
            with self.subTest(efeito=efeito):
                self.assertIn(efeito, corpo)

    def test_o_catch_do_elo_registra_em_vez_de_engolir(self):
        corpo = _corpo_de("runAutoEstimarTrechos")
        vazios = re.findall(r"\.catch\(function\s*\([^)]*\)\s*\{\s*\}\s*\)", corpo)
        self.assertEqual(
            vazios,
            [],
            "catch vazio devolve o silêncio que este ID veio corrigir",
        )
