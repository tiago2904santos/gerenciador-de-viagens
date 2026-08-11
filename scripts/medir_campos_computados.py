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
`/roteiros/9/editar/`, ...). Medido: com 56 caminhos sao 208 combinacoes
rota|tema|estado e 1144 leituras de campo, contra 64 e 224 antes.

**Rota quebrada aborta.** `page.goto()` NAO levanta em 404, 500 nem em
redirecionamento para o login — devolve a resposta e segue. Sem conferir status
e URL final, a rota caia no ramo "nenhum campo" e sumia em silencio: foi assim
que `/prestacoes-contas/1/`, que nao existe, passou tres medicoes inteiras
contando como cobertura.

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
from scripts.navegador_medicao import abrir_chromium  # noqa: E402

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
    # Separados de propósito: forçar os dois de uma vez escondia regras que
    # valem apenas para foco por ponteiro atrás do piso global de
    # ``:focus-visible``. A combinação continua medida porque é o estado real
    # de navegação por teclado nos controles nativos.
    ("focus",),
    ("focus-visible",),
    ("focus", "focus-visible"),
    ("active",),
)

JS_COLETA = """
(props) => Array.from(document.querySelectorAll('.cv-field__control')).map((el, i) => {
  const c = getComputedStyle(el);
  const estilo = {};
  props.forEach(p => { estilo[p] = c.getPropertyValue(p); });
  return {
    chave: `${i}:${el.tagName.toLowerCase()}.${el.getAttribute('class') || ''}`,
    texto: 'value' in el ? el.value : (el.textContent || ''),
    estilo,
  };
})
"""

JS_ESPERAR_ESTILO = """
() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
"""

CSS_SEM_MOVIMENTO = """
*, *::before, *::after {
  animation: none !important;
  transition: none !important;
}
"""


def carregar_rotas(caminho):
    """Caminhos a visitar: os do `--rotas`, ou as rotas sem argumento de `ROTAS`."""
    if not caminho:
        return [(r.slug, r.path) for r in ROTAS]
    lista = json.loads(Path(caminho).read_text(encoding="utf-8"))
    return [(p, p) for p in lista]


def esperar_arvore_estavel(pagina, quieto_ms=400, teto_ms=8000):
    """Espera a arvore parar de crescer, em vez de contar um tempo fixo.

    O editor de roteiro so materializa os campos depois de `loadCities(...)`
    resolver e `renderTrechos` rodar. Com espera fixa, uma rede mais lenta numa
    das capturas mede a pagina antes dos campos existirem — e ai a regra que
    pinta esses campos parece inocua porque ninguem olhou para eles. Contar
    elementos ate o numero repetir amarra a medicao ao DOM, nao ao relogio.
    """
    anterior = -1
    parado = 0
    passo = 100
    for _ in range(teto_ms // passo):
        atual = pagina.evaluate("() => document.getElementsByTagName('*').length")
        parado = parado + passo if atual == anterior else 0
        anterior = atual
        if parado >= quieto_ms:
            return atual
        pagina.wait_for_timeout(passo)
    return anterior


def medir(base_url, usuario, senha, temas, rotas):
    from playwright.sync_api import sync_playwright

    resultado: dict[str, list] = {}
    with sync_playwright() as pw:
        navegador = abrir_chromium(pw)
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
                # "depois" vira diferenca que nao existe. Espera ate a arvore
                # parar de crescer, e a falha ABORTA: comparar dois conjuntos de
                # rotas diferentes e pior que nao medir.
                try:
                    resposta = pagina.goto(
                        f"{base_url}{caminho}", wait_until="domcontentloaded", timeout=45000
                    )
                except Exception as erro:
                    sys.exit(f"rota {caminho} nao carregou: {str(erro).splitlines()[0]}")

                # `goto` NAO levanta em 404, 500 nem em redirecionamento para o
                # login: devolve a resposta e segue. Sem conferir aqui, a rota
                # cairia no ramo "nenhum campo" e sumiria em silencio — e uma
                # captura com uma rota boa e vinte quebradas aprovaria remocao
                # alegando cobertura que nao houve.
                if resposta is not None and resposta.status >= 400:
                    sys.exit(f"rota {caminho} respondeu {resposta.status}")
                if "/login" in pagina.url and "/login" not in caminho:
                    sys.exit(f"rota {caminho} caiu no login: sessao perdida")
                esperar_arvore_estavel(pagina)
                # A regra da E0 também vale aqui: capturar no meio de uma
                # transição produz cores e sombras fracionárias diferentes
                # entre duas execuções do mesmo código. O medidor compara a
                # cascata estabilizada, não um frame acidental da animação.
                pagina.add_style_tag(content=CSS_SEM_MOVIMENTO)
                pagina.evaluate(
                    "t => document.documentElement.setAttribute('data-theme', t)", tema
                )
                pagina.evaluate(JS_ESPERAR_ESTILO)
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
                    pagina.evaluate(JS_ESPERAR_ESTILO)
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
