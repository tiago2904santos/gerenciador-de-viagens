#!/usr/bin/env python
"""Régua das regras visuais que valem em TODA tela (2026-08-21).

Existe porque a revisão visual página a página encontrou, em Ofícios, quatro
defeitos que não eram daquela tela — eram do sistema, e estavam em todas as
outras. Corrigir e conferir só onde o olho passou deixaria as outras 42 rotas
esperando a próxima leva de prints.

Confere, em cada rota do corpus e nos DOIS temas:

* **faixa de filtros em uma linha** — a banda é de uma linha por desenho; com
  cinco controles ela quebrava e dobrava de altura;
* **valor de fato cortado** — mede o TEXTO com `Range` e a CAIXA em fração, e
  não por `scrollWidth`/`clientWidth`: o `text-overflow: ellipsis` faz o
  `scrollWidth` mentir, e foi assim que "TOYOTA COROLLA XEI" saía cortado por
  0,06px;
* **bloco de cartão com conteúdo maior que a caixa** — o teto de altura é o que
  mantém os cartões do mesmo tamanho, e um vão fixo dentro dele corta conteúdo;
* **tom de menu fora do vocabulário por função** — a cor do botão é da função e
  é a mesma em toda tela; um tom antigo esquecido volta a pintar pelo estado.

Não substitui a conferência em tela: ela vê alinhamento, hierarquia e cor, que
nenhuma medição pega. Esta régua cobre o que é MEDÍVEL, para a conferência
humana não gastar rodada com o que uma consulta ao DOM responde.

Uso:
  python scripts/audit_regras_visuais.py                    # servidor em 127.0.0.1:8000
  python scripts/audit_regras_visuais.py --base-url ...     # outro endereço

Precisa do servidor no ar, do banco populado (`manage.py resetar_banco_demo`) e
de um usuário com vínculo de área. A senha vem de `SHOT_PASSWORD`, ou de
`--password-env`.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.navegador_medicao import abrir_chromium
from scripts.rotas_do_sistema import ROTAS
from playwright.sync_api import sync_playwright

TONS_VALIDOS = {"view","pdf","docx","attach","cancel","amend","delete","edit","neutral"}

SONDA = """() => {
  const util = el => {const cs=getComputedStyle(el);
    return el.getBoundingClientRect().width - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);};
  const real = el => {const r=document.createRange(); r.selectNodeContents(el);
    return r.getBoundingClientRect().width;};

  const faixa = document.querySelector('.rail__form');
  let linhas = 0;
  if (faixa) {
    const tops = new Set([...faixa.children].filter(c=>c.getBoundingClientRect().height>0)
                  .map(c=>Math.round(c.getBoundingClientRect().top)));
    linhas = tops.size;
  }
  const cortados = [...document.querySelectorAll('.fact__value')]
    .filter(v => real(v) > util(v) + 0.01)
    .map(v => v.textContent.trim().slice(0,28));
  const blocos = [...document.querySelectorAll('.record .form-block--v2')]
    .map(b => {const c=b.querySelector('.form-block__body');
      return c ? c.scrollHeight - Math.round(c.getBoundingClientRect().height) : 0;})
    .filter(x => x > 0);
  const tons = [...new Set([...document.querySelectorAll('.menu__icon[data-tone]')]
    .map(e => e.getAttribute('data-tone')))];
  return {linhas, cortados, blocos, tons};
}"""

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/")
    parser.add_argument("--username", default="revisor")
    parser.add_argument("--password-env", default="SHOT_PASSWORD")
    parser.add_argument("--max", type=int, default=0, help="teto de achados (catraca)")
    args = parser.parse_args()
    BASE = args.base_url
    senha = os.environ.get(args.password_env)
    if not senha:
        parser.error(f"defina {args.password_env} com a senha do usuário de medição")

    achados = []
    with sync_playwright() as pw:
        b = abrir_chromium(pw, headless=True)
        for tema in ("light", "dark"):
            ctx = b.new_context(viewport={"width":1440,"height":900}, color_scheme=tema)
            ctx.add_init_script("try{window.localStorage.setItem('theme',%r)}catch(e){}" % tema)
            p = ctx.new_page()
            p.goto(urljoin(BASE,"login/"), wait_until="domcontentloaded")
            p.locator('[name="username"]').fill(args.username)
            p.locator('[name="password"]').fill(senha)
            p.locator('button[type="submit"], input[type="submit"]').first.click()
            p.wait_for_load_state("networkidle")
            for rota in ROTAS:
                if not rota.requires_auth:
                    continue
                try:
                    resp = p.goto(urljoin(BASE, rota.path.lstrip("/")), wait_until="networkidle", timeout=25000)
                    p.wait_for_timeout(350)
                    if resp and resp.status != 200:
                        achados.append((tema, rota.slug, f"HTTP {resp.status}"))
                        continue
                    d = p.evaluate(SONDA)
                except Exception as erro:
                    achados.append((tema, rota.slug, f"erro: {str(erro)[:60]}"))
                    continue
                if d["linhas"] > 1:
                    achados.append((tema, rota.slug, f"faixa em {d['linhas']} linhas"))
                for t in d["cortados"]:
                    achados.append((tema, rota.slug, f"valor cortado: {t!r}"))
                for px in d["blocos"]:
                    achados.append((tema, rota.slug, f"bloco corta {px}px"))
                for tom in d["tons"]:
                    if tom not in TONS_VALIDOS:
                        achados.append((tema, rota.slug, f"tom fora do vocabulário: {tom!r}"))
            ctx.close()
        b.close()
    for tema, slug, o in achados:
        print(f"  [{tema}] {slug:34} {o}")
    print(f"\nRegras visuais violadas: {len(achados)} (teto {args.max})")
    return 1 if len(achados) > args.max else 0


if __name__ == "__main__":
    raise SystemExit(main())
