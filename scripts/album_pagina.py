"""Monta a pagina unica do album a partir das capturas de `album_telas.py`.

    python scripts/album_telas.py
    python scripts/album_pagina.py screenshots/album-sistema

Le o `_relatorio.json`, embute cada WebP como data URI e escreve `album.html`
ao lado das imagens. A pagina e autocontida de proposito: abre offline e pode
ser publicada sem servir arquivo nenhum.

A paleta e a do proprio sistema (a mesma medida por `scripts/medir_paleta.py`),
para o album nao competir visualmente com o que ele mostra.
"""
from __future__ import annotations

import base64
import html
import json
import sys
from collections import OrderedDict
from pathlib import Path

RAIZ = Path(sys.argv[1] if len(sys.argv) > 1 else "screenshots/album-sistema")
SAIDA = RAIZ / "album.html"
DATA = "05/08/2026"

# Telas que existem no sistema mas nao entraram no album, com o motivo. Manter
# a lacuna visivel vale mais do que uma cobertura que parece completa.
LACUNAS = [
    ("/termos/oficio/&lt;pk&gt;/preview/", "erro 500",
     "termos/views.py:693 serializa o contexto com DjangoJSONEncoder, e o "
     "contexto carrega uma instancia de Cidade — <code>TypeError: Object of "
     "type Cidade is not JSON serializable</code>."),
    ("/planos-trabalho/&lt;pk&gt;/identificacao/", "erro 500",
     "templates/planos_trabalho/partials/resumo_evento_card.html:17 usa "
     "<code>total</code> dentro do mesmo <code>{% with %}</code> que o define; "
     "o Django resolve todos os valores do <code>with</code> no contexto de "
     "fora, entao o lookup falha em qualquer plano com mais de um evento."),
]

EXCLUIDOS = [
    "endpoints de API e JSON (<code>/api/…</code>, autosave, calculo de rota)",
    "download de arquivo (PDF, DOCX, ZIP) e visualizacao inline de PDF",
    "rotas POST-only (excluir, cancelar, retificar, definir padrao)",
    "fluxo publico de assinatura (<code>/prestacoes-contas/assinar/&lt;token&gt;/</code>), que exige token vivo",
    "Django admin (<code>/admin/</code>), que nao faz parte da interface do sistema",
]


def data_uri(caminho: Path) -> str:
    return "data:image/webp;base64," + base64.b64encode(caminho.read_bytes()).decode()


def montar() -> str:
    registros = json.loads((RAIZ / "_relatorio.json").read_text(encoding="utf-8"))
    telas: OrderedDict[int, dict] = OrderedDict()
    for r in sorted(registros, key=lambda x: x["ordem"]):
        if not r.get("webp"):
            continue
        tela = telas.setdefault(r["ordem"], {
            "ordem": r["ordem"], "grupo": r["grupo"], "titulo": r["titulo"],
            "rota": r["rota"], "interacao": bool(r.get("interacao")), "img": {},
        })
        tela["img"][r["tema"]] = data_uri(RAIZ / r["webp"])

    grupos: OrderedDict[str, list] = OrderedDict()
    for tela in telas.values():
        grupos.setdefault(tela["grupo"], []).append(tela)

    total = len(telas)
    total_imgs = sum(len(t["img"]) for t in telas.values())

    nav = "\n".join(
        f'<a class="rail__link" href="#g{i}"><span>{html.escape(g)}</span>'
        f'<span class="rail__count">{len(v)}</span></a>'
        for i, (g, v) in enumerate(grupos.items())
    )

    secoes = []
    for i, (grupo, itens) in enumerate(grupos.items()):
        cartoes = []
        for t in itens:
            selo = '<span class="card__flag">estado</span>' if t["interacao"] else ""
            cartoes.append(f"""
        <button class="card" type="button" data-ordem="{t['ordem']}"
                data-busca="{html.escape((t['titulo'] + ' ' + t['rota'] + ' ' + grupo).lower())}">
          <span class="card__shot">
            <img class="shot shot--light" src="{t['img'].get('light', '')}" alt="{html.escape(t['titulo'])} — tema claro" loading="lazy" decoding="async">
            <img class="shot shot--dark" src="{t['img'].get('dark', '')}" alt="{html.escape(t['titulo'])} — tema escuro" loading="lazy" decoding="async">
          </span>
          <span class="card__meta">
            <span class="card__idx">{t['ordem']:03d}</span>
            <span class="card__title">{html.escape(t['titulo'])}{selo}</span>
            <span class="card__route">{html.escape(t['rota'])}</span>
          </span>
        </button>""")
        secoes.append(f"""
    <section class="grupo" id="g{i}">
      <header class="grupo__head">
        <h2 class="grupo__title">{html.escape(grupo)}</h2>
        <span class="grupo__count">{len(itens)} tela{'s' if len(itens) > 1 else ''}</span>
      </header>
      <div class="grade">{''.join(cartoes)}
      </div>
    </section>""")

    lacunas = "\n".join(
        f"<li><code>{rota}</code> <span class=\"tag tag--erro\">{tag}</span>"
        f"<p>{txt}</p></li>" for rota, tag, txt in LACUNAS
    )
    excluidos = "\n".join(f"<li>{x}</li>" for x in EXCLUIDOS)

    dados_js = json.dumps(
        [{"ordem": t["ordem"], "titulo": t["titulo"], "rota": t["rota"],
          "grupo": t["grupo"]} for t in telas.values()],
        ensure_ascii=False,
    )

    return f"""<title>Álbum de telas — Central de Viagens 3</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {{
  --page:#eceef1; --card:#ffffff; --block:#e3e6ea; --linha:#d2d7de;
  --tinta:#12181f; --tinta-2:#4d5865; --tinta-3:#79848f;
  --acento:#155b9a; --acento-suave:#e4edf6; --alerta:#a3341f;
  --sombra:0 1px 2px rgba(16,26,38,.07), 0 6px 18px -10px rgba(16,26,38,.28);
  --rail:270px;
  --sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --page:#0d0f11; --card:#191c1f; --block:#23272b; --linha:#31363b;
    --tinta:#e9ebee; --tinta-2:#a3abb4; --tinta-3:#767f88;
    --acento:#d8a21b; --acento-suave:#2b2412; --alerta:#e0765c;
    --sombra:0 1px 2px rgba(0,0,0,.5), 0 8px 22px -12px rgba(0,0,0,.8);
  }}
}}
:root[data-theme="dark"] {{
  --page:#0d0f11; --card:#191c1f; --block:#23272b; --linha:#31363b;
  --tinta:#e9ebee; --tinta-2:#a3abb4; --tinta-3:#767f88;
  --acento:#d8a21b; --acento-suave:#2b2412; --alerta:#e0765c;
  --sombra:0 1px 2px rgba(0,0,0,.5), 0 8px 22px -12px rgba(0,0,0,.8);
}}
:root[data-theme="light"] {{
  --page:#eceef1; --card:#ffffff; --block:#e3e6ea; --linha:#d2d7de;
  --tinta:#12181f; --tinta-2:#4d5865; --tinta-3:#79848f;
  --acento:#155b9a; --acento-suave:#e4edf6; --alerta:#a3341f;
  --sombra:0 1px 2px rgba(16,26,38,.07), 0 6px 18px -10px rgba(16,26,38,.28);
}}

* {{ box-sizing:border-box; }}
body {{
  margin:0; background:var(--page); color:var(--tinta);
  font-family:var(--sans); font-size:15px; line-height:1.55;
  -webkit-font-smoothing:antialiased;
}}
code {{ font-family:var(--mono); font-size:.88em; }}

.layout {{ display:grid; grid-template-columns:var(--rail) minmax(0,1fr); align-items:start; }}

/* ── trilho, espelhando a navegação do próprio sistema ─────────────── */
.rail {{
  position:sticky; top:0; height:100vh; overflow-y:auto;
  padding:22px 16px; border-right:1px solid var(--linha); background:var(--card);
  display:flex; flex-direction:column; gap:18px;
}}
.rail__brand {{ display:flex; align-items:center; gap:10px; }}
.rail__mark {{
  width:30px; height:30px; border-radius:50%; background:var(--acento);
  color:var(--card); display:grid; place-items:center;
  font-size:11px; font-weight:700; letter-spacing:.04em; flex:none;
}}
.rail__name {{ font-weight:700; font-size:14px; line-height:1.25; }}
.rail__sub {{ font-size:11px; color:var(--tinta-3); }}
.rail__label {{
  font-family:var(--mono); font-size:10px; letter-spacing:.13em;
  text-transform:uppercase; color:var(--tinta-3);
}}
.rail__nav {{ display:flex; flex-direction:column; gap:1px; }}
.rail__link {{
  display:flex; justify-content:space-between; gap:10px; align-items:center;
  padding:7px 10px; border-radius:7px; text-decoration:none;
  color:var(--tinta-2); font-size:13.5px;
}}
.rail__link:hover, .rail__link:focus-visible {{ background:var(--block); color:var(--tinta); }}
.rail__count {{ font-family:var(--mono); font-size:11px; color:var(--tinta-3); }}
.rail__foot {{ margin-top:auto; font-size:11.5px; color:var(--tinta-3); }}

/* ── conteúdo ───────────────────────────────────────────────────────── */
.main {{ padding:34px 34px 80px; max-width:1500px; }}
.hero {{ display:flex; flex-direction:column; gap:6px; margin-bottom:26px; }}
.hero__eyebrow {{
  font-family:var(--mono); font-size:11px; letter-spacing:.14em;
  text-transform:uppercase; color:var(--acento);
}}
.hero h1 {{ margin:0; font-size:30px; line-height:1.15; letter-spacing:-.015em; text-wrap:balance; }}
.hero p {{ margin:2px 0 0; max-width:65ch; color:var(--tinta-2); }}

.numeros {{ display:flex; flex-wrap:wrap; gap:10px; margin:20px 0 26px; }}
.numero {{
  background:var(--card); border:1px solid var(--linha); border-radius:9px;
  padding:10px 14px; min-width:118px; box-shadow:var(--sombra);
}}
.numero b {{ display:block; font-size:22px; font-variant-numeric:tabular-nums; line-height:1.2; }}
.numero span {{
  font-family:var(--mono); font-size:10px; letter-spacing:.1em;
  text-transform:uppercase; color:var(--tinta-3);
}}

.barra {{
  position:sticky; top:0; z-index:20; display:flex; flex-wrap:wrap; gap:12px;
  align-items:center; padding:12px 0 14px; margin-bottom:8px;
  background:linear-gradient(var(--page) 78%, transparent);
}}
.busca {{
  flex:1 1 240px; min-width:200px; padding:9px 13px; border-radius:8px;
  border:1px solid var(--linha); background:var(--card); color:var(--tinta);
  font:inherit; font-size:14px;
}}
.busca::placeholder {{ color:var(--tinta-3); }}
.busca:focus-visible {{ outline:2px solid var(--acento); outline-offset:1px; }}
.switch {{
  display:flex; align-items:center; gap:9px; font-family:var(--mono);
  font-size:10px; letter-spacing:.11em; text-transform:uppercase; color:var(--tinta-3);
}}
.switch__grupo {{
  display:flex; background:var(--block); border:1px solid var(--linha);
  border-radius:8px; padding:2px; gap:2px;
}}
.switch__btn {{
  border:0; background:none; cursor:pointer; padding:6px 13px; border-radius:6px;
  font:inherit; font-size:11px; letter-spacing:.06em; color:var(--tinta-2);
}}
.switch__btn[aria-pressed="true"] {{ background:var(--acento); color:var(--card); font-weight:700; }}
.switch__btn:focus-visible {{ outline:2px solid var(--acento); outline-offset:2px; }}

.grupo {{ scroll-margin-top:76px; margin-bottom:38px; }}
.grupo__head {{
  display:flex; align-items:baseline; gap:12px;
  padding-bottom:8px; margin-bottom:16px; border-bottom:1px solid var(--linha);
}}
.grupo__title {{ margin:0; font-size:17px; letter-spacing:-.01em; }}
.grupo__count {{ font-family:var(--mono); font-size:11px; color:var(--tinta-3); }}
.grupo[hidden] {{ display:none; }}

.grade {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(268px,1fr)); gap:18px; }}
.card {{
  display:flex; flex-direction:column; text-align:left; padding:0; cursor:pointer;
  background:var(--card); border:1px solid var(--linha); border-radius:10px;
  overflow:hidden; box-shadow:var(--sombra); font:inherit; color:inherit;
  transition:transform .12s ease, border-color .12s ease;
}}
.card:hover {{ transform:translateY(-2px); border-color:var(--acento); }}
.card:focus-visible {{ outline:2px solid var(--acento); outline-offset:2px; }}
.card[hidden] {{ display:none; }}
.card__shot {{
  display:block; height:186px; overflow:hidden; background:var(--block);
  border-bottom:1px solid var(--linha);
}}
.shot {{ display:block; width:100%; height:auto; }}
:root[data-shots="light"] .shot--dark, :root[data-shots="dark"] .shot--light {{ display:none; }}
.card__meta {{ display:flex; flex-direction:column; gap:2px; padding:11px 13px 13px; }}
.card__idx {{
  font-family:var(--mono); font-size:10px; letter-spacing:.1em; color:var(--tinta-3);
}}
.card__title {{ font-size:13.5px; font-weight:650; line-height:1.35; }}
.card__flag {{
  margin-left:6px; padding:1px 6px; border-radius:20px; background:var(--acento-suave);
  color:var(--acento); font-family:var(--mono); font-size:9px; letter-spacing:.08em;
  text-transform:uppercase; vertical-align:1px;
}}
.card__route {{
  font-family:var(--mono); font-size:11px; color:var(--tinta-3);
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}}

.vazio {{ padding:40px 0; color:var(--tinta-3); }}
.vazio[hidden] {{ display:none; }}

/* ── notas ──────────────────────────────────────────────────────────── */
.notas {{
  display:grid; grid-template-columns:repeat(auto-fit,minmax(310px,1fr)); gap:18px;
  margin-top:46px; padding-top:26px; border-top:1px solid var(--linha);
}}
.nota {{ background:var(--card); border:1px solid var(--linha); border-radius:10px; padding:18px 20px; }}
.nota h3 {{ margin:0 0 4px; font-size:14px; }}
.nota > p {{ margin:0 0 12px; font-size:13px; color:var(--tinta-2); }}
.nota ul {{ margin:0; padding-left:17px; display:flex; flex-direction:column; gap:9px; font-size:13px; }}
.nota li p {{ margin:3px 0 0; color:var(--tinta-2); }}
.tag {{
  margin-left:6px; padding:1px 7px; border-radius:20px; font-family:var(--mono);
  font-size:9.5px; letter-spacing:.07em; text-transform:uppercase;
}}
.tag--erro {{ background:var(--alerta); color:var(--card); }}

/* ── visor ──────────────────────────────────────────────────────────── */
.visor {{ border:0; padding:0; width:min(1160px,94vw); max-height:92vh; background:var(--card);
  color:var(--tinta); border-radius:12px; overflow:hidden; }}
.visor::backdrop {{ background:rgba(9,12,15,.82); }}
.visor__head {{
  display:flex; flex-wrap:wrap; gap:12px; align-items:center;
  padding:13px 18px; border-bottom:1px solid var(--linha); background:var(--card);
}}
.visor__title {{ font-size:14.5px; font-weight:650; }}
.visor__route {{ font-family:var(--mono); font-size:11.5px; color:var(--tinta-3); }}
.visor__acoes {{ margin-left:auto; display:flex; gap:8px; align-items:center; }}
.visor__btn {{
  border:1px solid var(--linha); background:var(--block); color:var(--tinta-2);
  border-radius:7px; padding:6px 11px; cursor:pointer; font:inherit; font-size:12px;
}}
.visor__btn:hover {{ border-color:var(--acento); color:var(--tinta); }}
.visor__btn:focus-visible {{ outline:2px solid var(--acento); outline-offset:2px; }}
.visor__corpo {{ overflow:auto; max-height:calc(92vh - 58px); background:var(--block); }}
.visor__corpo img {{ display:block; width:100%; height:auto; }}

@media (max-width:900px) {{
  .layout {{ grid-template-columns:1fr; }}
  .rail {{ position:static; height:auto; border-right:0; border-bottom:1px solid var(--linha); }}
  .main {{ padding:24px 18px 60px; }}
}}
@media (prefers-reduced-motion: reduce) {{
  * {{ animation:none !important; transition:none !important; }}
}}
</style>

<div class="layout">
  <aside class="rail">
    <div class="rail__brand">
      <span class="rail__mark">CV</span>
      <span>
        <span class="rail__name">Central de Viagens 3</span><br>
        <span class="rail__sub">Álbum de telas · {DATA}</span>
      </span>
    </div>
    <span class="rail__label">Grupos</span>
    <nav class="rail__nav">{nav}</nav>
    <p class="rail__foot">
      Capturado em 1440×900, página inteira, banco de demonstração
      (<code>resetar_banco_demo</code>). Nenhum dado real.
    </p>
  </aside>

  <main class="main">
    <div class="hero">
      <span class="hero__eyebrow">Inventário visual</span>
      <h1>Todas as telas do sistema</h1>
      <p>
        Cada tela que renderiza página, nos dois temas, mais os estados que só
        existem depois de um clique — a edição em linha dos catálogos e os
        diálogos de confirmação. Clique em qualquer cartão para ver a captura
        inteira.
      </p>
    </div>

    <div class="numeros">
      <div class="numero"><b>{total}</b><span>telas</span></div>
      <div class="numero"><b>{total_imgs}</b><span>capturas</span></div>
      <div class="numero"><b>{len(grupos)}</b><span>grupos</span></div>
      <div class="numero"><b>2</b><span>temas</span></div>
    </div>

    <div class="barra">
      <input class="busca" id="busca" type="search" placeholder="Filtrar por nome ou rota…" aria-label="Filtrar telas">
      <div class="switch">
        <span>Tema das telas</span>
        <div class="switch__grupo" role="group" aria-label="Tema das telas capturadas">
          <button class="switch__btn" type="button" data-shots="light" aria-pressed="false">Claro</button>
          <button class="switch__btn" type="button" data-shots="dark" aria-pressed="true">Escuro</button>
        </div>
      </div>
    </div>

    {''.join(secoes)}

    <p class="vazio" id="vazio" hidden>Nenhuma tela corresponde ao filtro.</p>

    <div class="notas">
      <div class="nota">
        <h3>Telas que faltam</h3>
        <p>Duas rotas devolvem 500 com os dados de demonstração e por isso não têm captura.</p>
        <ul>{lacunas}</ul>
      </div>
      <div class="nota">
        <h3>Fora do álbum por não serem tela</h3>
        <p>Rotas que existem no <code>urls.py</code> mas não renderizam página.</p>
        <ul>{excluidos}</ul>
      </div>
    </div>
  </main>
</div>

<dialog class="visor" id="visor">
  <div class="visor__head">
    <span>
      <span class="visor__title" id="visorTitulo"></span><br>
      <span class="visor__route" id="visorRota"></span>
    </span>
    <span class="visor__acoes">
      <button class="visor__btn" type="button" id="visorTema">Ver no tema claro</button>
      <button class="visor__btn" type="button" id="visorAnterior" aria-label="Tela anterior">←</button>
      <button class="visor__btn" type="button" id="visorProxima" aria-label="Próxima tela">→</button>
      <button class="visor__btn" type="button" id="visorFechar">Fechar</button>
    </span>
  </div>
  <div class="visor__corpo"><img id="visorImg" alt=""></div>
</dialog>

<script>
const TELAS = {dados_js};
const raiz = document.documentElement;
raiz.setAttribute('data-shots', 'dark');

/* tema das capturas (independente do tema da própria página) */
document.querySelectorAll('.switch__btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    const tema = btn.dataset.shots;
    raiz.setAttribute('data-shots', tema);
    document.querySelectorAll('.switch__btn').forEach(b =>
      b.setAttribute('aria-pressed', String(b.dataset.shots === tema)));
    if (visor.open) mostrar(atual);
  }});
}});

/* filtro */
const busca = document.getElementById('busca');
const vazio = document.getElementById('vazio');
busca.addEventListener('input', () => {{
  const termo = busca.value.trim().toLowerCase();
  let visiveis = 0;
  document.querySelectorAll('.grupo').forEach(grupo => {{
    let n = 0;
    grupo.querySelectorAll('.card').forEach(card => {{
      const bate = !termo || card.dataset.busca.includes(termo);
      card.hidden = !bate;
      if (bate) n++;
    }});
    grupo.hidden = n === 0;
    visiveis += n;
  }});
  vazio.hidden = visiveis > 0;
}});

/* visor */
const visor = document.getElementById('visor');
const visorImg = document.getElementById('visorImg');
const visorTema = document.getElementById('visorTema');
let atual = null;

function cartao(ordem) {{
  return document.querySelector(`.card[data-ordem="${{ordem}}"]`);
}}

function mostrar(ordem) {{
  const card = cartao(ordem);
  if (!card) return;
  atual = ordem;
  const dados = TELAS.find(t => t.ordem === ordem);
  const tema = raiz.getAttribute('data-shots');
  const img = card.querySelector(tema === 'dark' ? '.shot--dark' : '.shot--light');
  visorImg.src = img.src;
  visorImg.alt = `${{dados.titulo}} — tema ${{tema === 'dark' ? 'escuro' : 'claro'}}`;
  document.getElementById('visorTitulo').textContent = dados.titulo;
  document.getElementById('visorRota').textContent = `${{dados.grupo}} · ${{dados.rota}}`;
  visorTema.textContent = tema === 'dark' ? 'Ver no tema claro' : 'Ver no tema escuro';
  visor.querySelector('.visor__corpo').scrollTop = 0;
}}

document.querySelectorAll('.card').forEach(card => {{
  card.addEventListener('click', () => {{
    mostrar(Number(card.dataset.ordem));
    if (!visor.open) visor.showModal();
  }});
}});

function passo(direcao) {{
  const lista = [...document.querySelectorAll('.card:not([hidden])')]
    .map(c => Number(c.dataset.ordem));
  const i = lista.indexOf(atual);
  if (i === -1) return;
  mostrar(lista[(i + direcao + lista.length) % lista.length]);
}}

document.getElementById('visorProxima').addEventListener('click', () => passo(1));
document.getElementById('visorAnterior').addEventListener('click', () => passo(-1));
document.getElementById('visorFechar').addEventListener('click', () => visor.close());
visorTema.addEventListener('click', () => {{
  const proximo = raiz.getAttribute('data-shots') === 'dark' ? 'light' : 'dark';
  document.querySelector(`.switch__btn[data-shots="${{proximo}}"]`).click();
}});
visor.addEventListener('click', e => {{ if (e.target === visor) visor.close(); }});
document.addEventListener('keydown', e => {{
  if (!visor.open) return;
  if (e.key === 'ArrowRight') passo(1);
  if (e.key === 'ArrowLeft') passo(-1);
}});
</script>
"""


if __name__ == "__main__":
    SAIDA.write_text(montar(), encoding="utf-8")
    print(f"{SAIDA} · {SAIDA.stat().st_size / 1e6:.1f} MB")
