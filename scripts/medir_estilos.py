"""Compara o estilo COMPUTADO das telas entre duas versoes do CSS (NOVO-30 fase 4).

POR QUE ESTE INSTRUMENTO EXISTE

A fase 4 apaga `!important`. Nenhum teste diz se apagar mudou a tela: a pagina
responde 200, o HTML e o mesmo, e a suite fica verde tanto faz. O `medir_paleta.py`
mede cor de fundo; aqui a pergunta e outra — *alguma propriedade computada mudou?*

Uso:

    python manage.py runserver 127.0.0.1:8000 --noreload &
    python scripts/medir_estilos.py --salvar antes.json
    # ... mexe no CSS ...
    python scripts/medir_estilos.py --salvar depois.json
    python scripts/medir_estilos.py --diff antes.json depois.json

A chave de cada elemento e `tag.classe[:3]#ordem`, estavel entre execucoes desde
que o HTML nao mude — e ele nao muda, porque esta fase so toca CSS.

Elemento oculto ou de area zero fica de fora: o que nao pinta nao tem o que
comparar. O numero de elementos comparados sai no relatorio, para o alcance da
evidencia ficar explicito.
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"

PAGINAS = [
    ("dashboard", "/"),
    ("oficios-lista", "/oficios/"),
    ("oficio-novo", "/oficios/novo/"),
    ("configuracoes", "/cadastros/configuracao/"),
    ("perfil", "/perfil/"),
]

# As propriedades que os `!important` deste repositorio tocam.
PROPS = [
    "background-color", "background-image", "border-top-width", "border-top-style",
    "border-top-color", "border-bottom-color", "border-left-color", "border-right-color",
    "border-radius", "box-shadow", "color", "display", "opacity", "outline-style",
    "outline-width", "padding", "margin", "transform", "transition", "visibility",
    "font-size", "font-weight", "width", "height",
]

JS = """(props) => {
  const saida = {};
  const contagem = {};
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    if (r.width < 2 || r.height < 2 || cs.visibility === 'hidden' || cs.display === 'none') continue;
    const cls = (typeof el.className === 'string' ? el.className : '')
      .trim().split(/\\s+/).filter(Boolean).slice(0, 3).join('.');
    const base = el.tagName.toLowerCase() + (cls ? '.' + cls : '');
    contagem[base] = (contagem[base] || 0) + 1;
    const chave = base + '#' + contagem[base];
    const v = {};
    for (const p of props) v[p] = cs.getPropertyValue(p);
    saida[chave] = v;
  }
  return saida;
}"""


def coletar():
    dados = {}
    with sync_playwright() as pw:
        nav = pw.chromium.launch(
            executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
        ctx = nav.new_context(viewport={"width": 1500, "height": 950})
        pag = ctx.new_page()
        pag.goto(BASE + "/login/", wait_until="networkidle")
        pag.fill("input[name=username]", os.environ.get("USUARIO_MEDICAO", "olho"))
        pag.fill("input[name=password]", os.environ.get("SENHA_MEDICAO", "olho12345"))
        pag.click("button[type=submit]")
        pag.wait_for_load_state("networkidle")
        for tema in ("light", "dark"):
            for nome, rota in PAGINAS:
                try:
                    pag.goto(BASE + rota, wait_until="networkidle", timeout=25000)
                except Exception as e:
                    print(f"  {nome} [{tema}] nao abriu: {str(e)[:60]}", file=sys.stderr)
                    continue
                pag.evaluate(f"document.documentElement.setAttribute('data-theme','{tema}')")
                pag.wait_for_timeout(250)
                dados[f"{nome}/{tema}"] = pag.evaluate(JS, PROPS)
        nav.close()
    return dados


def diferenca(a, b):
    mudou = []
    for tela in sorted(set(a) | set(b)):
        ea, eb = a.get(tela, {}), b.get(tela, {})
        for chave in sorted(set(ea) & set(eb)):
            for prop, valor in ea[chave].items():
                novo = eb[chave].get(prop)
                if novo != valor:
                    mudou.append((tela, chave, prop, valor, novo))
    return mudou


if __name__ == "__main__":
    if "--diff" in sys.argv:
        i = sys.argv.index("--diff")
        a = json.load(open(sys.argv[i + 1]))
        b = json.load(open(sys.argv[i + 2]))
        comparados = sum(len(set(a.get(t, {})) & set(b.get(t, {}))) for t in set(a) | set(b))
        mudou = diferenca(a, b)
        print(f"elementos comparados: {comparados}")
        print(f"propriedades que mudaram: {len(mudou)}")
        for tela, chave, prop, va, vb in mudou[:60]:
            print(f"  {tela:24s} {chave[:46]:48s} {prop:20s} {va[:26]:28s} -> {vb[:26]}")
        if len(mudou) > 60:
            print(f"  … mais {len(mudou) - 60}")
        sys.exit(1 if mudou else 0)

    destino = sys.argv[sys.argv.index("--salvar") + 1] if "--salvar" in sys.argv else "estilos.json"
    d = coletar()
    json.dump(d, open(destino, "w"))
    print(f"{sum(len(v) for v in d.values())} elementos em {len(d)} telas -> {destino}")
