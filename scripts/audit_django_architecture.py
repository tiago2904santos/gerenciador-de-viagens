import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# `P-01`: ORM montado dentro de views.py. A catraca desce a cada app que ganha
# selectors e nunca sobe — mesma convenção do `--max-warnings` do auditor de
# frontend e do piso de cobertura. O alvo final é zero, mas ele não é atingível
# num PR só: `core`, `documentos` e `usuarios` estão fora do escopo do `P-01`.
ORM_EM_VIEW = re.compile(r"\.objects\b")
DRIVE_ROOT = ROOT / "integracoes" / "google_drive"

PY_RULES = [
    ("query_direta_view", ("views.py", ".objects.filter(")),
    ("query_direta_view", ("views.py", ".objects.get(")),
    ("query_direta_view", ("views.py", ".objects.all(")),
    ("get_object_or_404_em_view", ("views.py", "get_object_or_404(")),
    ("html_em_presenter", ("presenters.py", "mark_safe")),
    ("html_em_presenter", ("presenters.py", "<")),
    ("protectederror_fora_service", (".py", "ProtectedError")),
    ("atomic_em_view", ("views.py", "transaction.atomic")),
    ("http_direto_em_view", ("views.py", "requests.get(")),
    ("http_direto_em_view", ("views.py", "requests.post(")),
]

HTML_RULES = [
    ("href_falso_template", 'href="#"'),
    ("javascript_void_template", "javascript:void"),
    ("updated_at_exibido", "updated_at"),
    ("atualizado_em_exibido", "Atualizado em"),
    ("css_inline_template", 'style="'),
    ("script_inline_template", "<script>"),
    ("onclick_inline_template", "onclick="),
    ("onchange_inline_template", "onchange="),
    ("oninput_inline_template", "oninput="),
]

ALLOWLIST = {
    "core/deletion.py": {"protectederror_fora_service"},
    "scripts/audit_django_architecture.py": {"protectederror_fora_service", "http_direto_em_view"},
}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_allowed(path: str, rule_name: str) -> bool:
    return rule_name in ALLOWLIST.get(path, set())


def iter_files(ext: str):
    for path in ROOT.rglob(f"*{ext}"):
        if ".venv" in path.parts or ".git" in path.parts or "legacy" in path.parts:
            continue
        if path.is_file():
            yield path


def audit_python():
    findings = []
    for path in iter_files(".py"):
        path_rel = rel(path)
        text = path.read_text(encoding="utf-8")
        for idx, line in enumerate(text.splitlines(), start=1):
            for rule_name, (filename_suffix, needle) in PY_RULES:
                if not path_rel.endswith(filename_suffix):
                    continue
                if rule_name == "protectederror_fora_service" and "/services" in path_rel:
                    continue
                if is_allowed(path_rel, rule_name):
                    continue
                if needle in line:
                    findings.append((path_rel, idx, rule_name, line.strip()))
    return findings


def audit_templates():
    findings = []
    for path in iter_files(".html"):
        path_rel = rel(path)
        text = path.read_text(encoding="utf-8")
        for idx, line in enumerate(text.splitlines(), start=1):
            for rule_name, needle in HTML_RULES:
                if is_allowed(path_rel, rule_name):
                    continue
                if needle in line:
                    findings.append((path_rel, idx, rule_name, line.strip()))
    return findings


def contar_orm_em_views():
    """Conta ocorrências de `.objects` em cada `views.py`, por app."""
    por_app = {}
    for path in iter_files(".py"):
        if path.name != "views.py":
            continue
        app = rel(path).rsplit("/", 1)[0] or "."
        total = len(ORM_EM_VIEW.findall(path.read_text(encoding="utf-8")))
        if total:
            por_app[app] = total
    return por_app


def _is_exception_handler(node: ast.ExceptHandler) -> bool:
    if isinstance(node.type, ast.Name):
        return node.type.id == "Exception"
    if isinstance(node.type, ast.Tuple):
        return any(isinstance(item, ast.Name) and item.id == "Exception" for item in node.type.elts)
    return False


def _is_capture_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Name):
        return node.func.id == "capture"
    return isinstance(node.func, ast.Attribute) and node.func.attr == "capture"


def _handler_starts_with_capture(node: ast.ExceptHandler) -> bool:
    if not node.body or not isinstance(node.body[0], ast.Expr):
        return False
    return _is_capture_call(node.body[0].value)


def except_exception_without_capture(code: str) -> list[int]:
    tree = ast.parse(code)
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.ExceptHandler)
        and _is_exception_handler(node)
        and not _handler_starts_with_capture(node)
    ]


def drive_excepts_without_capture():
    findings = []
    for path in DRIVE_ROOT.rglob("*.py"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for line_no in except_exception_without_capture(text):
            findings.append((rel(path), line_no))
    return findings


def main():
    parser = argparse.ArgumentParser(description="Auditoria de arquitetura Django")
    parser.add_argument(
        "--max-orm-em-view",
        type=int,
        default=None,
        help="falha se o total de `.objects` em views.py passar deste número (catraca do P-01)",
    )
    parser.add_argument(
        "--max-drive-except-without-capture",
        type=int,
        default=None,
        help="falha se handlers `except Exception` do Drive não chamarem core.errors.capture",
    )
    args = parser.parse_args()

    findings = [*audit_python(), *audit_templates()]
    print("== Auditoria Django Arquitetura (suspeitas) ==")
    if findings:
        for file_path, line_no, rule_name, line in findings:
            print(f"{file_path}:{line_no} [{rule_name}] {line}")
        print(f"Total de suspeitas: {len(findings)}")
    else:
        print("Nenhuma suspeita encontrada.")

    por_app = contar_orm_em_views()
    total_orm = sum(por_app.values())
    print("\n== ORM em views.py (P-01) ==")
    for app, total in sorted(por_app.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {app}: {total}")
    print(f"Total: {total_orm}")

    if args.max_orm_em_view is not None and total_orm > args.max_orm_em_view:
        print(
            f"\nERRO: {total_orm} usos de ORM em views.py, acima da catraca "
            f"de {args.max_orm_em_view}. A camada de selectors existe para isso "
            f"(docs/PADRAO_SELECTORS.md); a catraca só desce.",
        )
        sys.exit(1)

    drive_findings = drive_excepts_without_capture()
    print("\n== except Exception sem capture no Google Drive (P-05) ==")
    for file_path, line_no in drive_findings:
        print(f"  {file_path}:{line_no}")
    print(f"Total: {len(drive_findings)}")

    if (
        args.max_drive_except_without_capture is not None
        and len(drive_findings) > args.max_drive_except_without_capture
    ):
        print(
            f"\nERRO: {len(drive_findings)} handlers genéricos do Drive sem "
            "core.errors.capture, acima da catraca de "
            f"{args.max_drive_except_without_capture}.",
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
