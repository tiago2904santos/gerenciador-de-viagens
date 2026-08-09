#!/usr/bin/env python
"""Relata padrões de UI legados e, com ``--max``, funciona como catraca.

Sem teto o comando é diagnóstico e sempre sai zero. No CI, ``--max N`` reprova
somente quando a dívida medida ultrapassa N. Definições de custom properties e
o bundle gerado não entram na conta: os literais são válidos na camada de token
e o bundle apenas duplicaria achados que já pertencem aos arquivos-fonte.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
TARGETS = [ROOT / "templates", ROOT / "static" / "css"]
IGNORED_PARTS = {
    "templates/components/ui",
    "templates/documentos/pdf",
}
GENERATED_FILES = {"static/css/shell.bundle.css"}

PATTERNS: dict[str, str] = {
    "inline_css": r"style\s*=",
    "inline_js": r"\bon(click|input|change)\s*=",
    "bootstrap_button": r'\bbtn-(primary|secondary|success|danger)\b|\bclass="btn\b',
    "raw_button": r"<button\b",
    "legacy_action_group": r"\b(submit-row|form-actions|action-buttons)\b",
    "page_header_legacy": r"\b(app-page-hero|page-header--clean|toolbar-header|title-bar)\b",
    "module_card": r"\b(oficio-card|termo-card|servidor-card|cargo-card|unidade-card|combustivel-card|custom-card|process-card)\b",
    "field_legacy": r"\b(input-group|form-control|form-select|custom-input|custom-select|field-wrapper|inline-field)\b",
    "filter_legacy": r"\b(filter-bar|filters|search-box|search-row|list-toolbar)\b",
    "hardcoded_visual": r"(?:^|[;{])\s*(box-shadow|border-radius|background|color|border|font-size|font-weight|padding|margin|gap)\s*:\s*(?!\s*(var|transparent|none|0|inherit|currentColor)\b)",
    "hex_or_rgba": r"(?<!&)#[0-9a-fA-F]{3,8}\b|rgba?\(",
    "rendered_docs": r"(# Button|Parâmetros|Parametros)",
}

CSS_ONLY = {"hardcoded_visual", "hex_or_rgba"}
TEMPLATE_ONLY = {"inline_css", "inline_js", "raw_button", "rendered_docs"}
CUSTOM_PROPERTY = re.compile(r"^\s*--[\w-]+\s*:")
COMPILED = {name: re.compile(pattern, re.IGNORECASE) for name, pattern in PATTERNS.items()}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    excerpt: str


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def ignored(path: Path, *, root: Path = ROOT) -> bool:
    rel = _relative(path, root)
    return rel in GENERATED_FILES or any(rel.startswith(part) for part in IGNORED_PARTS)


def iter_files(*, root: Path = ROOT, targets: Sequence[Path] | None = None) -> list[Path]:
    files: list[Path] = []
    for target in targets or TARGETS:
        if not target.exists():
            continue
        for path in target.rglob("*"):
            if path.suffix not in {".html", ".css"} or ignored(path, root=root):
                continue
            files.append(path)
    return sorted(files)


def scan_file(path: Path, *, root: Path = ROOT) -> list[Finding]:
    if ignored(path, root=root):
        return []

    rel = _relative(path, root)
    suffix = path.suffix.lower()
    findings: list[Finding] = []
    for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        is_custom_property = suffix == ".css" and CUSTOM_PROPERTY.search(line)
        for name, pattern in COMPILED.items():
            if name in CSS_ONLY and suffix != ".css":
                continue
            if name in TEMPLATE_ONLY and suffix != ".html":
                continue
            if is_custom_property and name in CSS_ONLY:
                continue
            if pattern.search(line):
                findings.append(Finding(rel, number, name, line.strip()[:140]))
    return findings


def collect_findings(*, root: Path = ROOT, targets: Sequence[Path] | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_files(root=root, targets=targets):
        findings.extend(scan_file(path, root=root))
    return findings


def exceeds_limit(*, total: int, maximum: int) -> bool:
    return total > maximum


def _print_report(findings: Sequence[Finding], *, quiet: bool) -> None:
    print(f"{len(findings)} ocorrência(s) suspeita(s) encontradas:")
    by_kind: dict[str, int] = {}
    for finding in findings:
        by_kind[finding.kind] = by_kind.get(finding.kind, 0) + 1
    for name, count in sorted(by_kind.items()):
        print(f"- {name}: {count}")

    if quiet or not findings:
        return
    print("\nPrimeiras 200 ocorrências:")
    for finding in findings[:200]:
        print(f"{finding.path}:{finding.line}: {finding.kind}: {finding.excerpt}")
    if len(findings) > 200:
        print(f"... {len(findings) - 200} ocorrência(s) adicionais omitidas.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--max",
        dest="maximum",
        type=int,
        help="reprova se a contagem ultrapassar este teto; sem teto, apenas relata",
    )
    parser.add_argument("--quiet", action="store_true", help="omite a listagem detalhada")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    findings = collect_findings(root=ROOT, targets=TARGETS)
    _print_report(findings, quiet=args.quiet)

    if args.maximum is None:
        print("Modo relatório: use --max N para ativar a catraca.")
        return 0
    if exceeds_limit(total=len(findings), maximum=args.maximum):
        print(f"ERRO: {len(findings)} ocorrência(s) excedem o teto de {args.maximum}.")
        return 1
    print(f"OK: {len(findings)} ocorrência(s), dentro do teto de {args.maximum}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
