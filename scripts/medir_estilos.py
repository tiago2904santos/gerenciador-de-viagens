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

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"

# A lista existe para cobrir os ARQUIVOS de CSS, nao para passear pelo sistema:
# cada folha grande precisa de pelo menos uma tela que a carregue, senao a medicao
# diz "0 mudou" sobre codigo que ninguem abriu. Foi ampliada na fase 5a, quando o
# corte pegou `roteiros.css` (1.526 linhas) e `oficios.css` (998) — nenhum dos dois
# coberto pelas cinco telas originais.
PAGINAS = [
    ("dashboard", "/"),                                  # dashboard, cards
    ("oficios-lista", "/oficios/"),                      # oficios, list-header, tabs
    ("oficio-novo", "/oficios/novo/"),
    ("oficios-modelos", "/oficios/modelos-motivo/"),
    ("oficios-modelo-novo", "/oficios/modelos-motivo/novo/"),
    ("configuracoes", "/cadastros/configuracao/"),       # cadastros-config, gdrive
    ("perfil", "/perfil/"),
    ("roteiros-lista", "/roteiros/"),                    # roteiros-list
    ("roteiro-novo", "/roteiros/novo/"),                 # roteiros (o maior corte)
    ("eventos-lista", "/eventos/"),                      # eventos-list
    ("evento-novo", "/eventos/novo/"),
    ("termos-lista", "/termos/"),                        # termos, stages
    ("termo-novo", "/termos/novo/"),
    ("justificativas", "/justificativas/"),              # justificativas
    ("justificativa-nova", "/justificativas/novo/"),
    ("planos-lista", "/planos-trabalho/"),               # planos-trabalho-eventos
    ("plano-novo", "/planos-trabalho/novo/"),
    ("planos-atividades", "/planos-trabalho/atividades/"),  # planos-trabalho-atividades
    ("ordens-lista", "/ordens-servico/"),                # ordens-servico
    ("ordem-nova", "/ordens-servico/nova/"),
    ("prestacoes", "/prestacoes-contas/"),               # prestacoes_contas
    ("prestacoes-modelos", "/prestacoes-contas/modelos-texto/"),
    ("diario-bordo", "/diario-bordo/"),                  # diario-troca
    ("documentos", "/documentos/"),                      # documents
    ("cadastros", "/cadastros/"),
    ("servidores", "/cadastros/servidores/"),            # lists, record-list
    ("servidor-novo", "/cadastros/servidores/novo/"),    # forms, cv-select
    ("viaturas", "/cadastros/viaturas/"),
    ("cidades", "/cadastros/cidades/"),
    ("usuarios", "/usuarios/"),                          # usuarios
    ("usuario-novo", "/usuarios/novo/"),
    # `static/css/dev/*` so e alcancado por aqui. Sem estas rotas, o segundo e o
    # terceiro maiores blocos de corte da fase 5 ficariam sem medicao nenhuma.
    ("ui-lab", "/dev/ui-lab/"),                          # dev/ui-lab-pages
    ("ui-lab-2", "/dev/ui-lab-2/"),
    ("ui-lab-buttons", "/dev/ui-lab/buttons/"),
    ("ui-lab-cards", "/dev/ui-lab/cards/"),
    ("ui-lab-documents", "/dev/ui-lab/documents/"),
    ("ui-lab-eventos-cadastro", "/dev/ui-lab/eventos/cadastro/"),
    ("ui-lab-eventos-lista", "/dev/ui-lab/eventos/lista/"),
    ("ui-lab-feedback", "/dev/ui-lab/feedback/"),
    ("ui-lab-fields", "/dev/ui-lab/fields/"),            # dev/ui-lab-fields
    ("ui-lab-headers", "/dev/ui-lab/headers/"),
    ("ui-lab-lists", "/dev/ui-lab/lists/"),
    ("ui-lab-overlays", "/dev/ui-lab/overlays/"),
    ("ui-lab-selects-filters", "/dev/ui-lab/selects-filters/"),
    ("ui-lab-signature", "/dev/ui-lab/signature/"),
    ("ui-lab-status", "/dev/ui-lab/status/"),
    ("ui-lab-structures", "/dev/ui-lab/structures/"),
    ("ui-lab-tables", "/dev/ui-lab/tables/"),
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
    dados, falhou = {}, []
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
                    try:
                        resp = pag.goto(BASE + rota, wait_until="networkidle",
                                        timeout=25000)
                    except PWTimeout:
                        # Tela que nunca fica ociosa (mapa, polling) nao pode
                        # ficar de fora da medicao: cai para `load`. O
                        # `roteiro-novo` — a pagina do MAIOR bloco de corte —
                        # estava saindo por este motivo, sem ninguem notar.
                        resp = pag.goto(BASE + rota, wait_until="load", timeout=40000)
                        pag.wait_for_timeout(3000)
                except Exception as e:
                    print(f"  {nome} [{tema}] nao abriu: {str(e)[:60]}", file=sys.stderr)
                    falhou.append(f"{nome}/{tema}")
                    # Uma tela que morre no meio da navegacao interrompe a
                    # proxima e derruba o resto da varredura em cascata.
                    # `about:blank` corta o encadeamento.
                    pag.goto("about:blank")
                    continue
                if resp is not None and resp.status >= 400:
                    print(f"  {nome} [{tema}] respondeu {resp.status}", file=sys.stderr)
                    falhou.append(f"{nome}/{tema}")
                    continue
                pag.evaluate(f"document.documentElement.setAttribute('data-theme','{tema}')")
                # Tira o ponteiro da tela: sem isso o elemento sob o mouse e
                # capturado em `:hover` e a comparacao acusa mudanca que nao
                # existe. A origem e o login — `page.click` move o ponteiro para
                # o botao, em (1007, 593) neste viewport, e o Playwright NAO o
                # devolve na navegacao; esse ponto cai dentro do 4o card do
                # Dashboard. As seis propriedades que a fase 5a leu como
                # diferenca eram exatamente `.summary-card:hover` (cards.css).
                #
                # Coordenada negativa, nao (2, 2): no canto superior esquerdo
                # mora a sidebar, que ficaria em `:hover` no lugar do card.
                pag.mouse.move(-5, -5)
                # Trocar de tema dispara `transition` de cor. Esperar por tempo nao
                # resolve: sobrou uma transicao a meio caminho e a leitura saiu
                # `rgb(150,...)` numa execucao e `rgb(151,...)` na seguinte, com o
                # CSS identico. Era esse o ruido que travou a fase 5a — seis
                # propriedades "mudadas" num card do Dashboard, sem causa no CSS.
                # Agora as transicoes sao levadas ao fim antes da leitura; as
                # infinitas (spinner) recusam `finish()` e ficam de fora, que e o
                # certo — elemento que nunca para nao tem valor estavel para medir.
                pag.evaluate("""() => {
                  for (const a of document.getAnimations()) {
                    try { a.finish(); } catch (e) { /* infinita: sem estado final */ }
                  }
                }""")
                pag.wait_for_timeout(120)
                # Guarda: se ainda houver algo em `:hover` abaixo do <body>, a
                # captura esta contaminada e nao serve de evidencia. Melhor
                # parar do que comparar lixo — foi comparando lixo que a fase 5a
                # perdeu um dia.
                sujo = pag.evaluate(
                    "() => [...document.querySelectorAll(':hover')]"
                    ".filter(e => !['HTML', 'BODY'].includes(e.tagName))"
                    ".map(e => e.tagName + '.' + (e.className || '')).slice(0, 3)")
                if sujo:
                    raise SystemExit(
                        f"captura contaminada por :hover em {nome} [{tema}]: {sujo}")
                dados[f"{nome}/{tema}"] = pag.evaluate(JS, PROPS)
        nav.close()
    if falhou:
        # Tela que nao abriu nao entra na evidencia; dizer quais e o que impede
        # a varredura de parecer mais larga do que foi.
        print(f"telas fora da medicao ({len(falhou)}): {', '.join(falhou)}",
              file=sys.stderr)
    return dados


def diferenca(a, b):
    """Propriedades mudadas, elementos que sumiram e elementos que surgiram.

    Sumir importa tanto quanto mudar: `JS` descarta o que tem area < 2px, entao
    um elemento que colapsou por causa da regra apagada some da captura em vez
    de aparecer como diferenca. Comparar so a intersecao esconderia exatamente
    o estrago que uma fase de delecao pode causar.
    """
    mudou, sumiu, surgiu = [], [], []
    for tela in sorted(set(a) | set(b)):
        ea, eb = a.get(tela, {}), b.get(tela, {})
        sumiu += [(tela, k) for k in sorted(set(ea) - set(eb))]
        surgiu += [(tela, k) for k in sorted(set(eb) - set(ea))]
        for chave in sorted(set(ea) & set(eb)):
            for prop, valor in ea[chave].items():
                novo = eb[chave].get(prop)
                if novo != valor:
                    mudou.append((tela, chave, prop, valor, novo))
    return mudou, sumiu, surgiu


if __name__ == "__main__":
    if "--diff" in sys.argv:
        i = sys.argv.index("--diff")
        a = json.load(open(sys.argv[i + 1]))
        b = json.load(open(sys.argv[i + 2]))
        comparados = sum(len(set(a.get(t, {})) & set(b.get(t, {}))) for t in set(a) | set(b))
        mudou, sumiu, surgiu = diferenca(a, b)
        print(f"elementos comparados: {comparados}")
        print(f"propriedades que mudaram: {len(mudou)}")
        for tela, chave, prop, va, vb in mudou[:60]:
            print(f"  {tela:24s} {chave[:46]:48s} {prop:20s} {va[:26]:28s} -> {vb[:26]}")
        if len(mudou) > 60:
            print(f"  … mais {len(mudou) - 60}")
        for rotulo, lista in (("sumiram", sumiu), ("surgiram", surgiu)):
            print(f"elementos que {rotulo}: {len(lista)}")
            for tela, chave in lista[:20]:
                print(f"  {tela:24s} {chave}")
            if len(lista) > 20:
                print(f"  … mais {len(lista) - 20}")
        sys.exit(1 if (mudou or sumiu or surgiu) else 0)

    destino = sys.argv[sys.argv.index("--salvar") + 1] if "--salvar" in sys.argv else "estilos.json"
    d = coletar()
    json.dump(d, open(destino, "w"))
    print(f"{sum(len(v) for v in d.values())} elementos em {len(d)} telas -> {destino}")
