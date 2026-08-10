#!/usr/bin/env python
"""Mede CSS entregue e efetivamente casado nas 43 rotas canônicas via CDP."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.navegador_medicao import abrir_chromium  # noqa: E402
from scripts.rotas_do_sistema import ROTAS  # noqa: E402


DEFAULT_THRESHOLDS = ROOT / "scripts" / "tetos_front.json"


def merge_ranges(ranges: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted(ranges):
        if end <= start:
            continue
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def _utf8_bytes_for_offsets(text: str, start: int, end: int) -> int:
    """Converte offsets UTF-16 do CDP em bytes UTF-8 sem errar astral chars."""
    raw = text.encode("utf-16-le")
    segment = raw[max(0, start) * 2 : max(0, end) * 2]
    return len(segment.decode("utf-16-le", errors="ignore").encode("utf-8"))


def summarize_rule_usage(stylesheets: dict[str, str], usage: list[dict]) -> dict[str, float | int]:
    used_by_sheet: dict[str, list[tuple[int, int]]] = {}
    for item in usage:
        if not item.get("used"):
            continue
        sheet_id = item["styleSheetId"]
        used_by_sheet.setdefault(sheet_id, []).append((item["startOffset"], item["endOffset"]))

    delivered = sum(len(text.encode("utf-8")) for text in stylesheets.values())
    matched = 0
    for sheet_id, ranges in used_by_sheet.items():
        text = stylesheets.get(sheet_id)
        if text is None:
            continue
        matched += sum(_utf8_bytes_for_offsets(text, start, end) for start, end in merge_ranges(ranges))
    percent = (100.0 * matched / delivered) if delivered else 0.0
    return {
        "bytes_delivered": delivered,
        "bytes_matched": matched,
        "usage_percent": round(percent, 4),
    }


def updated_floors(
    old: dict[str, dict],
    measured: dict[str, dict],
    *,
    allow_weaker: bool = False,
) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for slug, data in measured.items():
        current = round(float(data["usage_percent"]), 4)
        previous = old.get(slug, {}).get("usage_percent_min")
        if previous is None or allow_weaker:
            floor = current
        else:
            floor = max(float(previous), current)
        result[slug] = {"usage_percent_min": round(floor, 4)}
    return result


def evaluate_floors(measured: dict[str, dict], floors: dict[str, dict]) -> list[str]:
    regressions: list[str] = []
    for slug, threshold in sorted(floors.items()):
        if slug not in measured:
            regressions.append(f"{slug}: rota não foi medida")
            continue
        actual = float(measured[slug]["usage_percent"])
        minimum = float(threshold["usage_percent_min"])
        if actual + 1e-9 < minimum:
            regressions.append(f"{slug}: uso {actual:.4f}% < piso {minimum:.4f}%")
    return regressions


def _read_thresholds(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 1}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_thresholds(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_valid_final_url(actual_url: str, expected_path: str, base_url: str, *, requires_auth: bool) -> bool:
    actual = urlparse(actual_url)
    base = urlparse(base_url)
    if (actual.scheme, actual.netloc) != (base.scheme, base.netloc):
        return False
    actual_path = actual.path.rstrip("/")
    if requires_auth:
        return actual_path != "/login"
    return actual_path == expected_path.rstrip("/")


def _measure_page(page, route, base_url: str, timeout_ms: int) -> dict:
    from playwright.sync_api import Error as PlaywrightError

    session = page.context.new_cdp_session(page)
    session.send("DOM.enable")
    session.send("CSS.enable")
    session.send("CSS.startRuleUsageTracking")
    response = page.goto(urljoin(base_url, route.path.lstrip("/")), wait_until="networkidle", timeout=timeout_ms)
    coverage = session.send("CSS.stopRuleUsageTracking").get("ruleUsage", [])

    if response is None:
        raise RuntimeError(f"{route.slug}: navegação não produziu resposta HTTP")
    if response.status >= 400:
        raise RuntimeError(f"{route.slug}: HTTP {response.status} em {route.path}")
    if not is_valid_final_url(
        page.url,
        route.path,
        base_url,
        requires_auth=route.requires_auth,
    ):
        raise RuntimeError(f"{route.slug}: {route.path} terminou em URL inválida: {page.url}")

    stylesheets: dict[str, str] = {}
    for sheet_id in sorted({item["styleSheetId"] for item in coverage}):
        try:
            stylesheets[sheet_id] = session.send(
                "CSS.getStyleSheetText",
                {"styleSheetId": sheet_id},
            )["text"]
        except PlaywrightError:
            # Folhas internas do navegador não são bytes entregues pela aplicação.
            continue
    result = summarize_rule_usage(stylesheets, coverage)
    result.update(
        {
            "path": route.path,
            "final_url": page.url,
            "redirected": urlparse(page.url).path.rstrip("/") != route.path.rstrip("/"),
            "stylesheets": len(stylesheets),
        }
    )
    session.detach()
    return result


def _login(page, base_url: str, username: str, password: str, timeout_ms: int) -> None:
    login_url = urljoin(base_url, "login/")
    page.goto(login_url, wait_until="domcontentloaded", timeout=timeout_ms)
    page.locator('[name="username"]').fill(username)
    page.locator('[name="password"]').fill(password)
    page.locator('button[type="submit"], input[type="submit"]').first.click()
    page.wait_for_load_state("networkidle", timeout=timeout_ms)
    if urlparse(page.url).path.rstrip("/") == "/login":
        raise RuntimeError("a autenticação do usuário de medição foi recusada")


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

    measurements: dict[str, dict] = {}
    with sync_playwright() as playwright:
        if args.cdp_url:
            browser = playwright.chromium.connect_over_cdp(args.cdp_url)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            owns_browser = False
        else:
            browser = abrir_chromium(playwright, headless=not args.headful)
            context = browser.new_context(
                viewport={"width": args.viewport_width, "height": args.viewport_height},
                storage_state=args.storage_state,
            )
            owns_browser = True
        page = context.new_page()

        public_routes = [route for route in ROTAS if not route.requires_auth]
        protected_routes = [route for route in ROTAS if route.requires_auth]
        for route in public_routes:
            measurements[route.slug] = _measure_page(page, route, args.base_url, args.timeout_ms)

        if not args.storage_state:
            _login(page, args.base_url, username, password, args.timeout_ms)
        for route in protected_routes:
            measurements[route.slug] = _measure_page(page, route, args.base_url, args.timeout_ms)
            print(
                f"{route.slug}: {measurements[route.slug]['usage_percent']:.2f}% "
                f"({measurements[route.slug]['bytes_matched']}/"
                f"{measurements[route.slug]['bytes_delivered']} bytes)"
            )
        context.close()
        if owns_browser:
            browser.close()

    values = [float(item["usage_percent"]) for item in measurements.values()]
    return {
        "metric": "css_usage_by_route",
        "direction": "up",
        "route_count": len(measurements),
        "summary": {"minimum_percent": min(values), "maximum_percent": max(values)},
        "routes": measurements,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("FRONT_METRICS_BASE_URL", "http://127.0.0.1:8000/"))
    parser.add_argument("--username")
    parser.add_argument("--password-env", default="FRONT_METRICS_PASSWORD")
    parser.add_argument("--storage-state", type=Path)
    parser.add_argument("--cdp-url")
    parser.add_argument("--headful", action="store_true")
    parser.add_argument("--viewport-width", type=int, default=1440)
    parser.add_argument("--viewport-height", type=int, default=900)
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--atualizar-tetos", action="store_true")
    parser.add_argument("--permitir-subir-teto", action="store_true", help="permite enfraquecer um piso existente")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    report = run_measurement(args)
    if report["route_count"] != len(ROTAS):
        print(f"ERRO: foram medidas {report['route_count']} de {len(ROTAS)} rotas.")
        return 1
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    thresholds = _read_thresholds(args.thresholds)
    current = thresholds.get("css_by_route", {}).get("routes", {})
    measured = report["routes"]
    if args.atualizar_tetos:
        thresholds["css_by_route"] = {
            "direction": "up",
            "routes": updated_floors(current, measured, allow_weaker=args.permitir_subir_teto),
        }
        _write_thresholds(args.thresholds, thresholds)
        print(f"Pisos regravados em {args.thresholds}")

    floors = thresholds.get("css_by_route", {}).get("routes", {})
    regressions = evaluate_floors(measured, floors)
    if regressions:
        print("\nERRO: regressão de uso de CSS:")
        for regression in regressions:
            print(f"- {regression}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
