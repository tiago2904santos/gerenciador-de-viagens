#!/usr/bin/env python
"""Reprova violações WCAG detectáveis pelo axe nas 43 rotas reais (QA-12).

O gate reutiliza o corpus, o usuário e o Chromium das métricas de frontend. A
rota pública é medida antes da autenticação; depois o mesmo contexto visita as
rotas protegidas. Cada rota é conferida em claro e escuro porque contraste é
parte do contrato, não apenas a semântica do HTML.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urljoin

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from scripts.medir_css_por_rota import is_valid_final_url  # noqa: E402
from scripts.navegador_medicao import abrir_chromium  # noqa: E402
from scripts.rotas_do_sistema import ROTAS  # noqa: E402

THEMES = ("light", "dark")
AXE_TAGS = ("wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa")
# Regras centrais explicitadas no contrato; axe executa todas as regras dos tags acima.
AXE_RULES = ("color-contrast", "image-alt", "label", "aria-valid-attr-value")
DEFAULT_BASELINE = RAIZ / "scripts/accessibility-baseline.json"


def summarize_violations(route: str, theme: str, violations: list[dict]) -> list[dict]:
    """Reduz o resultado verboso do axe sem perder o seletor que permite corrigir."""
    summary = []
    for violation in violations:
        targets = []
        details = []
        for node in violation.get("nodes", []):
            target = node.get("target", [])
            rendered = " > ".join(str(part) for part in target)
            if rendered and rendered not in targets:
                targets.append(rendered)
            details.append(
                {
                    "target": rendered,
                    "html": node.get("html", ""),
                    "failure": node.get("failureSummary", ""),
                }
            )
        summary.append(
            {
                "route": route,
                "theme": theme,
                "rule": violation["id"],
                "impact": violation.get("impact"),
                "nodes": len(violation.get("nodes", [])),
                "targets": targets[:10],
                "details": details[:10],
            }
        )
    return summary


def violation_keys(findings: list[dict]) -> set[tuple[str, str, str, str]]:
    """Identidade estável da dívida: rota, tema, regra e alvo DOM."""
    return {
        (item["route"], item["theme"], item["rule"], target)
        for item in findings
        for target in item["targets"]
    }


def serialize_baseline(findings: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "entries": [
            {"route": route, "theme": theme, "rule": rule, "target": target}
            for route, theme, rule, target in sorted(violation_keys(findings))
        ],
    }


def read_baseline(path: Path) -> set[tuple[str, str, str, str]]:
    if not path.is_file():
        raise SystemExit(f"baseline de acessibilidade ausente: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not data.get("entries"):
        raise SystemExit(f"baseline de acessibilidade vazia ou incompatível: {path}")
    return {
        (entry["route"], entry["theme"], entry["rule"], entry["target"])
        for entry in data["entries"]
    }


def _login(page, base_url: str, username: str, password: str, timeout_ms: int) -> None:
    page.goto(urljoin(base_url, "login/"), wait_until="domcontentloaded", timeout=timeout_ms)
    page.locator('[name="username"]').fill(username)
    page.locator('[name="password"]').fill(password)
    page.locator('button[type="submit"], input[type="submit"]').first.click()
    page.wait_for_load_state("networkidle", timeout=timeout_ms)
    if page.url.rstrip("/").endswith("/login"):
        raise RuntimeError("a autenticação do usuário de acessibilidade foi recusada")


def _scan(page, route, theme: str, base_url: str, timeout_ms: int) -> list[dict]:
    response = page.goto(
        urljoin(base_url, route.path.lstrip("/")),
        wait_until="networkidle",
        timeout=timeout_ms,
    )
    if response is None or response.status >= 400:
        status = response.status if response else "sem resposta"
        raise RuntimeError(f"{route.slug}: HTTP {status} em {route.path}")
    if not is_valid_final_url(
        page.url,
        route.path,
        base_url,
        requires_auth=route.requires_auth,
    ):
        raise RuntimeError(f"{route.slug}: terminou em URL inválida: {page.url}")

    result = page.evaluate(
        """async (tags) => axe.run(document, {
            runOnly: {type: 'tag', values: tags},
            resultTypes: ['violations']
        })""",
        list(AXE_TAGS),
    )
    return summarize_violations(route.slug, theme, result["violations"])


def run_audit(args) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("Playwright não instalado; instale requirements/test-lock.txt.") from exc

    axe_path = RAIZ / "node_modules/axe-core/axe.min.js"
    if not axe_path.is_file():
        raise SystemExit("axe-core ausente; rode `npm ci` antes da auditoria.")

    username = args.username or os.environ.get("FRONT_METRICS_USERNAME")
    password = os.environ.get(args.password_env)
    routes = [route for route in ROTAS if not args.route or route.slug in args.route]
    unknown = sorted(set(args.route or ()) - {route.slug for route in ROTAS})
    if unknown:
        raise SystemExit(f"rotas desconhecidas: {', '.join(unknown)}")
    if any(route.requires_auth for route in routes) and (not username or not password):
        raise SystemExit(
            "rotas protegidas exigem --username e a senha em " f"{args.password_env}."
        )

    findings: list[dict] = []
    measurements = 0
    with sync_playwright() as playwright:
        browser = abrir_chromium(playwright, headless=not args.headful)
        for theme in THEMES:
            context = browser.new_context(viewport={"width": args.width, "height": args.height})
            context.add_init_script(
                script=(
                    f"localStorage.setItem('theme', {json.dumps(theme)});"
                    f"document.documentElement.setAttribute('data-theme', {json.dumps(theme)});"
                )
            )
            # Init scripts não são bloqueados pelo `script-src 'self'` da página;
            # uma tag inline seria corretamente recusada pela CSP de produção.
            context.add_init_script(path=str(axe_path))
            page = context.new_page()
            public = [route for route in routes if not route.requires_auth]
            protected = [route for route in routes if route.requires_auth]
            for route in public:
                findings.extend(_scan(page, route, theme, args.base_url, args.timeout_ms))
                measurements += 1
            if protected:
                _login(page, args.base_url, username, password, args.timeout_ms)
            for route in protected:
                findings.extend(_scan(page, route, theme, args.base_url, args.timeout_ms))
                measurements += 1
            context.close()
        browser.close()

    return {
        "metric": "axe_wcag_violations",
        "route_count": len(routes),
        "themes": list(THEMES),
        "measurement_count": measurements,
        "violations": findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/")
    parser.add_argument("--username")
    parser.add_argument("--password-env", default="FRONT_METRICS_PASSWORD")
    parser.add_argument("--route", action="append", help="slug a medir; repetível")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=1000)
    parser.add_argument("--timeout-ms", type=int, default=45_000)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--headful", action="store_true")
    args = parser.parse_args(argv)

    report = run_audit(args)
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    expected = report["route_count"] * len(THEMES)
    if report["measurement_count"] != expected:
        print(f"ERRO: {report['measurement_count']} de {expected} medições concluídas.")
        return 1
    if args.update_baseline:
        if args.route:
            raise SystemExit("a baseline só pode ser atualizada com o corpus completo")
        args.baseline.write_text(
            json.dumps(serialize_baseline(report["violations"]), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Baseline atualizada: {args.baseline}")

    baseline = read_baseline(args.baseline)
    current = violation_keys(report["violations"])
    new = current - baseline
    if new:
        for route, theme, rule, target in sorted(new):
            print(f"{route}@{theme}: {rule} — {target}")
        print(f"ERRO: {len(new)} novas violações de acessibilidade.")
        return 1

    removed = baseline - current
    print(
        f"OK: {report['measurement_count']} medições axe, "
        f"{report['route_count']} rotas × {len(THEMES)} temas, "
        f"0 novas violações; {len(current)} alvos conhecidos e "
        f"{len(removed)} removidos da baseline."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
