"""Gate de sintaxe do CSS (NOVO-36).

POR QUE ESTE TESTE EXISTE

Na fase 5a um seletor perdeu o parentese de fechamento — `:is(` aberto num
seletor multilinha. O efeito nao e local: o navegador declara o arquivo invalido
dali em diante e **descarta todas as regras seguintes**. No `shell.bundle.css`
foram 716 regras de 1.878 que simplesmente deixaram de existir, os icones
sumiram do sistema inteiro, e:

- a suite ficou verde (1.323 testes) — nenhum teste le CSS;
- o balanco de CHAVES continuou correto, entao a conferencia obvia passou;
- `collectstatic` e `build_shell_bundles --check` passaram, porque nenhum dos
  dois interpreta CSS;
- so a medicao de estilo computado no navegador acusou, e essa nao roda no CI.

Este gate e a versao barata do que o navegador faz: onde ele para de ler, aqui
o teste para tambem. Roda sem navegador, entao pode rodar sempre.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

CSS = Path(settings.BASE_DIR) / "static" / "css"
# Folha de terceiro: chega pronta, nao e nossa para consertar.
VENDIDOS = {"leaflet.css"}


def sem_comentario(css: str) -> str:
    """Comentario vira espaco do mesmo tamanho — as posicoes nao andam."""
    return re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), css, flags=re.S)


def preludes(css: str):
    """Cada texto que antecede um `{`, que e onde o seletor mora."""
    marco = 0
    for i, c in enumerate(css):
        if c in "{};":
            if c == "{":
                yield marco, css[marco:i]
            marco = i + 1


class SintaxeDoCSS(SimpleTestCase):
    def folhas(self):
        for caminho in sorted(CSS.rglob("*.css")):
            if caminho.name not in VENDIDOS:
                yield caminho

    def test_chaves_equilibradas(self):
        for caminho in self.folhas():
            texto = sem_comentario(caminho.read_text(encoding="utf-8"))
            self.assertEqual(
                texto.count("{"), texto.count("}"),
                f"{caminho.name}: bloco aberto sem fechar",
            )

    def test_seletor_nao_deixa_parentese_aberto(self):
        """`:is(`, `:not(`, `:has(` sem fechar levam o resto do arquivo junto."""
        for caminho in self.folhas():
            texto = sem_comentario(caminho.read_text(encoding="utf-8"))
            for pos, prelude in preludes(texto):
                if prelude.count("(") != prelude.count(")"):
                    linha = texto.count("\n", 0, pos) + 1
                    self.fail(
                        f"{caminho.name}:{linha}: parentese aberto no seletor "
                        f"{prelude.strip()[:90]!r} — o navegador descarta daqui "
                        f"em diante"
                    )

    def test_lista_de_seletores_nao_tem_item_vazio(self):
        """`.a, , .b` e `, .b` sao restos de corte automatico de seletor morto."""
        for caminho in self.folhas():
            texto = sem_comentario(caminho.read_text(encoding="utf-8"))
            for pos, prelude in preludes(texto):
                if prelude.strip().startswith("@"):
                    continue
                prof, atual, vazios = 0, [], []
                for c in prelude:
                    prof += (c == "(") - (c == ")")
                    if c == "," and prof == 0:
                        vazios.append("".join(atual).strip())
                        atual = []
                    else:
                        atual.append(c)
                vazios.append("".join(atual).strip())
                if prelude.strip() and not all(vazios):
                    linha = texto.count("\n", 0, pos) + 1
                    self.fail(
                        f"{caminho.name}:{linha}: seletor vazio na lista "
                        f"{prelude.strip()[:90]!r}"
                    )
