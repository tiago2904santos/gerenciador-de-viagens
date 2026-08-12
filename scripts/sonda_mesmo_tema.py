#!/usr/bin/env python
"""Compara o mesmo tema entre duas versoes do frontend (NOVO-114).

A regua de divergencia compara claro e escuro no mesmo codigo. Esta sonda faz
o eixo ortogonal exigido pela E9: compara o mesmo tema, rota, largura e estado
em duas versoes servidas ao mesmo tempo. Um resultado com zero diferencas de
estilo prova que o diff exercitado nao alterou a cascata observavel no corpus.

As duas ordens de captura sao executadas. Uma diferenca que aparece apenas em
uma ordem torna a combinacao irreprodutivel e reprova a medicao. Mudancas de
texto direto sao marcadas no diagnostico, mas nunca retiram uma diferenca de
estilo da catraca: correlacao com relogio ou contador nao prova causalidade.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.medir_css_por_rota import is_valid_final_url  # noqa: E402
from scripts.navegador_medicao import abrir_chromium  # noqa: E402
from scripts.rotas_do_sistema import ROTAS  # noqa: E402


DEFAULT_VIEWPORTS = (1440, 800, 500)
PSEUDOS = ("::before", "::after", "::placeholder")
IGNORED_PROPERTIES = {
    "animation",
    "animation-delay",
    "animation-direction",
    "animation-duration",
    "animation-fill-mode",
    "animation-iteration-count",
    "animation-name",
    "animation-play-state",
    "animation-timing-function",
    "caret-color",
    "transition",
    "transition-delay",
    "transition-duration",
    "transition-property",
    "transition-timing-function",
}

CSS_STABLE = """
*, *::before, *::after {
  animation: none !important;
  transition-property: none !important;
  transition-duration: 0s !important;
}
"""

CSS_REVEAL = """
[hidden] { display: revert !important; }
[aria-hidden="true"] { visibility: visible !important; }
"""

SETTLE_SCRIPT = r"""
async ({attempts, intervalMs}) => {
  const measure = () => {
    const root = document.documentElement;
    return `${root.scrollHeight}x${root.scrollWidth}x${document.body.scrollHeight}x${document.getElementsByTagName('*').length}`;
  };
  let previous = measure();
  let equal = 0;
  for (let index = 0; index < attempts; index += 1) {
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
    const current = measure();
    if (current === previous) {
      equal += 1;
      if (equal >= 3) return {stable: true, rounds: index + 1, measure: current};
    } else {
      equal = 0;
      previous = current;
    }
  }
  return {stable: false, rounds: attempts, measure: previous};
}
"""

SNAPSHOT_SCRIPT = r"""
({ignored, pseudos}) => {
  const ignoredSet = new Set(ignored);
  const properties = Array.from(getComputedStyle(document.documentElement))
    .filter((name) => !name.startsWith('--') && !ignoredSet.has(name));
  const pathFor = (element) => {
    const parts = [];
    let current = element;
    while (current && current.nodeType === Node.ELEMENT_NODE) {
      let index = 1;
      let sibling = current.previousElementSibling;
      while (sibling) {
        if (sibling.tagName === current.tagName) index += 1;
        sibling = sibling.previousElementSibling;
      }
      parts.push(`${current.tagName.toLowerCase()}:nth-of-type(${index})`);
      current = current.parentElement;
    }
    return parts.reverse().join('>');
  };
  const directText = (element) => {
    const own = Array.from(element.childNodes)
      .filter((node) => node.nodeType === Node.TEXT_NODE)
      .map((node) => node.textContent || '')
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim();
    const value = 'value' in element ? String(element.value || '') : '';
    return `${own}\u0000${value}`;
  };
  const collectStyle = (element, pseudo = null) => {
    const computed = getComputedStyle(element, pseudo);
    const values = {};
    properties.forEach((name) => { values[name] = computed.getPropertyValue(name); });
    return values;
  };
  return Array.from(document.querySelectorAll('*')).map((element) => {
    const pseudoStyles = {};
    pseudos.forEach((pseudo) => {
      if (pseudo === '::placeholder' && !element.matches('input, textarea')) return;
      const computed = getComputedStyle(element, pseudo);
      if (pseudo !== '::placeholder' && ['none', 'normal', ''].includes(computed.content)) return;
      pseudoStyles[pseudo] = collectStyle(element, pseudo);
    });
    return {
      key: pathFor(element),
      label: element.id ? `${element.tagName.toLowerCase()}#${element.id}` :
        `${element.tagName.toLowerCase()}.${Array.from(element.classList).slice(0, 3).join('.')}`,
      text: directText(element),
      styles: collectStyle(element),
      pseudos: pseudoStyles,
    };
  });
}
"""


@dataclass(frozen=True)
class Route:
    slug: str
    path: str
    requires_auth: bool = True


def parse_viewports(value: str) -> tuple[int, ...]:
    widths = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not widths or any(width <= 0 for width in widths):
        raise argparse.ArgumentTypeError("use larguras positivas separadas por virgula")
    return widths


def load_routes(path: Path | None) -> list[Route]:
    if path is None:
        return [Route(item.slug, item.path, item.requires_auth) for item in ROTAS]
    raw = json.loads(path.read_text(encoding="utf-8"))
    routes: list[Route] = []
    for index, item in enumerate(raw):
        if isinstance(item, str):
            routes.append(Route(item, item, True))
            continue
        routes.append(
            Route(
                str(item.get("slug") or item["path"] or index),
                str(item["path"]),
                bool(item.get("requires_auth", True)),
            )
        )
    if not routes:
        raise SystemExit("o corpus de rotas nao pode ser vazio")
    return routes


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def normalize_snapshot(items: list[dict]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for item in items:
        result[item["key"]] = {
            "label": item["label"],
            "text_hash": text_hash(item.get("text", "")),
            "styles": item["styles"],
            "pseudos": item.get("pseudos", {}),
        }
    return result


def _style_differences(first: dict, second: dict) -> list[tuple[str, str, str, str]]:
    differences: list[tuple[str, str, str, str]] = []
    names = set(first) | set(second)
    for name in sorted(names):
        before = first.get(name, "")
        after = second.get(name, "")
        if before != after:
            differences.append(("element", name, before, after))
    return differences


def compare_snapshots(before: dict[str, dict], after: dict[str, dict]) -> dict:
    before_keys = set(before)
    after_keys = set(after)
    missing_before = sorted(after_keys - before_keys)
    missing_after = sorted(before_keys - after_keys)
    style_differences: set[tuple[str, str, str, str, str]] = set()
    text_correlated_style_differences: set[tuple[str, str, str, str, str]] = set()
    text_changes: set[str] = set()
    divergent_elements: set[str] = set()

    for key in sorted(before_keys & after_keys):
        first = before[key]
        second = after[key]
        text_changed = first["text_hash"] != second["text_hash"]
        if text_changed:
            text_changes.add(key)
        differences = _style_differences(first["styles"], second["styles"])
        pseudo_names = set(first["pseudos"]) | set(second["pseudos"])
        for pseudo in sorted(pseudo_names):
            for _, prop, old, new in _style_differences(
                first["pseudos"].get(pseudo, {}), second["pseudos"].get(pseudo, {})
            ):
                differences.append((pseudo, prop, old, new))
        for scope, prop, old, new in differences:
            difference = (key, scope, prop, old, new)
            style_differences.add(difference)
            if text_changed:
                text_correlated_style_differences.add(difference)
            divergent_elements.add(key)

    property_counts = Counter(item[2] for item in style_differences)
    return {
        "elements_before": len(before),
        "elements_after": len(after),
        "missing_before": missing_before,
        "missing_after": missing_after,
        "structural_differences": len(missing_before) + len(missing_after),
        "style_differences": len(style_differences),
        "text_correlated_style_differences": len(text_correlated_style_differences),
        "text_changes": len(text_changes),
        "divergent_elements": len(divergent_elements),
        "difference_keys": style_differences,
        "text_correlated_difference_keys": text_correlated_style_differences,
        "text_change_keys": text_changes,
        "top_properties": property_counts.most_common(30),
        "examples": [
            {"key": key, "scope": scope, "property": prop, "before": old, "after": new}
            for key, scope, prop, old, new in sorted(style_differences)[:100]
        ],
    }


def order_exclusives(first: set, reverse: set) -> tuple[set, set]:
    return first - reverse, reverse - first


def reproducibility_keys(result: dict) -> set[tuple]:
    """Representa tudo que pode mudar o veredito ou explicar a medicao."""
    keys = set(result["difference_keys"])
    keys.update(("missing-before", key) for key in result["missing_before"])
    keys.update(("missing-after", key) for key in result["missing_after"])
    keys.update(("text-change", key) for key in result["text_change_keys"])
    keys.update(
        ("text-correlated", *difference)
        for difference in result["text_correlated_difference_keys"]
    )
    return keys


def _disable_motion(page, reveal: bool) -> None:
    page.add_style_tag(content=CSS_STABLE)
    if reveal:
        page.add_style_tag(content=CSS_REVEAL)
        page.evaluate(
            """() => {
              document.querySelectorAll('[hidden]').forEach((el) => el.removeAttribute('hidden'));
              document.querySelectorAll('[aria-hidden="true"]').forEach((el) => el.setAttribute('aria-hidden', 'false'));
              document.querySelectorAll('details').forEach((el) => { el.open = true; });
            }"""
        )


def _force_pseudos(context, page, pseudos: tuple[str, ...]) -> None:
    if not pseudos:
        return
    cdp = context.new_cdp_session(page)
    cdp.send("DOM.enable")
    cdp.send("CSS.enable")
    root = cdp.send("DOM.getDocument")["root"]["nodeId"]
    node_ids = cdp.send("DOM.querySelectorAll", {"nodeId": root, "selector": "*"})["nodeIds"]
    for node_id in node_ids:
        cdp.send("CSS.forcePseudoState", {"nodeId": node_id, "forcedPseudoClasses": list(pseudos)})


def _login(page, base_url: str, username: str, password: str, timeout_ms: int) -> None:
    page.goto(urljoin(base_url, "login/"), wait_until="domcontentloaded", timeout=timeout_ms)
    page.locator('[name="username"]').fill(username)
    page.locator('[name="password"]').fill(password)
    page.locator('button[type="submit"], input[type="submit"]').first.click()
    page.wait_for_load_state("networkidle", timeout=timeout_ms)
    if "/login" in page.url:
        raise RuntimeError(f"autenticacao recusada em {base_url}")


def _prime_theme(page, base_url: str, theme: str, timeout_ms: int) -> None:
    """Grava o tema antes da rota para que o bootstrap JS ja nasca nele."""
    expected_origin = urljoin(base_url, "/").rstrip("/")
    if not page.url.startswith(expected_origin):
        page.goto(urljoin(base_url, "login/"), wait_until="domcontentloaded", timeout=timeout_ms)
    page.evaluate(
        "theme => { localStorage.setItem('theme', theme); "
        "document.documentElement.setAttribute('data-theme', theme); }",
        theme,
    )


def _load_route(page, route: Route, base_url: str, timeout_ms: int) -> None:
    response = page.goto(
        urljoin(base_url, route.path.lstrip("/")),
        wait_until="networkidle",
        timeout=timeout_ms,
    )
    if response is None or response.status >= 400:
        status = response.status if response else "sem resposta"
        raise RuntimeError(f"{route.slug}: HTTP {status} em {base_url}{route.path}")
    if not is_valid_final_url(page.url, route.path, base_url, requires_auth=route.requires_auth):
        raise RuntimeError(f"{route.slug}: URL final invalida em {base_url}: {page.url}")


def _capture(context, page, route, base_url, theme, pseudos, reveal, timeout_ms) -> dict[str, dict]:
    _prime_theme(page, base_url, theme, timeout_ms)
    _load_route(page, route, base_url, timeout_ms)
    _disable_motion(page, reveal)
    actual_theme = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
    if actual_theme != theme:
        raise RuntimeError(
            f"{route.slug}: tema esperado {theme!r}, pagina iniciou em {actual_theme!r}"
        )
    settled = page.evaluate(SETTLE_SCRIPT, {"attempts": 40, "intervalMs": 50})
    if not settled["stable"]:
        raise RuntimeError(f"{route.slug}: layout nao estabilizou em {base_url} ({settled['measure']})")
    _force_pseudos(context, page, pseudos)
    return normalize_snapshot(page.evaluate(SNAPSHOT_SCRIPT, {"ignored": sorted(IGNORED_PROPERTIES), "pseudos": PSEUDOS}))


def route_groups(routes: list[Route]) -> tuple[list[Route], list[Route]]:
    return (
        [item for item in routes if not item.requires_auth],
        [item for item in routes if item.requires_auth],
    )


def _measure_route_set(browser, args, width, routes, results, *, authenticated: bool) -> None:
    if not routes:
        return
    storage_state = args.storage_state if authenticated else None
    before_context = browser.new_context(
        viewport={"width": width, "height": args.viewport_height},
        storage_state=storage_state,
    )
    after_context = browser.new_context(
        viewport={"width": width, "height": args.viewport_height},
        storage_state=storage_state,
    )
    try:
        before_page = before_context.new_page()
        after_page = after_context.new_page()
        if authenticated and not args.storage_state:
            username = args.username or os.environ.get("FRONT_METRICS_USERNAME")
            password = os.environ.get(args.password_env)
            _login(before_page, args.before_url, username, password, args.timeout_ms)
            _login(after_page, args.after_url, username, password, args.timeout_ms)

        for route in routes:
            for theme in args.themes:
                key = f"{route.slug}@{width}@{theme}"
                before_first = _capture(
                    before_context, before_page, route, args.before_url, theme,
                    args.pseudo, args.reveal, args.timeout_ms,
                )
                after_second = _capture(
                    after_context, after_page, route, args.after_url, theme,
                    args.pseudo, args.reveal, args.timeout_ms,
                )
                first = compare_snapshots(before_first, after_second)

                after_first = _capture(
                    after_context, after_page, route, args.after_url, theme,
                    args.pseudo, args.reveal, args.timeout_ms,
                )
                before_second = _capture(
                    before_context, before_page, route, args.before_url, theme,
                    args.pseudo, args.reveal, args.timeout_ms,
                )
                reverse = compare_snapshots(before_second, after_first)
                only_first, only_reverse = order_exclusives(
                    reproducibility_keys(first), reproducibility_keys(reverse)
                )
                if only_first or only_reverse:
                    raise RuntimeError(
                        f"{key}: ordem alterou o resultado: {len(only_first)} exclusivos "
                        f"antes->depois e {len(only_reverse)} exclusivos depois->antes"
                    )
                first.pop("difference_keys")
                first.pop("text_correlated_difference_keys")
                first.pop("text_change_keys")
                results[key] = first
                print(
                    f"{key}: {first['style_differences']} estilo; "
                    f"{first['structural_differences']} estrutura; "
                    f"{first['text_correlated_style_differences']} correlacionadas a texto"
                )
    finally:
        before_context.close()
        after_context.close()


def run_measurement(args) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("Playwright nao instalado; instale requirements/test.txt.") from exc

    username = args.username or os.environ.get("FRONT_METRICS_USERNAME")
    password = os.environ.get(args.password_env)
    routes = load_routes(args.routes_json)
    if any(route.requires_auth for route in routes) and not args.storage_state and (not username or not password):
        raise SystemExit(
            "rotas protegidas exigem FRONT_METRICS_USERNAME e a variavel indicada em "
            f"--password-env ({args.password_env}), ou --storage-state"
        )

    results: dict[str, dict] = {}
    with sync_playwright() as playwright:
        browser = abrir_chromium(playwright, headless=not args.headful)
        for width in args.viewports:
            public_routes, protected_routes = route_groups(routes)
            _measure_route_set(
                browser, args, width, public_routes, results, authenticated=False
            )
            _measure_route_set(
                browser, args, width, protected_routes, results, authenticated=True
            )
        browser.close()

    summary = {
        "measurements": len(results),
        "style_differences": sum(item["style_differences"] for item in results.values()),
        "structural_differences": sum(item["structural_differences"] for item in results.values()),
        "text_correlated_style_differences": sum(
            item["text_correlated_style_differences"] for item in results.values()
        ),
        "text_changes": sum(item["text_changes"] for item in results.values()),
    }
    return {
        "metric": "same_theme_between_versions",
        "before_url": args.before_url,
        "after_url": args.after_url,
        "route_count": len(routes),
        "viewports": list(args.viewports),
        "themes": list(args.themes),
        "pseudo": list(args.pseudo),
        "reveal": args.reveal,
        "summary": summary,
        "routes": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-url", required=True)
    parser.add_argument("--after-url", required=True)
    parser.add_argument("--username")
    parser.add_argument("--password-env", default="FRONT_METRICS_PASSWORD")
    parser.add_argument("--storage-state", type=Path)
    parser.add_argument("--routes-json", type=Path)
    parser.add_argument("--viewports", type=parse_viewports, default=DEFAULT_VIEWPORTS)
    parser.add_argument("--viewport-height", type=int, default=900)
    parser.add_argument("--themes", type=lambda value: tuple(value.split(",")), default=("light", "dark"))
    parser.add_argument("--pseudo", action="append", choices=("hover", "focus", "focus-visible", "active"), default=[])
    parser.add_argument("--reveal", "--revelar", dest="reveal", action="store_true")
    parser.add_argument("--headful", action="store_true")
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    parser.add_argument("--max-style-differences", type=int, default=0)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    report = run_measurement(args)
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = report["summary"]
    failures = report_failures(report, args.max_style_differences)
    if failures:
        print("ERRO: " + "; ".join(failures))
        return 1
    print(
        "OK: "
        f"{summary['measurements']} medicoes, {summary['style_differences']} diferencas de estilo, "
        f"{summary['structural_differences']} estruturais"
    )
    return 0


def report_failures(report: dict, max_style_differences: int) -> list[str]:
    summary = report["summary"]
    expected = report["route_count"] * len(report["viewports"]) * len(report["themes"])
    failures: list[str] = []
    if summary["measurements"] != expected:
        failures.append(f"{summary['measurements']} de {expected} medicoes")
    if summary["structural_differences"]:
        failures.append(f"{summary['structural_differences']} diferencas estruturais")
    if summary["style_differences"] > max_style_differences:
        failures.append(
            f"{summary['style_differences']} diferencas de estilo > teto {max_style_differences}"
        )
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
