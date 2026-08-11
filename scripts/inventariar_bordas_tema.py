#!/usr/bin/env python
"""Atribui divergências de borda às regras CSS predicadas no tema escuro (NOVO-93)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urljoin


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.medir_css_por_rota import is_valid_final_url  # noqa: E402
from scripts.medir_divergencia_tema import (  # noqa: E402
    _disable_motion,
    _esperar_layout_estavel,
    _login,
)
from scripts.navegador_medicao import abrir_chromium  # noqa: E402
from scripts.rotas_do_sistema import ROTAS  # noqa: E402


DEFAULT_VIEWPORTS = (1440, 800, 500)


INVENTORY_SCRIPT = r"""
async ({reveal}) => {
  const root = document.documentElement;
  const physical = [
    'border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width',
    'border-top-style', 'border-right-style', 'border-bottom-style', 'border-left-style',
  ];
  const isDark = (selector) => selector.includes('[data-theme="dark"]');
  const splitSelectors = (selectorText) => {
    const result = [];
    let start = 0;
    let paren = 0;
    let bracket = 0;
    let quote = '';
    for (let i = 0; i < selectorText.length; i += 1) {
      const char = selectorText[i];
      if (quote) {
        if (char === quote && selectorText[i - 1] !== '\\') quote = '';
        continue;
      }
      if (char === '"' || char === "'") { quote = char; continue; }
      if (char === '(') paren += 1;
      else if (char === ')') paren -= 1;
      else if (char === '[') bracket += 1;
      else if (char === ']') bracket -= 1;
      else if (char === ',' && paren === 0 && bracket === 0) {
        result.push(selectorText.slice(start, i).trim());
        start = i + 1;
      }
    }
    result.push(selectorText.slice(start).trim());
    return result.filter(Boolean);
  };
  const borderDeclarations = (style) => {
    const declarations = [];
    for (const property of style) {
      const lowered = property.toLowerCase();
      if (!lowered.startsWith('border')) continue;
      if (lowered.includes('color') || lowered.includes('radius') || lowered.includes('image')) continue;
      declarations.push([property, style.getPropertyValue(property), style.getPropertyPriority(property)]);
    }
    return declarations;
  };
  const rules = [];
  const seen = new Set();
  const walk = (ruleList, href, active) => {
    if (!ruleList) return;
    for (const rule of ruleList) {
      if (rule.type === CSSRule.MEDIA_RULE) {
        walk(rule.cssRules, href, active && matchMedia(rule.conditionText).matches);
        continue;
      }
      if (rule.cssRules && rule.type !== CSSRule.STYLE_RULE) {
        walk(rule.cssRules, href, active);
        continue;
      }
      if (!active || rule.type !== CSSRule.STYLE_RULE || !isDark(rule.selectorText)) continue;
      const declarations = borderDeclarations(rule.style);
      if (!declarations.length) continue;
      const selectors = splitSelectors(rule.selectorText).filter(isDark);
      for (const selector of selectors) {
        const cssText = rule.style.cssText;
        const key = JSON.stringify([selector, cssText]);
        if (seen.has(key)) continue;
        seen.add(key);
        rules.push({selector, declarations, cssText, href: href || ''});
      }
    }
  };
  for (const sheet of document.styleSheets) {
    try { walk(sheet.cssRules, sheet.href, true); } catch (_) {}
  }
  if (reveal) {
    document.querySelectorAll('[hidden]').forEach((element) => { element.hidden = false; });
    document.querySelectorAll('[aria-hidden="true"]').forEach((element) => {
      if (element.matches('[role="dialog"], [role="menu"], .dropdown-menu, .cv-dialog')) {
        element.setAttribute('aria-hidden', 'false');
      }
    });
  }
  const settle = async () => {
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    await new Promise((resolve) => setTimeout(resolve, 100));
  };
  root.setAttribute('data-theme', 'dark');
  await settle();
  const captures = [];
  for (const rule of rules) {
    let elements = [];
    try { elements = Array.from(document.querySelectorAll(rule.selector)); } catch (_) {}
    if (!elements.length) continue;
    captures.push({
      ...rule,
      elements,
      dark: elements.map((element) => {
        const style = getComputedStyle(element);
        return physical.map((property) => style.getPropertyValue(property));
      }),
    });
  }
  root.setAttribute('data-theme', 'light');
  await settle();
  return captures.map((capture) => {
    let affected = 0;
    const examples = [];
    capture.elements.forEach((element, index) => {
      const style = getComputedStyle(element);
      const light = physical.map((property) => style.getPropertyValue(property));
      const dark = capture.dark[index];
      if (light.every((value, propertyIndex) => value === dark[propertyIndex])) return;
      affected += 1;
      if (examples.length < 5) {
        examples.push({
          element: element.id ? `${element.tagName.toLowerCase()}#${element.id}` :
            `${element.tagName.toLowerCase()}.${Array.from(element.classList).slice(0, 4).join('.')}`,
          light,
          dark,
        });
      }
    });
    return {
      selector: capture.selector,
      declarations: capture.declarations,
      cssText: capture.cssText,
      href: capture.href,
      matched: capture.elements.length,
      affected,
      examples,
    };
  }).filter((item) => item.affected > 0);
}
"""


def parse_viewports(value: str) -> tuple[int, ...]:
    widths = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not widths or any(width <= 0 for width in widths):
        raise argparse.ArgumentTypeError("use larguras positivas separadas por vírgula")
    return widths


def split_selectors(selector_text: str) -> list[str]:
    result: list[str] = []
    start = 0
    paren = 0
    bracket = 0
    quote = ""
    for index, char in enumerate(selector_text):
        if quote:
            if char == quote and selector_text[index - 1 : index] != "\\":
                quote = ""
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "(":
            paren += 1
        elif char == ")":
            paren -= 1
        elif char == "[":
            bracket += 1
        elif char == "]":
            bracket -= 1
        elif char == "," and paren == 0 and bracket == 0:
            result.append(selector_text[start:index].strip())
            start = index + 1
    result.append(selector_text[start:].strip())
    return [item for item in result if item]


def normalize_selector(selector: str) -> str:
    selector = re.sub(r"\s+", " ", selector.strip())
    selector = re.sub(r"\s*,\s*", ",", selector)
    selector = re.sub(r"\s*([>+~])\s*", r"\1", selector)
    return selector


def source_index() -> dict[str, list[dict]]:
    import tinycss2

    index: dict[str, list[dict]] = defaultdict(list)

    def visit(nodes, relative_path: str) -> None:
        for node in nodes:
            if node.type == "qualified-rule":
                selector_text = tinycss2.serialize(node.prelude).strip()
                for selector in split_selectors(selector_text):
                    index[normalize_selector(selector)].append(
                        {"path": relative_path, "line": node.source_line}
                    )
            elif node.type == "at-rule" and node.content is not None:
                visit(tinycss2.parse_rule_list(node.content), relative_path)

    css_root = ROOT / "static" / "css"
    for path in sorted(css_root.rglob("*.css")):
        if path.name == "shell.bundle.css":
            continue
        visit(
            tinycss2.parse_stylesheet(path.read_text(encoding="utf-8")),
            path.relative_to(ROOT).as_posix(),
        )
    return index


def rule_key(item: dict) -> str:
    return json.dumps(
        [item["selector"], item.get("cssText", item["declarations"])],
        ensure_ascii=False,
        sort_keys=True,
    )


def rule_removes_border(item: dict) -> bool:
    """Diz se a regra escura zera ao menos um lado que existe no tema claro."""
    for example in item.get("examples", []):
        for light, dark in zip(example["light"][:4], example["dark"][:4], strict=True):
            if light != "0px" and dark == "0px":
                return True
    return False


def run(args) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("Playwright não instalado") from exc

    password = os.environ.get(args.password_env)
    if not args.username or not password:
        raise SystemExit(f"informe --username e {args.password_env}")

    aggregate: dict[str, dict] = {}
    occurrences: dict[str, list[dict]] = defaultdict(list)
    with sync_playwright() as playwright:
        browser = abrir_chromium(playwright, headless=not args.headful)
        for width in args.viewports:
            context = browser.new_context(viewport={"width": width, "height": args.viewport_height})
            page = context.new_page()
            public = [route for route in ROTAS if not route.requires_auth]
            protected = [route for route in ROTAS if route.requires_auth]
            for route in public + protected:
                if route.requires_auth and route is protected[0]:
                    _login(page, args.base_url, args.username, password, args.timeout_ms)
                response = page.goto(
                    urljoin(args.base_url, route.path.lstrip("/")),
                    wait_until="networkidle",
                    timeout=args.timeout_ms,
                )
                status = response.status if response else None
                if status != 200 or not is_valid_final_url(
                    page.url,
                    route.path,
                    args.base_url,
                    requires_auth=route.requires_auth,
                ):
                    raise RuntimeError(f"{route.slug}: HTTP {status}; URL final {page.url}")
                _disable_motion(page)
                stable = _esperar_layout_estavel(page)
                if not stable["estavel"]:
                    raise RuntimeError(f"{route.slug}@{width}: layout instável")
                measured = page.evaluate(INVENTORY_SCRIPT, {"reveal": args.reveal})
                for item in measured:
                    key = rule_key(item)
                    aggregate.setdefault(
                        key,
                        {
                            "selector": item["selector"],
                            "declarations": item["declarations"],
                            "cssText": item["cssText"],
                            "hrefs": set(),
                            "affected": 0,
                            "matched": 0,
                            "examples": [],
                        },
                    )
                    target = aggregate[key]
                    target["hrefs"].add(item["href"])
                    target["affected"] += item["affected"]
                    target["matched"] += item["matched"]
                    target["examples"].extend(item["examples"][: max(0, 5 - len(target["examples"]))])
                    occurrences[key].append(
                        {"route": route.slug, "width": width, "affected": item["affected"]}
                    )
                print(f"{route.slug}@{width}: {len(measured)} regra(s) de borda com efeito")
            context.close()
        browser.close()

    locations = source_index()
    rules = []
    for key, item in aggregate.items():
        rules.append(
            {
                **item,
                "hrefs": sorted(item["hrefs"]),
                "source_locations": locations.get(normalize_selector(item["selector"]), []),
                "occurrences": occurrences[key],
            }
        )
    rules.sort(key=lambda item: (-item["affected"], item["selector"]))
    removal_rules = [item for item in rules if rule_removes_border(item)]
    return {
        "metric": "dark_border_rules_with_computed_effect",
        "viewports": list(args.viewports),
        "route_count": len(ROTAS),
        "rule_count": len(rules),
        "border_removal_rule_count": len(removal_rules),
        "rules": rules,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password-env", default="FRONT_METRICS_PASSWORD")
    parser.add_argument("--viewports", type=parse_viewports, default=DEFAULT_VIEWPORTS)
    parser.add_argument("--viewport-height", type=int, default=900)
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    parser.add_argument("--reveal", action="store_true")
    parser.add_argument("--headful", action="store_true")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    report = run(args)
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Regras escuras de borda com efeito computado: {report['rule_count']}")
    print(f"Regras escuras que removem borda do tema claro: {report['border_removal_rule_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
