"""Classe montada por interpolacao tem de ter regra (NOVO-37).

O TEMPLATE ESCREVE `cv-person-list--n{{ card.servidores_count }}`.

O nome final nunca aparece inteiro em lugar nenhum: nem no template, nem no
Python, nem no CSS de quem busca por texto. Uma varredura literal conclui que
`.cv-person-list--n3` nao tem consumidor — e apaga. A tela nao quebra teste
nenhum: o card responde 200 e so cai para o numero de colunas da regra base.

Foi o que aconteceu na fase 5a do `NOVO-30`: `--n0`, `--n3` e `--n5..--n9`
foram apagadas, e todo card de oficio/evento/termo com 3 ou 5+ servidores
passou a renderizar em duas colunas em vez de tres. A medicao de estilo
computado nao pegou porque depende do DADO — precisa existir um card com
exatamente aquela contagem nas telas medidas.

Este teste nao depende de dado. Ele le o template, extrai o prefixo colado a
interpolacao, e exige que a familia inteira tenha regra no CSS.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)
CSS_DIR = ROOT / "static" / "css"

# familia -> variantes que PRECISAM de regra propria.
#
# Nem toda variante entra: `--n2` e `--n4` nao tem regra de proposito, porque a
# regra base `.cv-person-list` ja e `repeat(2, ...)` e duas colunas e o que elas
# querem. Exigir regra para toda variante inventaria CSS. O que se protege aqui
# e o conjunto que EXISTE — se uma delas some, a coluna muda na tela.
FAMILIAS_COMPOSTAS = {
    # templates/eventos/partials/_evento_card_body.html e irmaos:
    # class="cv-person-list cv-person-list--n{{ card.servidores_count|default:0 }}"
    #   --n0/--n1 -> uma coluna · --n3 e --n5..--n9 -> tres colunas
    "cv-person-list--n": ["0", "1", "3", "5", "6", "7", "8", "9"],
}


def _css_fontes() -> list[Path]:
    return [f for f in sorted(CSS_DIR.rglob("*.css")) if f.name != "shell.bundle.css"]


class NomeCompostoTemRegraTests(SimpleTestCase):
    def setUp(self):
        self.css = "\n".join(f.read_text(encoding="utf-8") for f in _css_fontes())

    def test_toda_variante_composta_tem_regra(self):
        sem_regra = [
            f"{prefixo}{sufixo}"
            for prefixo, sufixos in FAMILIAS_COMPOSTAS.items()
            for sufixo in sufixos
            if not re.search(rf"\.{re.escape(prefixo + sufixo)}\b", self.css)
        ]
        self.assertEqual(
            sem_regra, [],
            "classe montada por interpolacao ficou sem CSS — a tela muda e "
            f"nenhum outro teste ve: {sem_regra}",
        )

    def test_o_template_ainda_monta_o_nome_do_jeito_declarado(self):
        """Se o template parar de compor, esta lista vira letra morta.

        O teste acima protegeria classes que ninguem mais emite, e o CSS morto
        voltaria pela porta dos fundos. Entao o prefixo tem de existir colado a
        uma interpolacao em algum template.
        """
        htmls = [f for f in (ROOT / "templates").rglob("*.html")]
        texto = "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in htmls)
        for prefixo in FAMILIAS_COMPOSTAS:
            self.assertRegex(
                texto, rf"{re.escape(prefixo)}(?:\{{\{{|\{{%)",
                f"nenhum template monta `{prefixo}` — tire a familia da lista "
                "em vez de manter CSS vivo por um consumidor que sumiu",
            )

    def test_o_auditor_de_css_morto_preserva_a_familia(self):
        """A defesa de verdade e o criterio do auditor, nao esta lista.

        A lista cobre uma familia; o auditor cobre todas as que seguem o padrao
        BEM. Se ele voltar a julgar `--n3` morta, o proximo corte apaga de novo
        e este arquivo vira o unico obstaculo — que alguem remove junto.
        """
        import importlib.util

        caminho = ROOT / "scripts" / "audit_css_morto.py"
        spec = importlib.util.spec_from_file_location("audit_css_morto", caminho)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        tokens = modulo.tokens_do_produto()
        for prefixo, sufixos in FAMILIAS_COMPOSTAS.items():
            for sufixo in sufixos:
                self.assertTrue(
                    modulo.viva(prefixo + sufixo, tokens),
                    f"o auditor considerou `{prefixo}{sufixo}` morta; o proximo "
                    "corte a apaga",
                )
