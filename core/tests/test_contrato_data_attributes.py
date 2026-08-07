"""`HT-13` — `docs/DATA_ATTRIBUTES_JS.md` só pode descrever o que existe.

O documento tinha virado um `PADRAO_*` apontando para o passado: **4 arquivos JS
que não existem mais** e **7 atributos com zero ocorrência no repositório** — o
enunciado do defeito dizia 3, a medição achou 7. Pior que estar incompleto é estar
errado: quem seguisse, erraria.

Rescrever não resolve sozinho — foi assim que ele apodreceu da primeira vez. O que
resolve é a suíte conferir, **nos dois sentidos**:

1. tudo que o documento cita existe no código (nada morto);
2. todo atributo que um **motor compartilhado** procura no DOM está citado
   (nada esquecido).

A segunda regra é a que faz o documento se manter: atributo novo em
`static/js/components/` ou `static/js/core/` reprova a suíte até ser documentado.

**Por que só os motores compartilhados.** Os atributos de uma página só são 137, cada
um com um único consumidor, e indexá-los aqui seria transcrever `static/js/pages/`
num arquivo Markdown que ninguém lê e todo mundo esquece. A fronteira é essa, está
escrita no documento, e é conferida por `test_a_fronteira_do_documento_e_a_medida`.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
DOC = RAIZ / "docs/DATA_ATTRIBUTES_JS.md"
JS = RAIZ / "static/js"

_ATRIBUTO = re.compile(r"data-[a-z0-9-]*[a-z0-9]")
_SELETOR = re.compile(r"\[(data-[a-z0-9-]+)")

#: Genéricos demais para virar linha de tabela: aparecem em vários motores com
#: significados diferentes e sempre acompanhando um atributo próprio já documentado
#: (`data-value` vem com `data-cv-state-option`, `data-id`/`data-key`/`data-ordem`/
#: `data-src` são chaves de item dentro de listas de página).
GENERICOS = {"data-value", "data-id", "data-key", "data-ordem", "data-src"}


def fontes_js() -> list[Path]:
    return [p for p in sorted(JS.rglob("*.js")) if "bundle" not in p.name]


def e_motor_compartilhado(caminho: Path) -> bool:
    """`pages/` e `dev/` são de uma tela só; o resto qualquer tela pode acionar."""
    rel = caminho.relative_to(JS).as_posix()
    return not rel.startswith(("pages/", "dev/"))


#: Trecho que cita, **de propósito**, o que foi removido. Fica fora da varredura.
HISTORICO = ("A versão anterior citava", "Nomes de classe CSS")


def corpo_vivo() -> str:
    """O documento sem o parágrafo que lista os mortos do `HT-13`."""
    texto = DOC.read_text(encoding="utf-8")
    inicio, fim = (texto.index(marca) for marca in HISTORICO)
    return texto[:inicio] + texto[fim:]


def citados_no_documento() -> set[str]:
    """Todo `data-*` do documento.

    A primeira versão desta função expandia sufixos abreviados (`-trigger`,
    `-form`) a partir do prefixo da mesma linha, e errou três vezes — inventou
    `data-file-selection-list-item`, `data-cv-filter-dropdown-value` e
    `data-segment-nav`, nenhum existente. A saída foi tirar a esperteza daqui e pôr
    o nome cheio no documento: referência que não dá para grepar não é referência.
    """
    return set(_ATRIBUTO.findall(corpo_vivo()))


def _todos_os_usados() -> set[str]:
    usados: set[str] = set()
    for js in fontes_js():
        usados.update(_ATRIBUTO.findall(js.read_text(encoding="utf-8", errors="replace")))
    for html in RAIZ.joinpath("templates").rglob("*.html"):
        usados.update(_ATRIBUTO.findall(html.read_text(encoding="utf-8", errors="replace")))
    return usados


TODOS_OS_USADOS = _todos_os_usados()


class DocumentoNaoCitaMortoTests(SimpleTestCase):
    def test_todo_atributo_citado_existe_no_codigo(self):
        """Era o defeito: 7 atributos citados com zero ocorrência no repositório."""
        fantasmas = sorted(a for a in citados_no_documento() if a not in TODOS_OS_USADOS)

        self.assertEqual(fantasmas, [], "atributo citado que não existe no código")

    def test_todo_arquivo_js_citado_existe(self):
        """Era a outra metade: 4 arquivos JS citados que já tinham sido removidos."""
        existentes = {p.name for p in fontes_js()}
        citados = set(re.findall(r"`([\w./-]+\.js)`", corpo_vivo()))
        fantasmas = sorted(c for c in citados if Path(c).name not in existentes)

        self.assertEqual(fantasmas, [], "arquivo JS citado que não existe")

    def test_o_bloco_historico_continua_citando_os_mortos(self):
        """A exceção da varredura não pode virar porta dos fundos.

        O parágrafo do `HT-13` fica fora da checagem porque cita os removidos **como
        removidos**. Se ele deixasse de fazer isso, a exceção passaria a esconder
        citação viva — então o que ele contém também é afirmado.
        """
        texto = DOC.read_text(encoding="utf-8")
        bloco = texto[texto.index(HISTORICO[0]) : texto.index(HISTORICO[1])]

        for morto in ("data-quick-add-toggle", "data-cv-select", "cv-search-picker.js"):
            with self.subTest(morto=morto):
                self.assertIn(morto, bloco)
                self.assertNotIn(morto, corpo_vivo())

    def test_a_varredura_esta_achando_o_documento(self):
        """Sem isto, as duas regras acima passariam com o documento vazio."""
        citados = citados_no_documento()

        self.assertGreaterEqual(len(citados), 120)
        self.assertIn("data-entity-picker-root", citados)
        self.assertIn("data-collection", citados)


class DocumentoNaoEsqueceMotorCompartilhadoTests(SimpleTestCase):
    """A regra que faz o documento se manter sozinho."""

    def seletores_compartilhados(self) -> dict[str, str]:
        achados: dict[str, str] = {}
        for js in fontes_js():
            if not e_motor_compartilhado(js):
                continue
            texto = js.read_text(encoding="utf-8", errors="replace")
            for atributo in _SELETOR.findall(texto):
                achados.setdefault(atributo, js.relative_to(JS).as_posix())
        return achados

    def test_todo_atributo_de_motor_compartilhado_esta_documentado(self):
        citados = citados_no_documento()
        faltando = sorted(
            f"{a} ({arquivo})"
            for a, arquivo in self.seletores_compartilhados().items()
            if a not in citados and a not in GENERICOS
        )

        self.assertEqual(faltando, [], "atributo de motor compartilhado fora do documento")

    def test_a_fronteira_do_documento_e_a_medida(self):
        """O documento afirma um número de atributos de página. Ele tem de bater.

        Sem isto a frase "são 137 deles" viraria decoração — e é justamente esse
        tipo de número solto que fez o documento apodrecer da primeira vez.
        """
        compartilhados = set(self.seletores_compartilhados())
        so_pagina = set()
        for js in fontes_js():
            if e_motor_compartilhado(js):
                continue
            texto = js.read_text(encoding="utf-8", errors="replace")
            so_pagina.update(a for a in _SELETOR.findall(texto) if a not in compartilhados)

        self.assertIn(str(len(so_pagina)), DOC.read_text(encoding="utf-8"))
