"""
Baseline visual pré-Fase 5 — reutiliza Playwright já usado em screenshots/auditoria-telas/.
Requer: servidor em http://localhost:8000 e sessão autenticada (ou rotas públicas).
"""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8000"
OUT_DIR = Path(__file__).parent
VIEWPORT = {"width": 1440, "height": 900}

TELAS = [
    ("ui-lab-lists", "/dev/ui-lab/lists/"),
    ("ui-lab-fields", "/dev/ui-lab/fields/"),
    ("ui-lab-selects-filters", "/dev/ui-lab/selects-filters/"),
    ("cadastros-cargos", "/cadastros/cargos/"),
    ("cadastros-servidores", "/cadastros/servidores/"),
    ("cadastros-viaturas", "/cadastros/viaturas/"),
    ("oficios-index", "/oficios/"),
    ("roteiros-index", "/roteiros/"),
    ("cadastros-configuracao", "/cadastros/configuracao/"),
]


def capture_all():
    results = []
    console_log = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()

        def on_console(msg):
            if msg.type in ("error", "warning"):
                console_log.append(
                    {
                        "type": msg.type,
                        "text": msg.text,
                        "url": page.url,
                    }
                )

        page.on("console", on_console)

        for nome, rota in TELAS:
            url = BASE_URL + rota
            path = OUT_DIR / f"{nome}.png"
            entry = {"nome": nome, "rota": rota, "screenshot": None, "status": None}
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(500)
                page.screenshot(path=str(path), full_page=True)
                entry["screenshot"] = path.name
                entry["status"] = "ok" if page.url.rstrip("/") == url.rstrip("/") else f"url_final={page.url}"
                print(f"[OK] {nome}.png")
            except Exception as e:
                entry["status"] = f"ERRO: {e}"
                print(f"[ERRO] {nome}: {e}")
            results.append(entry)

        browser.close()

    report = {
        "telas": results,
        "console_errors_warnings": console_log,
        "viewport": VIEWPORT,
        "base_url": BASE_URL,
    }
    with open(OUT_DIR / "_baseline_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report


if __name__ == "__main__":
    capture_all()
