"""Criar pasta no Drive: `.then` solto escapava do `try/catch` (NOVO-24).

`static/js/pages/gdrive_config.js`, no clique de "Criar pasta": depois de criar a
pasta o código encadeava `loadPastas(currentPaiId()).then(...)` **sem `await`**.
Duas consequências, as duas medidas no navegador antes de mexer:

1. **O callback ficava fora do `try`.** Qualquer erro dentro dele não chegava ao
   `catch` e virava exceção solta no console. O gatilho real é o modo mock:
   `services.py:200` monta o id da pasta como `"mock-nova-" + nome digitado`, e
   esse id ia cru para dentro de um seletor de atributo — um nome com aspas
   (`Ação "2026"`) estourava
   `Failed to execute 'querySelector' … is not a valid selector`. Na tela: a
   pasta aparecia na lista, mas não vinha selecionada, e nada explicava por quê.
2. **O `finally` passava por cima da recarga.** Medido: o botão voltava a
   `disabled = false` **antes** de a listagem responder, então "Criar pasta"
   ficava clicável com a lista ainda em "Carregando…".

O teste é estático porque o projeto não roda JavaScript no CI (`JS-03`). Ele não
substitui a reprodução no navegador — guarda o padrão que a reprodução provou
correto.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

PAGINA = Path(settings.BASE_DIR) / "static" / "js" / "pages" / "gdrive_config.js"


def _bloco_a_partir_de(marcador: str) -> str:
    """Recorta um bloco `{...}` do arquivo contando chaves a partir do marcador."""
    fonte = PAGINA.read_text(encoding="utf-8")
    if marcador not in fonte:
        raise AssertionError(
            "não achei %r em %s — o contrato que este ID fixou saiu do lugar"
            % (marcador, PAGINA.name)
        )
    inicio = fonte.index(marcador)
    abertura = fonte.index("{", inicio)
    profundidade = 0
    for pos in range(abertura, len(fonte)):
        if fonte[pos] == "{":
            profundidade += 1
        elif fonte[pos] == "}":
            profundidade -= 1
            if profundidade == 0:
                return fonte[abertura : pos + 1]
    raise AssertionError("não achei o fim do bloco de %r" % marcador)


def _handler_criar() -> str:
    return _bloco_a_partir_de('btnCriar.addEventListener("click"')


class CriarPastaEsperaARecargaTests(SimpleTestCase):
    def test_a_recarga_e_aguardada_em_vez_de_encadeada(self):
        corpo = _handler_criar()
        self.assertIn(
            "await loadPastas(",
            corpo,
            "sem `await`, o callback da recarga fica fora do `try` e o erro dele "
            "não chega ao `catch` — é o NOVO-24",
        )
        self.assertNotIn(
            "loadPastas(currentPaiId()).then(",
            corpo,
            "`.then` encadeado devolve exatamente o defeito que este ID corrigiu",
        )

    def test_o_botao_so_volta_depois_que_a_recarga_termina(self):
        """Medido: com `.then`, o `finally` rodava antes de a listagem responder."""
        corpo = _handler_criar()
        self.assertIn("await loadPastas(", corpo)
        self.assertLess(
            corpo.index("await loadPastas("),
            corpo.index("} finally {"),
            "a recarga precisa ser aguardada dentro do `try`, senão o `finally` "
            "reabilita 'Criar pasta' com a lista ainda carregando",
        )


class SelecaoDaPastaCriadaTests(SimpleTestCase):
    def test_o_id_entra_escapado_no_seletor(self):
        corpo = _bloco_a_partir_de("function selecionarPastaCriada(")
        self.assertIn("CSS.escape(", corpo)
        self.assertNotIn(
            '[data-id="${data.pasta.id}"]',
            PAGINA.read_text(encoding="utf-8"),
            "no modo mock o id carrega o nome digitado pelo usuário: sem escape, "
            "uma aspa quebra o seletor",
        )

    def test_sem_id_a_selecao_desiste_em_vez_de_estourar(self):
        corpo = _bloco_a_partir_de("function selecionarPastaCriada(")
        self.assertIn(
            "if (!id) return;",
            corpo,
            "`data.pasta` ausente virava TypeError solto; a pasta já foi criada, "
            "então o certo é não selecionar e seguir",
        )

    def test_a_falha_de_selecao_nao_vira_erro_de_criacao(self):
        """A pasta já existe no servidor quando a seleção roda.

        Dizer "não foi possível criar a pasta" ali seria a mesma mentira que o
        `NOVO-23` corrigiu no modal de assinado.
        """
        corpo = _handler_criar()
        self.assertIn("selecionarPastaCriada(", corpo)
        self.assertLess(
            corpo.index("selecionarPastaCriada("),
            corpo.index("} catch (err) {"),
            "a chamada precisa estar dentro do `try`, depois do `await`",
        )
        self.assertIn("Não foi possível criar a pasta: ", corpo)


class CriacaoContinuaAcontecendoTests(SimpleTestCase):
    """A rede que impede 'consertar' o defeito desligando o que funcionava."""

    def test_o_post_de_criacao_e_a_recarga_seguem_no_lugar(self):
        corpo = _handler_criar()
        self.assertIn("window.CV.http.fetchJson(urlCriar", corpo)
        self.assertIn('method: "POST"', corpo)
        self.assertIn("await loadPastas(currentPaiId())", corpo)
        self.assertIn(".gdrive-folder-item__select", _bloco_a_partir_de(
            "function selecionarPastaCriada("
        ))
