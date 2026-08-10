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

Rodado contra as 43 rotas de `rotas_do_sistema.py`, nos dois temas e em quatro
estados, ele encontra campo em **8 rotas**: eventos-lista, justificativas-lista,
oficios-lista, oficios-modelos-motivo-lista, oficios-modelos-motivo-novo,
prestacoes-contas-lista, roteiros-novo, termos-lista. Sao 64 combinacoes e 224
leituras.

As outras 35 rotas devolvem zero elementos, e nao e defeito do script: dos 11
templates que emitem a classe, a maioria e partial que so entra no DOM depois de
interacao — `cotton/ui/modals/cancel_reason_modal.html` atras de um modal,
`_atividades_body.html` dentro de um passo de wizard,
`cadastros/configuracao/partials/_diarias_fields.html` dentro de um corpo
colapsavel.

**Consequencia pratica:** um diff vazio prova neutralidade para o que estas 8
rotas exercitam, e nada alem. Para as regras de contexto que so valem dentro de
modal ou passo de wizard, este instrumento ainda nao serve de prova — ampliar o
alcance (abrir os modais e navegar os passos) e trabalho a fazer antes de
remover essas regras.

Uso (com o servidor de pe):
    python scripts/medir_campos_computados.py --senha SENHA --saida antes.json
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


def medir(base_url, usuario, senha, temas):
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

        for rota in ROTAS:
            for tema in temas:
                try:
                    pagina.goto(f"{base_url}{rota.path}", wait_until="networkidle", timeout=30000)
                except Exception as erro:
                    resultado[f"{rota.slug}|{tema}|ERRO"] = [{"erro": str(erro)[:120]}]
                    continue
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
                    resultado[f"{rota.slug}|{tema}|{rotulo}"] = pagina.evaluate(
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
    a = p.parse_args()

    dados = medir(a.base_url, a.usuario, a.senha, tuple(a.temas.split(",")))
    Path(a.saida).write_text(json.dumps(dados, indent=1, sort_keys=True), encoding="utf-8")
    erros = [k for k in dados if k.endswith("|ERRO")]
    leituras = sum(len(v) for k, v in dados.items() if not k.endswith("|ERRO"))
    print(f"{len(dados)} combinacoes rota|tema|estado, {leituras} leituras de campo")
    if erros:
        print(f"ATENCAO: {len(erros)} rotas falharam: {erros[:5]}")


if __name__ == "__main__":
    main()
