from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = [ROOT / "templates", ROOT / "static" / "css"]
IGNORED_PARTS = {
    "templates/dev/ui_lab",
    "templates/documentos/pdf",
    "static/css/dev",
}

PATTERNS: dict[str, str] = {
    "inline_css": r'style\s*=',
    "inline_js": r"\bon(click|input|change)\s*=",
    "bootstrap_button": r"\bbtn-(primary|secondary|success|danger)\b|\bclass=\"btn\b",
    "raw_button": r"<button\b",
    "legacy_action_group": r"\b(submit-row|form-actions|action-buttons)\b",
    "page_header_legacy": r"\b(app-page-hero|page-header--clean|toolbar-header|title-bar)\b",
    "module_card": r"\b(oficio-card|termo-card|servidor-card|cargo-card|unidade-card|combustivel-card|custom-card|process-card)\b",
    "field_legacy": r"\b(input-group|form-control|form-select|custom-input|custom-select|field-wrapper|inline-field)\b",
    "filter_legacy": r"\b(filter-bar|filters|search-box|search-row|list-toolbar)\b",
    "hardcoded_visual": r"\b(box-shadow|border-radius|background|color|border|font-size|font-weight|padding|margin|gap)\s*:\s*(?!(var|transparent|none|0|inherit|currentColor)\b)",
    "hex_or_rgba": r"(#[0-9a-fA-F]{3,8}|rgba?\()",
    "rendered_docs": r"(# Button|Parâmetros|Parametros)",
}


def ignored(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    return any(rel.startswith(part) for part in IGNORED_PARTS)


def iter_files() -> list[Path]:
    files: list[Path] = []
    for target in TARGETS:
        if not target.exists():
            continue
        for path in target.rglob("*"):
            if path.suffix not in {".html", ".css"}:
                continue
            if ignored(path):
                continue
            files.append(path)
    return files


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    findings: list[tuple[str, int, str, str]] = []
    compiled = {name: re.compile(pattern, re.IGNORECASE) for name, pattern in PATTERNS.items()}

    for path in iter_files():
        rel = path.relative_to(ROOT).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for name, pattern in compiled.items():
                if pattern.search(line):
                    findings.append((rel, number, name, line.strip()[:140]))

    if not findings:
        print("Nenhum padrão proibido encontrado.")
        return 0

    print(f"{len(findings)} ocorrência(s) suspeita(s) encontradas:")
    for rel, number, name, excerpt in findings:
        print(f"{rel}:{number}: {name}: {excerpt}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
