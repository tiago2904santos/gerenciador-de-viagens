#!/usr/bin/env python
"""Mede divergências não-cor entre claro e escuro no mesmo documento."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.rotas_do_sistema import ROTAS  # noqa: E402


DEFAULT_THRESHOLDS = ROOT / "scripts" / "tetos_front.json"
DEFAULT_VIEWPORTS = (1440, 800, 500)

COLOR_PROPERTIES = {
    "color",
    "background",
    "fill",
    "stroke",
    "flood-color",
    "lighting-color",
    "stop-color",
}


def is_color_property(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith("--") or lowered.endswith("color") or lowered in COLOR_PROPERTIES


def compare_snapshots(light: list[dict], dark: list[dict]) -> dict:
    if len(light) != len(dark):
        raise ValueError(f"DOM mudou entre temas: {len(light)} elementos no claro e {len(dark)} no escuro")
    differences: set[tuple[str, str, str, str]] = set()
    divergent_elements: set[str] = set()
    pairs: set[tuple[str, str, str]] = set()
    for light_item, dark_item in zip(light, dark, strict=True):
        if light_item["key"] != dark_item["key"]:
            raise ValueError("a ordem dos elementos mudou entre as capturas")
        key = light_item["key"]
        for prop, light_value in light_item["styles"].items():
            dark_value = dark_item["styles"].get(prop)
            if dark_value is None or light_value == dark_value:
                continue
            differences.add((key, prop, light_value, dark_value))
            divergent_elements.add(key)
            pairs.add((prop, light_value, dark_value))
    return {
        "elements_compared": len(light),
        "elements_divergent": len(divergent_elements),
        "differences": len(differences),
        "distinct_pairs": len(pairs),
        "difference_keys": differences,
    }


def order_exclusives(
    first: set[tuple[str, str, str, str]],
    reverse: set[tuple[str, str, str, str]],
) -> tuple[set, set]:
    return first - reverse, reverse - first


PAIR_SCRIPT = r"""
async ({firstTheme, secondTheme}) => {
  const root = document.documentElement;
  const isColor = (name) => {
    const p = name.toLowerCase();
    return p.startsWith('--') || p.endsWith('color') ||
      ['color', 'background', 'fill', 'stroke', 'flood-color', 'lighting-color', 'stop-color'].includes(p);
  };
  const settle = async () => {
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  };
  const apply = async (theme) => {
    root.setAttribute('data-theme', theme);
    try { localStorage.setItem('theme', theme); } catch (_) {}
    await settle();
  };
  await apply(firstTheme);
  const elements = Array.from(document.querySelectorAll('*'));
  const properties = Array.from(getComputedStyle(root)).filter((name) => !isColor(name));
  const first = elements.map((element) => {
    const style = getComputedStyle(element);
    return properties.map((name) => style.getPropertyValue(name));
  });
  await apply(secondTheme);
  const diffs = [];
  const divergent = new Set();
  const pairs = new Set();
  elements.forEach((element, index) => {
    const style = getComputedStyle(element);
    properties.forEach((property, propertyIndex) => {
      const before = first[index][propertyIndex];
      const after = style.getPropertyValue(property);
      if (before === after) return;
      const light = firstTheme === 'light' ? before : after;
      const dark = firstTheme === 'dark' ? before : after;
      const key = String(index);
      divergent.add(key);
      pairs.add(JSON.stringify([property, light, dark]));
      diffs.push([key, property, light, dark,
        element.id ? `${element.tagName.toLowerCase()}#${element.id}` :
          `${element.tagName.toLowerCase()}.${Array.from(element.classList).slice(0, 3).join('.')}`]);
    });
  });
  return {
    elementsCompared: elements.length,
    elementsDivergent: divergent.size,
    distinctPairs: pairs.size,
    diffs,
  };
}
"""


def _disable_motion(page) -> None:
    page.add_style_tag(
        content=(
            "*, *::before, *::after { transition-property: none !important; "
            "transition-duration: 0s !important; animation: none !important; }"
        )
    )


def _capture_order(page, first_theme: str, second_theme: str) -> dict:
    raw = page.evaluate(PAIR_SCRIPT, {"firstTheme": first_theme, "secondTheme": second_theme})
    keys = {(item[0], item[1], item[2], item[3]) for item in raw["diffs"]}
    return {
        "elements_compared": raw["elementsCompared"],
        "elements_divergent": raw["elementsDivergent"],
        "differences": len(raw["diffs"]),
        "distinct_pairs": raw["distinctPairs"],
        "difference_keys": keys,
        "diffs": raw["diffs"],
    }


def _summarize_pair(first: dict, reverse: dict) -> dict:
    only_first, only_reverse = order_exclusives(first["difference_keys"], reverse["difference_keys"])
    if only_first or only_reverse:
        raise RuntimeError(
            "a ordem de captura alterou o resultado: "
            f"{len(only_first)} exclusivos claro→escuro; "
            f"{len(only_reverse)} exclusivos escuro→claro"
        )
    pair_counts = Counter((item[1], item[2], item[3]) for item in first["diffs"])
    top_pairs = [
        {"property": prop, "light": light, "dark": dark, "elements": count}
        for (prop, light, dark), count in pair_counts.most_common(100)
    ]
    return {
        "elements_compared": first["elements_compared"],
        "elements_divergent": first["elements_divergent"],
        "differences": first["differences"],
        "distinct_pairs": first["distinct_pairs"],
        "order_exclusive_light_dark": 0,
        "order_exclusive_dark_light": 0,
        "top_pairs": top_pairs,
    }


def _login(page, base_url: str, username: str, password: str, timeout_ms: int) -> None:
    page.goto(urljoin(base_url, "login/"), wait_until="domcontentloaded", timeout=timeout_ms)
    page.locator('[name="username"]').fill(username)
    page.locator('[name="password"]').fill(password)
    page.locator('button[type="submit"], input[type="submit"]').first.click()
    page.wait_for_load_state("networkidle", timeout=timeout_ms)
    if urlparse(page.url).path.rstrip("/") == "/login":
        raise RuntimeError("a autenticação do usuário de medição foi recusada")


def _measure_route(page, route, base_url: str, timeout_ms: int) -> dict:
    response = page.goto(urljoin(base_url, route.path.lstrip("/")), wait_until="networkidle", timeout=timeout_ms)
    if response is None or response.status >= 400:
        status = response.status if response else "sem resposta"
        raise RuntimeError(f"{route.slug}: HTTP {status} em {route.path}")
    if urlparse(page.url).path.rstrip("/") != route.path.rstrip("/"):
        raise RuntimeError(f"{route.slug}: {route.path} redirecionou para {page.url}")
    _disable_motion(page)
    first = _capture_order(page, "light", "dark")
    reverse = _capture_order(page, "dark", "light")
    return _summarize_pair(first, reverse)


def _parse_viewports(value: str) -> tuple[int, ...]:
    widths = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not widths or any(width <= 0 for width in widths):
        raise argparse.ArgumentTypeError("use larguras positivas separadas por vírgula")
    return widths


def updated_ceilings(old: dict[str, dict], measured: dict[str, dict], *, allow_weaker: bool = False) -> dict:
    result: dict[str, dict] = {}
    for key, data in measured.items():
        current = int(data["differences"])
        previous = old.get(key, {}).get("differences_max")
        ceiling = current if previous is None or allow_weaker else min(int(previous), current)
        result[key] = {"differences_max": ceiling}
    return result


def evaluate_ceilings(measured: dict[str, dict], ceilings: dict[str, dict]) -> list[str]:
    regressions: list[str] = []
    for key, threshold in sorted(ceilings.items()):
        if key not in measured:
            regressions.append(f"{key}: combinação rota/viewport não foi medida")
            continue
        actual = int(measured[key]["differences"])
        maximum = int(threshold["differences_max"])
        if actual > maximum:
            regressions.append(f"{key}: {actual} diferenças > teto {maximum}")
    return regressions


def _read_thresholds(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 1}
    return json.loads(path.read_text(encoding="utf-8"))


def run_measurement(args) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "Playwright não instalado. Instale requirements/test.txt e rode "
            "`python -m playwright install chromium`."
        ) from exc

    username = args.username or os.environ.get("FRONT_METRICS_USERNAME")
    password = os.environ.get(args.password_env)
    if not args.storage_state and (not username or not password):
        raise SystemExit(
            "As 42 rotas protegidas exigem autenticação. Defina FRONT_METRICS_USERNAME e "
            f"{args.password_env}, ou forneça --storage-state; não é permitido medir só a rota pública."
        )

    results: dict[str, dict] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headful)
        for width in args.viewports:
            context = browser.new_context(
                viewport={"width": width, "height": args.viewport_height},
                storage_state=args.storage_state,
            )
            page = context.new_page()
            public = [route for route in ROTAS if not route.requires_auth]
            protected = [route for route in ROTAS if route.requires_auth]
            for route in public:
                key = f"{route.slug}@{width}"
                results[key] = _measure_route(page, route, args.base_url, args.timeout_ms)
            if not args.storage_state:
                _login(page, args.base_url, username, password, args.timeout_ms)
            for route in protected:
                key = f"{route.slug}@{width}"
                results[key] = _measure_route(page, route, args.base_url, args.timeout_ms)
                print(
                    f"{key}: {results[key]['differences']} diferenças em "
                    f"{results[key]['elements_divergent']}/{results[key]['elements_compared']} elementos"
                )
            context.close()
        browser.close()

    return {
        "metric": "non_color_theme_divergence",
        "direction": "down",
        "route_count": len(ROTAS),
        "viewports": list(args.viewports),
        "measurement_count": len(results),
        "summary": {
            "elements_compared": sum(item["elements_compared"] for item in results.values()),
            "elements_divergent": sum(item["elements_divergent"] for item in results.values()),
            "differences": sum(item["differences"] for item in results.values()),
            "distinct_pairs": len(
                {
                    (pair["property"], pair["light"], pair["dark"])
                    for item in results.values()
                    for pair in item["top_pairs"]
                }
            ),
        },
        "routes": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("FRONT_METRICS_BASE_URL", "http://127.0.0.1:8000/"))
    parser.add_argument("--username")
    parser.add_argument("--password-env", default="FRONT_METRICS_PASSWORD")
    parser.add_argument("--storage-state", type=Path)
    parser.add_argument("--headful", action="store_true")
    parser.add_argument("--viewports", type=_parse_viewports, default=DEFAULT_VIEWPORTS)
    parser.add_argument("--viewport-height", type=int, default=900)
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--atualizar-tetos", action="store_true")
    parser.add_argument("--permitir-subir-teto", action="store_true", help="permite enfraquecer um teto existente")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    report = run_measurement(args)
    expected = len(ROTAS) * len(args.viewports)
    if report["measurement_count"] != expected:
        print(f"ERRO: foram feitas {report['measurement_count']} de {expected} medições.")
        return 1
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    thresholds = _read_thresholds(args.thresholds)
    current = thresholds.get("theme_divergence", {}).get("routes", {})
    measured = report["routes"]
    if args.atualizar_tetos:
        thresholds["theme_divergence"] = {
            "direction": "down",
            "routes": updated_ceilings(current, measured, allow_weaker=args.permitir_subir_teto),
        }
        args.thresholds.write_text(json.dumps(thresholds, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Tetos regravados em {args.thresholds}")

    ceilings = thresholds.get("theme_divergence", {}).get("routes", {})
    regressions = evaluate_ceilings(measured, ceilings)
    if regressions:
        print("\nERRO: regressão de divergência entre temas:")
        for regression in regressions:
            print(f"- {regression}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
