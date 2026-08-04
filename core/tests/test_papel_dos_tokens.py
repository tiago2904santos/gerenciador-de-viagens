"""Gate de papel de token (NOVO-30).

POR QUE ESTE TESTE EXISTE

A consolidacao de tokens colapsa nomes por proximidade de valor. Valor, porem,
nao carrega papel: `--color-primary` (fundo de botao) e `--color-white` (texto
do botao) podem ter historias diferentes e ainda assim cair no mesmo grupo. Foi
o que aconteceu na fase 3 do NOVO-30 — 96 regras ficaram com `background` e
`color` no MESMO token, e o sistema encheu de botao sem letra, chip vazio e aba
ativa em branco.

O detalhe que torna isto necessario: aquela entrega passou por 1311 testes
verdes, catraca de frontend em 10 e todos os demais gates. Nenhum deles olha a
tela, e texto invisivel nao quebra teste nenhum — a pagina responde 200, o HTML
tem o texto, so nao da para ler. Foi print de tela que achou.

Este teste custa milissegundos e fecha essa porta especifica. O instrumento
visual completo continua sendo `scripts/medir_paleta.py`, que roda sob demanda.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

CSS = Path(settings.BASE_DIR) / "static" / "css"

_REGRA = re.compile(r"([^{}]+)\{([^{}]*)\}")
_FUNDO = re.compile(r"(?:^|;)\s*background(?:-color)?\s*:\s*var\((--[a-z0-9-]+)\)\s*;")
_TEXTO = re.compile(r"(?:^|;)\s*color\s*:\s*var\((--[a-z0-9-]+)\)\s*;")
# `content: ""` marca pseudo-elemento decorativo: e um ponto/quadrado sem texto,
# entao fundo e cor iguais sao legitimos (o marcador de item selecionado do
# multiselect e assim). Sem esta excecao o gate acusaria falso positivo.
_CONTEUDO_VAZIO = re.compile(r"content\s*:\s*[\"']\s*[\"']")


def _regras_com_texto_invisivel() -> list[str]:
    achados = []
    for arquivo in sorted(CSS.rglob("*.css")):
        if arquivo.name == "shell.bundle.css":  # gerado; auditar as fontes
            continue
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        for regra in _REGRA.finditer(texto):
            corpo = regra.group(2)
            if _CONTEUDO_VAZIO.search(corpo):
                continue
            fundo = _FUNDO.search(corpo)
            cor = _TEXTO.search(corpo)
            if fundo and cor and fundo.group(1) == cor.group(1):
                linha = texto[: regra.start()].count("\n") + 1
                seletor = regra.group(1).strip().split("\n")[-1].strip()
                achados.append(
                    f"{arquivo.relative_to(settings.BASE_DIR).as_posix()}:{linha}"
                    f" — {seletor[:60]} usa {fundo.group(1)} em fundo E texto"
                )
    return achados


class PapelDoTokenTests(SimpleTestCase):
    def test_nenhuma_regra_pinta_texto_e_fundo_com_o_mesmo_token(self):
        """Fundo e texto sao papeis distintos, mesmo quando o valor coincide.

        Se esta lista voltar a crescer, quase sempre e uma consolidacao de
        tokens que agrupou por valor sem olhar em que propriedade cada nome era
        usado. A correcao NAO e afrouxar o teste: e separar os dois tokens de
        novo, ou trocar o `color` pelo par certo (`--on-accent` sobre acento,
        `--cv-ink` sobre superficie).
        """
        achados = _regras_com_texto_invisivel()
        self.assertEqual(
            achados,
            [],
            "texto invisivel — fundo e cor no mesmo token:\n" + "\n".join(achados[:15]),
        )
