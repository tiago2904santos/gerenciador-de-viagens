"""
Script de captura de screenshots - Central de Viagens 3.0
Viewport: 1440x900 desktop | Full page screenshots
"""

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8000"
OUT_DIR = Path(__file__).parent
VIEWPORT = {"width": 1440, "height": 900}

OFICIO_PK = 2
ROTEIRO_PK = 22
SERVIDOR_PK = 1
VIATURA_PK = 1
JUSTIFICATIVA_PK = 1
UNIDADE_PK = 1
CARGO_PK = 1
COMBUSTIVEL_PK = 1
MODELO_MOTIVO_PK = 2

TELAS = [
    # Login
    ("01-login", "/login/"),
    # Dashboard
    ("02-dashboard", "/"),
    # Ofícios
    ("03-oficios-lista", "/oficios/"),
    ("04-oficios-novo", "/oficios/novo/"),
    ("05-oficios-detalhe", f"/oficios/{OFICIO_PK}/"),
    ("06-oficios-editar", f"/oficios/{OFICIO_PK}/editar/"),
    ("07-oficios-wizard-dados-viajantes", f"/oficios/{OFICIO_PK}/dados-viajantes/"),
    ("08-oficios-wizard-transporte", f"/oficios/{OFICIO_PK}/transporte/"),
    ("09-oficios-wizard-roteiro", f"/oficios/{OFICIO_PK}/roteiro/"),
    ("10-oficios-wizard-justificativa", f"/oficios/{OFICIO_PK}/justificativa/"),
    ("11-oficios-wizard-resumo", f"/oficios/{OFICIO_PK}/resumo/"),
    ("12-oficios-wizard-documentos", f"/oficios/{OFICIO_PK}/documentos/"),
    ("13-oficios-wizard-assinaturas", f"/oficios/{OFICIO_PK}/assinaturas/"),
    ("14-oficios-modelos-motivo-lista", "/oficios/modelos-motivo/"),
    ("15-oficios-modelos-motivo-novo", "/oficios/modelos-motivo/novo/"),
    ("16-oficios-modelos-motivo-editar", f"/oficios/modelos-motivo/{MODELO_MOTIVO_PK}/editar/"),
    # Roteiros
    ("17-roteiros-lista", "/roteiros/"),
    ("18-roteiros-novo", "/roteiros/novo/"),
    ("19-roteiros-detalhe", f"/roteiros/{ROTEIRO_PK}/"),
    ("20-roteiros-editar", f"/roteiros/{ROTEIRO_PK}/editar/"),
    # Termos
    ("21-termos-lista", "/termos/"),
    ("22-termos-preview-oficio", f"/termos/oficio/{OFICIO_PK}/preview/"),
    # Justificativas (modelos)
    ("23-justificativas-lista", "/justificativas/"),
    ("24-justificativas-novo", "/justificativas/novo/"),
    ("25-justificativas-editar", f"/justificativas/{JUSTIFICATIVA_PK}/editar/"),
    # Planos de Trabalho
    ("26-planos-trabalho-lista", "/planos-trabalho/"),
    # Ordens de Serviço
    ("27-ordens-servico-lista", "/ordens-servico/"),
    # Cadastros
    ("28-configuracao", "/cadastros/configuracao/"),
    ("29-servidores-lista", "/cadastros/servidores/"),
    ("30-servidor-novo", "/cadastros/servidores/novo/"),
    ("31-servidor-editar", f"/cadastros/servidores/{SERVIDOR_PK}/editar/"),
    ("32-viaturas-lista", "/cadastros/viaturas/"),
    ("33-viatura-nova", "/cadastros/viaturas/nova/"),
    ("34-viatura-editar", f"/cadastros/viaturas/{VIATURA_PK}/editar/"),
    ("35-unidades-lista", "/cadastros/unidades/"),
    ("36-unidade-nova", "/cadastros/unidades/novo/"),
    ("37-unidade-editar", f"/cadastros/unidades/{UNIDADE_PK}/editar/"),
    ("38-cargos-lista", "/cadastros/cargos/"),
    ("39-cargo-novo", "/cadastros/cargos/novo/"),
    ("40-cargo-editar", f"/cadastros/cargos/{CARGO_PK}/editar/"),
    ("41-combustiveis-lista", "/cadastros/combustiveis/"),
    ("42-combustivel-novo", "/cadastros/combustiveis/novo/"),
    ("43-combustivel-editar", f"/cadastros/combustiveis/{COMBUSTIVEL_PK}/editar/"),
    # UI Lab
    ("44-ui-lab-index", "/dev/ui-lab/"),
    ("45-ui-lab-structures", "/dev/ui-lab/structures/"),
    ("46-ui-lab-lists", "/dev/ui-lab/lists/"),
    ("47-ui-lab-headers", "/dev/ui-lab/headers/"),
    ("48-ui-lab-buttons", "/dev/ui-lab/buttons/"),
    ("49-ui-lab-fields", "/dev/ui-lab/fields/"),
    ("50-ui-lab-selects-filters", "/dev/ui-lab/selects-filters/"),
    ("51-ui-lab-status", "/dev/ui-lab/status/"),
    ("52-ui-lab-feedback", "/dev/ui-lab/feedback/"),
    ("53-ui-lab-cards", "/dev/ui-lab/cards/"),
    ("54-ui-lab-overlays", "/dev/ui-lab/overlays/"),
    ("55-ui-lab-tables", "/dev/ui-lab/tables/"),
    ("56-ui-lab-documents", "/dev/ui-lab/documents/"),
    ("57-ui-lab-signature", "/dev/ui-lab/signature/"),
]


def capture_all():
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()

        for nome, rota in TELAS:
            url = BASE_URL + rota
            path = OUT_DIR / f"{nome}.png"
            try:
                page.goto(url, wait_until="networkidle", timeout=15000)
                page.wait_for_timeout(300)
                page.screenshot(path=str(path), full_page=True)
                final_url = page.url
                status = "ok" if final_url == url else f"redirect -> {final_url}"
                print(f"[OK] {nome}.png  ({status})")
                results.append({"nome": nome, "rota": rota, "status": status, "arquivo": f"{nome}.png"})
            except Exception as e:
                print(f"[ERRO] {nome}  {e}")
                # screenshot of error state if possible
                try:
                    page.screenshot(path=str(OUT_DIR / f"{nome}_ERRO.png"), full_page=True)
                except Exception:
                    pass
                results.append({"nome": nome, "rota": rota, "status": f"ERRO: {e}", "arquivo": None})

        browser.close()

    with open(OUT_DIR / "_relatorio.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    ok = [r for r in results if not r["status"].startswith("ERRO")]
    erros = [r for r in results if r["status"].startswith("ERRO")]
    redirects = [r for r in ok if r["status"].startswith("redirect")]

    print(f"\n{'='*60}")
    print(f"Total de telas: {len(TELAS)}")
    print(f"Screenshots OK: {len(ok)}")
    print(f"Redirecionamentos: {len(redirects)}")
    print(f"Erros: {len(erros)}")
    if erros:
        print("\nERROS:")
        for r in erros:
            print(f"  - {r['nome']}: {r['status']}")
    if redirects:
        print("\nREDIRECIONAMENTOS (possível login ou 404):")
        for r in redirects:
            print(f"  - {r['nome']}: {r['status']}")

    return results


if __name__ == "__main__":
    capture_all()
