#!/usr/bin/env python
"""Retrato do estilo computado de todo `.cv-field__control` (`NOVO-54`).

O `NOVO-54` manda remover as sobrescritas que a regra base tornou redundantes,
"uma medicao por vez". Este e o instrumento dessa medicao: ele nao decide nada,
so fotografa. Roda antes e depois de mexer no CSS; diff vazio = a mudanca foi
neutra.

Por que nao da para provar por leitura estatica: das 63 regras que tocam a
classe, 24 sao de contexto, 15 de estado e 15 de tema. Contexto e estado so
existem com o elemento dentro do container certo e sob :hover/:focus, e nenhum
resolvedor estatico sabe qual elemento cai em qual regra sem montar a arvore.

Os estados sao forcados por `CSS.forcePseudoState` (CDP), nao por hover/focus de
verdade: o hover real alcanca um elemento por vez, e ai as 15 regras de estado
ficariam invisiveis para a medicao.

## ALCANCE MEDIDO — leia antes de confiar num diff vazio

`ROTAS` (de `rotas_do_sistema.py`) so tem rota sem argumento, e por isso a
primeira versao deste script encontrava campo em **8 rotas**: as paginas onde o
campo aparece de verdade sao as de wizard e edicao, que exigem PK. Daí `--rotas`:
um JSON com a lista de caminhos ja resolvidos (`/oficios/1/roteiro/`,
`/roteiros/9/editar/`, ...). Medido: com 57 caminhos sao 192 combinacoes
rota|tema|estado e 1048 leituras de campo, contra 64 e 224 antes.

Ampliar o alcance era, literalmente, o que a versao anterior deste arquivo
listava como "trabalho a fazer antes de remover essas regras".

**O que um diff vazio prova, e o que nao prova.** Prova neutralidade para o que
as rotas passadas exercitam, nos estados forcados. Nao prova nada sobre contexto
que so existe depois de interacao — modal fechado, passo de wizard nao aberto,
painel colapsado. Antes de remover uma regra, confira que o alvo dela aparece em
alguma rota da lista: `document.querySelectorAll(seletor).length > 0`. Rota
visitada nao e cobertura.

**Piso de ruido.** Rode duas vezes com o MESMO codigo antes de comparar. A
medicao nao volta zero: ha texto que muda de largura por 1px entre cargas.
Comparar contra zero em vez de contra o piso faz perseguir fantasma.

Uso (com o servidor de pe):
    python scripts/medir_campos_computados.py --senha SENHA --saida antes.json
    python scripts/medir_campos_computados.py --senha SENHA --saida ctrl.json
    # ... mexe no CSS ...
    python scripts/medir_campos_computados.py --senha SENHA --saida depois.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path.cwd().resolve()
while not (RAIZ / "manage.py").exists():
    if RAIZ.parent == RAIZ:
        sys.exit("rode a partir da raiz do projeto")
    RAIZ = RAIZ.parent
sys.path.insert(0, str(RAIZ))

from scripts.rotas_do_sistema import ROTAS  # noqa: E402

# So o que o campo de fato pinta. `getComputedStyle` devolve ~340 propriedades e
# a maioria e ruido que muda com a largura da janela.
PROPRIEDADES = [
    "background-color", "background-image",
    "border-top-width", "border-top-style", "border-top-color",
    "border-bottom-width", "border-bottom-style", "border-bottom-color",
    "border-radius", "box-shadow", "color",
    "outline-width", "outline-style", "outline-color", "outline-offset",
    "height", "min-height", "line-height",
    "padding-top", "padding-right", "padding-bottom", "padding-left",
    "font-size", "font-weight", "opacity",
]

ESTADOS = (
    (),
    ("hover",),
    ("focus", "focus-visible"),
    ("active",),
)

JS_COLETA = """
(props) => Array.from(document.querySelectorAll('.cv-field__control')).map((el, i) => {
  const c = getComputedStyle(el);
  const estilo = {};
  props.forEach(p => { estilo[p] = c.getPropertyValue(p); });
  return { chave: `${i}:${el.tagName.toLowerCase()}.${el.getAttribute('class') || ''}`, estilo };
})
"""


def carregar_rotas(caminho):
    """Caminhos a visitar: os do `--rotas`, ou as rotas sem argumento de `ROTAS`."""
    if not caminho:
        return [(r.slug, r.path) for r in ROTAS]
    lista = json.loads(Path(caminho).read_text(encoding="utf-8"))
    return [(p, p) for p in lista]


def medir(base_url, usuario, senha, temas, rotas):
    from playwright.sync_api import sync_playwright

    resultado: dict[str, list] = {}
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(
            executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
        )
        contexto = navegador.new_context(viewport={"width": 1440, "height": 900})
        pagina = contexto.new_page()

        pagina.goto(f"{base_url}/login/", wait_until="domcontentloaded")
        pagina.fill("input[name=username]", usuario)
        pagina.fill("input[name=password]", senha)
        pagina.press("input[name=password]", "Enter")
        pagina.wait_for_load_state("networkidle")

        cdp = contexto.new_cdp_session(pagina)
        cdp.send("DOM.enable")
        cdp.send("CSS.enable")

        for slug, caminho in rotas:
            for tema in temas:
                # `networkidle` nao serve: as paginas de roteiro tem pedido que o
                # proxy segura e nunca ficam ociosas, estouram o timeout e a rota
                # sumia da captura — e rota que sai do "antes" mas entra no
                # "depois" vira diferenca que nao existe. Espera fixa e
                # reprodutivel; e a falha ABORTA, porque comparar dois conjuntos
                # de rotas diferentes e pior que nao medir.
                try:
                    pagina.goto(
                        f"{base_url}{caminho}", wait_until="domcontentloaded", timeout=45000
                    )
                except Exception as erro:
                    sys.exit(f"rota {caminho} nao carregou: {str(erro).splitlines()[0]}")
                pagina.wait_for_timeout(700)
                pagina.evaluate(
                    "t => document.documentElement.setAttribute('data-theme', t)", tema
                )
                raiz = cdp.send("DOM.getDocument")["root"]["nodeId"]
                nos = cdp.send(
                    "DOM.querySelectorAll", {"nodeId": raiz, "selector": ".cv-field__control"}
                )["nodeIds"]
                if not nos:
                    continue
                for estados in ESTADOS:
                    for no in nos:
                        cdp.send(
                            "CSS.forcePseudoState",
                            {"nodeId": no, "forcedPseudoClasses": list(estados)},
                        )
                    rotulo = "+".join(estados) or "repouso"
                    resultado[f"{slug}|{tema}|{rotulo}"] = pagina.evaluate(
                        JS_COLETA, PROPRIEDADES
                    )
                for no in nos:  # devolve ao normal antes da proxima rota
                    cdp.send("CSS.forcePseudoState", {"nodeId": no, "forcedPseudoClasses": []})

        navegador.close()
    return resultado


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--usuario", default="medidor")
    p.add_argument("--senha", required=True)
    p.add_argument("--saida", required=True)
    p.add_argument("--temas", default="light,dark")
    p.add_argument(
        "--rotas",
        help="JSON com lista de caminhos ja resolvidos; sem isso usa as rotas "
             "sem argumento de rotas_do_sistema.py, que nao alcancam os wizards",
    )
    a = p.parse_args()

    rotas = carregar_rotas(a.rotas)
    dados = medir(a.base_url, a.usuario, a.senha, tuple(a.temas.split(",")), rotas)
    Path(a.saida).write_text(json.dumps(dados, indent=1, sort_keys=True), encoding="utf-8")
    leituras = sum(len(v) for v in dados.values())
    print(f"{len(rotas)} rotas, {len(dados)} combinacoes rota|tema|estado, "
          f"{leituras} leituras de campo")
    if not leituras:
        sys.exit("nenhum campo encontrado — a lista de rotas nao cobre nada")


if __name__ == "__main__":
    main()
