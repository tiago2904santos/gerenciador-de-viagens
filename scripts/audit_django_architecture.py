import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# `P-01`: ORM montado dentro de views.py. A catraca desce a cada app que ganha
# selectors e nunca sobe — mesma convenção do `--max-warnings` do auditor de
# frontend e do piso de cobertura. O alvo final é zero, mas ele não é atingível
# num PR só: `core`, `documentos` e `usuarios` estão fora do escopo do `P-01`.
# `BE-09`: `all_objects` conta igual. O manager que recorta por área trocou o nome
# do manager irrestrito, e contar só `objects` deixaria de casar com
# `Roteiro.all_objects` — renomear desinflaria esta catraca **sem tirar uma linha
# de ORM da view**. Pego por `core/tests/test_view_module_boundaries.py`, que
# existe justamente para impedir que a métrica seja esvaziada por forma.
# `NOVO-11`: a contagem é sobre a árvore sintática, não sobre o texto. A regex
# antiga casava `.objects` dentro de docstring e comentário — prosa segurava a
# catraca no alto e explicar um ORM recém-removido fazia o CI reprovar um PR certo.
ORM_MANAGER_ATTRS = {"objects", "all_objects"}
DRIVE_ROOT = ROOT / "integracoes" / "google_drive"
OBSERVABILITY_CALL_NAMES = {
    "capture",
    "critical",
    "debug",
    "error",
    "exception",
    "info",
    "log",
    "warning",
}
P06_SPLIT_VIEW_MODULES = {
    "oficios/api_views.py",
    "oficios/list_views.py",
    "oficios/route_views.py",
    "oficios/traveler_views.py",
    "oficios/view_helpers.py",
    "oficios/wizard_document_views.py",
    "planos_trabalho/activity_views.py",
    "planos_trabalho/document_views.py",
    "planos_trabalho/identification_views.py",
    "planos_trabalho/list_views.py",
    "planos_trabalho/per_diem_views.py",
    "planos_trabalho/view_helpers.py",
    # `BE-14` fatia 1: prestações foi fatiada em módulos por tela como os dois
    # apps acima, mas ninguém os acrescentou aqui — e como a contagem só olha
    # `views.py` e esta lista, **nove acessos de manager ficaram fora da
    # medição** desde então. A catraca dizia 24 com 33 no chão. Entram agora;
    # o número sobe uma vez, por honestidade, e volta a só descer.
    "prestacoes_contas/assinatura_views.py",
    "prestacoes_contas/diario_views.py",
    "prestacoes_contas/document_views.py",
    "prestacoes_contas/model_views.py",
    "prestacoes_contas/rt_views.py",
}
SYNC_DOCUMENT_GENERATORS = {
    "gerar_resposta_documento_oficio",
    "gerar_resposta_justificativa_documento",
    "gerar_resposta_ordem_servico_documento",
    "gerar_resposta_plano_documento",
    "gerar_os_docx_response",
    "gerar_os_pdf_response",
    "gerar_termo_cadastro_um",
    "gerar_termo_lote",
    "gerar_termos_pdf_consolidado",
    "gerar_termo_um",
    "pdf_termo_cadastro_assinado_ou_gerado",
    "pdf_termo_oficio_assinado_ou_gerado",
    "gerar_prestacao_consolidado_pdf",
    "gerar_relatorio_tecnico_docx",
    "gerar_relatorio_tecnico_pdf",
    "gerar_diario_bordo_xlsx",
    "gerar_diario_bordo_pdf",
    "pdf_rt_assinado_ou_gerado",
    "pdf_db_assinado_ou_gerado",
}

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


def contar_orm_no_codigo(code: str) -> int:
    """Acessos a `.objects`/`.all_objects` no **código**, via `ast.Attribute`.

    `NOVO-11`: docstring e comentário não existem para este contador. Expressão
    dentro de f-string continua contando — para o `ast` ela é código.
    """
    tree = ast.parse(code)
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in ORM_MANAGER_ATTRS
    )


def contar_orm_em_views():
    """Conta acessos de manager em cada módulo de view, por app."""
    por_app = {}
    for path in iter_files(".py"):
        path_rel = rel(path)
        if path.name != "views.py" and path_rel not in P06_SPLIT_VIEW_MODULES:
            continue
        app = (
            path_rel.split("/", 1)[0]
            if path_rel in P06_SPLIT_VIEW_MODULES
            else path_rel.rsplit("/", 1)[0] or "."
        )
        # `utf-8-sig` pela mesma razão dos gates vizinhos (BE-22): um BOM novo
        # mataria o `ast.parse` e o gate morreria em vez de medir.
        total = contar_orm_no_codigo(path.read_text(encoding="utf-8-sig"))
        if total:
            por_app[app] = por_app.get(app, 0) + total
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


class _HandlerObservabilityVisitor(ast.NodeVisitor):
    def __init__(self):
        self.found = False

    def visit_Raise(self, node):
        self.found = True

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        else:
            name = ""
        if name in OBSERVABILITY_CALL_NAMES:
            self.found = True
        if not self.found:
            self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        # Um log do handler interno não observa a falha capturada pelo externo.
        return

    def visit_FunctionDef(self, node):
        return

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_Lambda = visit_FunctionDef
    visit_ClassDef = visit_FunctionDef


def _handler_has_observability(node: ast.ExceptHandler) -> bool:
    visitor = _HandlerObservabilityVisitor()
    for statement in node.body:
        visitor.visit(statement)
        if visitor.found:
            return True
    return False


def except_exception_without_observability(code: str) -> list[int]:
    """Localiza handlers genéricos que engolem a falha sem registro nem re-raise."""

    tree = ast.parse(code)
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.ExceptHandler)
        and _is_exception_handler(node)
        and not _handler_has_observability(node)
    ]


def production_excepts_without_observability():
    findings = []
    for path in iter_files(".py"):
        path_rel = rel(path)
        if (
            path_rel.startswith("scripts/")
            or "/tests/" in f"/{path_rel}"
            or "/migrations/" in f"/{path_rel}"
            or path.name.startswith("test")
        ):
            continue
        text = path.read_text(encoding="utf-8-sig")
        for line_no in except_exception_without_observability(text):
            findings.append((path_rel, line_no))
    return findings


def drive_excepts_without_capture():
    findings = []
    for path in DRIVE_ROOT.rglob("*.py"):
        if not path.is_file():
            continue
        # `utf-8-sig` igual ao gate irmão abaixo (BE-22): `ast.parse` estoura com
        # `invalid non-printable character U+FEFF` se o arquivo vier com BOM, e o
        # gate morre em vez de medir. Hoje nenhum arquivo do Drive tem BOM — isto é
        # para que o dia em que tiver não vire vermelho de bootstrap.
        text = path.read_text(encoding="utf-8-sig")
        for line_no in except_exception_without_capture(text):
            findings.append((rel(path), line_no))
    return findings


def sync_document_generations_in_views():
    findings = []
    for path in iter_files(".py"):
        path_rel = rel(path)
        if "/tests/" in f"/{path_rel}" or path.name.startswith("test"):
            continue
        if path.name != "views.py" and not path.name.endswith("_views.py"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            else:
                continue
            if name in SYNC_DOCUMENT_GENERATORS:
                findings.append((path_rel, node.lineno, name))
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
        "--max-sync-document-generations",
        type=int,
        default=None,
        help="falha se uma view chamar diretamente um gerador documental pesado (S-06)",
    )
    parser.add_argument(
        "--max-drive-except-without-capture",
        type=int,
        default=None,
        help="falha se handlers `except Exception` do Drive não chamarem core.errors.capture",
    )
    parser.add_argument(
        "--max-except-without-observability",
        type=int,
        default=None,
        help="falha se handlers genéricos de produção engolirem erros sem log, capture ou re-raise",
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
    print("\n== ORM em módulos de view (P-01) ==")
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

    silent_findings = production_excepts_without_observability()
    print("\n== except Exception sem observabilidade em produção (BE-18) ==")
    for file_path, line_no in silent_findings:
        print(f"  {file_path}:{line_no}")
    print(f"Total: {len(silent_findings)}")

    if (
        args.max_except_without_observability is not None
        and len(silent_findings) > args.max_except_without_observability
    ):
        print(
            f"\nERRO: {len(silent_findings)} handlers genéricos de produção "
            "engolem falhas sem log, core.errors.capture ou re-raise; acima da catraca de "
            f"{args.max_except_without_observability}.",
        )
        sys.exit(1)

    sync_findings = sync_document_generations_in_views()
    print("\n== Geração documental síncrona em views (S-06) ==")
    for file_path, line_no, name in sync_findings:
        print(f"  {file_path}:{line_no} {name}")
    print(f"Total: {len(sync_findings)}")

    if (
        args.max_sync_document_generations is not None
        and len(sync_findings) > args.max_sync_document_generations
    ):
        print(
            f"\nERRO: {len(sync_findings)} chamadas diretas a geradores documentais "
            "em views, acima da catraca de "
            f"{args.max_sync_document_generations}. Use DocumentoGeracao + Celery.",
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
