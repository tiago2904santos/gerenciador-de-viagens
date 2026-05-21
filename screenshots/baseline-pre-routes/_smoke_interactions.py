"""
Smoke interativo mínimo (Playwright) — filtros UI Lab e carga de scripts globais.
Requer servidor em http://localhost:8000
"""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8000"
OUT_DIR = Path(__file__).parent


def run():
    console_log = []
    checks = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        def on_console(msg):
            if msg.type in ("error", "warning"):
                console_log.append({"type": msg.type, "text": msg.text})

        page.on("console", on_console)

        # CV.filters — UI Lab lists (primeiro escopo)
        page.goto(BASE_URL + "/dev/ui-lab/lists/", wait_until="domcontentloaded")
        page.wait_for_timeout(800)

        apis = page.evaluate(
            """() => ({
              filters: !!(window.CV && window.CV.filters),
              fields: !!(window.CV && window.CV.fields),
              masks: !!(window.CV && window.CV.masks),
              stateToggle: !!(window.CV && window.CV.stateToggle),
              http: !!(window.CV && window.CV.http),
            })"""
        )
        checks.append({"name": "apis_globais_ui_lab", "ok": all(apis.values()), "detail": apis})

        scope = page.locator("[data-cv-realtime-filter-scope]").first
        search = scope.locator('[data-cv-filter="search"]').first
        search.fill("zzznomatch")
        page.wait_for_timeout(400)
        visible_after = page.evaluate(
            """() => {
              const scope = document.querySelector('[data-cv-realtime-filter-scope]');
              const items = scope ? scope.querySelectorAll('[data-cv-filter-item]') : [];
              let visible = 0;
              items.forEach((el) => { if (!el.hidden) visible++; });
              const empty = scope && scope.querySelector('[data-cv-empty-state]');
              return {
                total: items.length,
                visible,
                emptyShown: empty ? !empty.hidden : null,
              };
            }"""
        )
        checks.append(
            {
                "name": "cv_filters_search_no_match",
                "ok": visible_after["visible"] == 0 and visible_after["emptyShown"] is True,
                "detail": visible_after,
            }
        )

        clear_btn = scope.locator("[data-cv-filter-clear]").first
        if clear_btn.count():
            clear_btn.click()
            page.wait_for_timeout(400)
            visible_cleared = page.evaluate(
                """() => {
                  const scope = document.querySelector('[data-cv-realtime-filter-scope]');
                  const items = scope ? scope.querySelectorAll('[data-cv-filter-item]') : [];
                  let visible = 0;
                  items.forEach((el) => { if (!el.hidden) visible++; });
                  return { visible, total: items.length };
                }"""
            )
            checks.append(
                {
                    "name": "cv_filters_clear",
                    "ok": visible_cleared["visible"] == visible_cleared["total"],
                    "detail": visible_cleared,
                }
            )

        # CV.fields — UI Lab fields
        page.goto(BASE_URL + "/dev/ui-lab/fields/", wait_until="domcontentloaded")
        page.wait_for_timeout(600)
        dup_select = page.evaluate(
            """() => document.querySelectorAll('[data-cv-select]._cvSelect, [data-cv-select][data-cv-select-bound]').length"""
        )
        checks.append({"name": "fields_page_load", "ok": True, "detail": {"bound_selects": dup_select}})

        browser.close()

    report = {"checks": checks, "console": console_log}
    with open(OUT_DIR / "_smoke_interactions.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report


if __name__ == "__main__":
    run()
