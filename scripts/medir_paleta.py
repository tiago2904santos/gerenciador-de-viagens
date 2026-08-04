"""Mede as cores realmente pintadas na tela, nos dois temas (NOVO-28).

Instrumento, nao gate: exige servidor de pe e Chromium, entao roda sob demanda
e nao no CI. O gate barato vive em core/tests/test_paleta.py.

Serve para duas coisas. A primeira e a evidencia de antes/depois no corpo do
PR. A segunda, mais util: tudo que ele lista como FORA DA PALETA e exatamente
a divida que sobrou — a saida dele e o insumo dos PRs seguintes, medida em vez
de estimada.

    python manage.py runserver 127.0.0.1:8000 --noreload &
    python scripts/medir_paleta.py

Usuario e senha vem de USUARIO_MEDICAO/SENHA_MEDICAO, ou caem no par de
desenvolvimento. Nao serve para ambiente com dado real.
"""
import os

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
SCR = os.environ.get("SAIDA_MEDICAO", "/tmp/paleta")
os.makedirs(SCR, exist_ok=True)

PAGINAS = [
    ("dashboard", "/"),
    ("oficios-lista", "/oficios/"),
    ("oficio-novo", "/oficios/novo/"),
    ("configuracoes", "/cadastros/configuracao/"),
    ("perfil", "/perfil/"),
]

# Conta as cores de fundo realmente pintadas e diz qual token cada uma e.
JS = """(paleta) => {
  const nome = {};
  for (const [k, v] of Object.entries(paleta)) nome[v] = k;
  const conta = {};
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 8) continue;
    const bg = getComputedStyle(el).backgroundColor;
    if (!bg || bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent') continue;
    if (!conta[bg]) conta[bg] = { n: 0, exemplo: '' };
    conta[bg].n += 1;
    if (!conta[bg].exemplo) {
      conta[bg].exemplo = el.tagName.toLowerCase() +
        (el.className && typeof el.className === 'string'
          ? '.' + el.className.trim().split(/\\s+/).slice(0, 2).join('.')
          : '');
    }
  }
  return { body: getComputedStyle(document.body).backgroundColor, conta, nome };
}"""


def rgb(hexa):
    h = hexa.lstrip("#")
    return f"rgb({int(h[0:2],16)}, {int(h[2:4],16)}, {int(h[4:6],16)})"


PALETA = {
    "light": {"page": rgb("#eceef1"), "card": rgb("#ffffff"), "block": rgb("#eceef1"),
              "acento": rgb("#155b9a")},
    "dark": {"page": rgb("#0d0f11"), "card": rgb("#191c1f"), "block": rgb("#23272b"),
             "acento": rgb("#d8a21b")},
}

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
    print("logado em:", pag.url)

    for tema in ("light", "dark"):
        conhecidas = {v: k for k, v in PALETA[tema].items()}
        for nome, rota in PAGINAS:
            try:
                pag.goto(BASE + rota, wait_until="networkidle", timeout=25000)
            except Exception as e:
                print(f"\n=== {nome} [{tema}] — nao abriu: {str(e)[:70]}")
                continue
            pag.evaluate(f"document.documentElement.setAttribute('data-theme','{tema}')")
            pag.wait_for_timeout(300)
            d = pag.evaluate(JS, PALETA[tema])
            fora = {c: v for c, v in d["conta"].items() if c not in conhecidas}
            print(f"\n=== {nome} [{tema}] === body={d['body']}"
                  f"  {'OK' if d['body'] == PALETA[tema]['page'] else 'FORA'}")
            for cor, v in sorted(d["conta"].items(), key=lambda x: -x[1]["n"])[:8]:
                marca = conhecidas.get(cor, "  <<< FORA DA PALETA")
                print(f"  {v['n']:4d}x  {cor:22} {marca:10} {v['exemplo'][:44]}")
            if fora:
                print(f"  ---> {len(fora)} cor(es) fora da paleta")
            pag.screenshot(path=f"{SCR}/{nome}-{tema}.png")
    nav.close()
